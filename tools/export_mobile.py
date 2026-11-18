"""
Xuất mô hình YOLO (models/best.pt) sang TFLite cho app mobile (Flutter, Android + iOS).

    python tools/export_mobile.py [--imgsz 288 640] [--tf-python <python của venv TensorFlow>]

Các bước:
  1. (Python hệ thống, có torch) ONNX với tọa độ hộp CHUẨN HÓA 0..1. Bắt buộc cho INT8: đầu ra gộp
     [x, y, w, h, điểm 5 lớp] chung một thang lượng tử; để tọa độ theo pixel (0..640) thì thang ≈ 2,5
     và mọi điểm lớp (0..1) bị làm tròn về 0.
  2. Ảnh hiệu chuẩn lấy từ tập train (letterbox giống Ultralytics, RGB 0..1, NHWC).
  3. (venv TensorFlow) onnx2tf -> các biến thể .tflite; chép 2 bản dùng trong app sang
     mobile/android/app/src/main/assets/models/ kèm model_meta_<HxW>.json (ô vào, tên lớp, cách giải mã).

Ô vào app dùng: 288x640 - đúng tỉ lệ dải đường app cắt từ khung 16:9 (mobile/android: core/Roi.kt).
Kết quả trên tập test (1300 ảnh; best.pt gốc mAP50 0,817 / mAP50-95 0,533 theo Ultralytics), chấm bằng
tools/eval_mobile.py (COCO 101 điểm, nên lệch Ultralytics vài phần nghìn):
                       384x640 cả khung    288x640 dải đường
  float16              0,8135 / 0,534      0,8127 / 0,531   -> "fp16": GPU delegate (Android GPU, iOS Metal)
  dynamic_range_quant  0,8094 / 0,526      0,8104 / 0,529   -> "int8": trọng số INT8, tính float, nhanh trên CPU
  integer_quant / full_integer_quant: 0 - lượng tử toàn phần làm nhánh tọa độ hộp (DFL) sập về 0,
  điểm lớp vẫn đúng. Không dùng.
Bước onnx2tf còn sinh thêm các bản INT16 rất lâu mà app không dùng: có fp16 + int8 trong tflite/ là đủ.

venv TensorFlow (tách khỏi Python hệ thống; đặt NGOÀI thư mục dự án vì đường dẫn "Đồ án"
có ký tự Unicode và Windows Application Control từng chặn DLL trong .venv của dự án):
    python -m venv %LOCALAPPDATA%\\adas_tfenv
    %LOCALAPPDATA%\\adas_tfenv\\Scripts\\python -m pip install tensorflow==2.19.0 tf_keras==2.19.0 ^
        onnx==1.17.0 onnxruntime sng4onnx onnx_graphsurgeon psutil "numpy<2.1" opencv-python-headless
    %LOCALAPPDATA%\\adas_tfenv\\Scripts\\python -m pip install --no-deps onnx2tf==1.26.9
onnx2tf >= 1.27 cần ai_edge_litert (không có bản Windows) nên phải dùng 1.26.9.
"""

import argparse
import glob
import json
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT.parent / "DEMO" / "Distance Estimation Model.v1i.yolov11"
OUT_DIR = ROOT / "mobile" / "android" / "app" / "src" / "main" / "assets" / "models"
# TensorFlow (file_io) không tạo được thư mục trong đường dẫn Unicode ("Đồ án") -> build ở thư mục ASCII
BUILD_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "adas_model_build"
DEFAULT_TF_PY = Path(os.environ.get("LOCALAPPDATA", "")) / "adas_tfenv" / "Scripts" / "python.exe"
# biến thể đưa vào app (xem bảng kết quả ở đầu file)
KEEP = {"float16": "fp16", "dynamic_range_quant": "int8"}


def letterbox(img, h, w):
    """Giống Ultralytics LetterBox(auto=False): giữ tỉ lệ, đệm xám 114 ở giữa."""
    r = min(h / img.shape[0], w / img.shape[1])
    nh, nw = round(img.shape[0] * r), round(img.shape[1] * r)
    top, left = (h - nh) // 2, (w - nw) // 2
    out = np.full((h, w, 3), 114, np.uint8)
    out[top:top + nh, left:left + nw] = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    return out


def export_onnx(weights: Path, h: int, w: int, out: Path) -> list:
    import onnx
    import onnxslim
    import torch
    from ultralytics import YOLO
    from ultralytics.nn.modules import Detect

    yolo = YOLO(str(weights))
    net = yolo.model.float().eval().fuse()
    for m in net.modules():
        if isinstance(m, Detect):
            m.export, m.format, m.dynamic = True, "onnx", False

    class Normalized(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.net = net
            self.register_buffer("scale", torch.tensor([w, h, w, h], dtype=torch.float32).view(1, 4, 1))

        def forward(self, x):
            y = self.net(x)
            y = y[0] if isinstance(y, (list, tuple)) else y
            return torch.cat([y[:, :4] / self.scale, y[:, 4:]], 1)

    torch.onnx.export(Normalized(), torch.zeros(1, 3, h, w), str(out), opset_version=17,
                      input_names=["images"], output_names=["output0"], do_constant_folding=True)
    onnx.save(onnxslim.slim(onnx.load(str(out))), str(out))
    return [yolo.names[i] for i in sorted(yolo.names)]


def calibration_data(build: Path, h: int, w: int, n: int = 200) -> Path:
    files = sorted(glob.glob(str(DATASET / "train" / "images" / "*")))
    random.Random(0).shuffle(files)
    imgs = [letterbox(cv2.imdecode(np.fromfile(f, np.uint8), 1), h, w)[..., ::-1] for f in files[:n]]
    arr = np.stack(imgs).astype(np.float32) / 255.0
    calib = build / "calib.npy"
    np.save(calib, arr)
    # onnx2tf luôn nạp file mẫu này từ thư mục làm việc (nếu thiếu sẽ tải từ GitHub và lỗi khi offline)
    np.save(build / "calibration_image_sample_data_20x128x128x3_float32.npy",
            np.stack([cv2.resize(x, (128, 128)) for x in arr[:20]]).astype(np.float32))
    return calib


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weights", default=str(ROOT / "models" / "best.pt"))
    ap.add_argument("--imgsz", type=int, nargs=2, default=[288, 640], metavar=("H", "W"),
                    help="ô vào (bội số 32). 288x640 = dải đường app cắt từ khung 16:9 (core/Roi.kt); "
                         "384x640 = cả khung 16:9")
    ap.add_argument("--tf-python", default=str(DEFAULT_TF_PY))
    args = ap.parse_args()
    h, w = args.imgsz
    tag = f"{h}x{w}"
    build = BUILD_DIR / tag
    build.mkdir(parents=True, exist_ok=True)

    onnx_path = build / f"best_{tag}.onnx"
    names = export_onnx(Path(args.weights), h, w, onnx_path)
    print(f"[1/3] ONNX: {onnx_path.name}  lớp {names}")
    calib = calibration_data(build, h, w)
    print(f"[2/3] Ảnh hiệu chuẩn: {calib.name}")

    tf_out = build / "tflite"
    cmd = [args.tf_python, "-m", "onnx2tf.onnx2tf", "-i", onnx_path.name, "-o", tf_out.name, "-nuo",
           "-oiqt", "-qt", "per-channel", "-cind", "images", calib.name, "[[[[0,0,0]]]]", "[[[[1,1,1]]]]"]
    env = dict(os.environ, TF_CPP_MIN_LOG_LEVEL="2", PYTHONIOENCODING="utf-8")
    with open(build / "onnx2tf.log", "w", encoding="utf-8") as log:
        subprocess.run(cmd, cwd=build, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)

    meta = {
        "source": Path(args.weights).name, "input": {"height": h, "width": w, "layout": "NHWC",
                                                      "color": "RGB", "scale": "0..1", "letterbox_pad": 114},
        "output": {"shape": [1, 4 + len(names), None], "layout": "[cx, cy, w, h, score_lớp...] x anchors",
                   "boxes": "chuẩn hóa 0..1 theo ô vào (nhân W/H rồi bỏ letterbox)", "nms": "chưa có - app tự làm"},
        "classes": names, "files": {},
    }
    for src, short in KEEP.items():
        f = tf_out / f"best_{tag}_{src}.tflite"
        dst = OUT_DIR / f"adas_yolo_{tag}_{short}.tflite"
        shutil.copyfile(f, dst)
        meta["files"][short] = dst.name
    (OUT_DIR / f"model_meta_{tag}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[3/3] TFLite -> {OUT_DIR}: {', '.join(meta['files'].values())}")


if __name__ == "__main__":
    sys.exit(main())
