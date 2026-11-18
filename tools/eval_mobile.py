"""
Đo mAP các mô hình TFLite của app mobile trên tập test, gồm cả kiểu cắt dải đường của app (core/Roi.kt).

    <python của venv TensorFlow> tools/eval_mobile.py [--limit N] [--out docs/ket_qua_mobile.json]

(venv TensorFlow: xem đầu tools/export_mobile.py - Python hệ thống không có TensorFlow.)

Ba phép đo cho mỗi biến thể (fp16, int8):
  full  - mô hình 384x640, cả khung, nhãn đầy đủ (đối chiếu với số đã công bố 0,817 / 0,533)
  band  - mô hình 384x640, cả khung, nhưng chỉ chấm trong dải đường (nhãn và hộp dự đoán cắt theo dải)
  crop  - mô hình 288x640 chạy trên dải đường đã cắt (đúng cách app làm), chấm như "band"
"band" và "crop" dùng cùng bộ nhãn nên so sánh trực tiếp được: chênh lệch là do mô hình 288x640 + cắt vùng.

Dải đường: cao bằng bề_ngang x 288/640 (80 % chiều cao khung 16:9), sát mép dưới - tức bỏ phần trời phía trên.
App đặt dải theo chân trời của hiệu chỉnh (35 % dải nằm trên chân trời); ảnh tập test không có hiệu chỉnh
nên dùng cách đặt sát mép dưới, tương đương khi camera hướng thẳng (chân trời ở khoảng giữa khung).
Nhãn bị cắt mất hơn một nửa diện tích bởi mép dải thì bỏ khỏi cả hai phép "band" và "crop".

mAP theo kiểu COCO (nội suy 101 điểm, IoU 0,50:0,95), hộp dự đoán ngưỡng 0,001, NMS theo lớp IoU 0,7,
tối đa 300 hộp - giống Ultralytics val.
"""

import argparse
import glob
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from export_mobile import DATASET, OUT_DIR, letterbox  # noqa: E402

IOUS = np.linspace(0.5, 0.95, 10)


def load_model(tag: str, kind: str):
    import tensorflow as tf
    meta = json.loads((OUT_DIR / f"model_meta_{tag}.json").read_text(encoding="utf-8"))
    # tf.lite không mở được đường dẫn Unicode ("Đồ án") -> nạp bằng bytes
    # num_threads=8 trên i7-12650H (6 nhân mạnh + 4 nhân yếu) chậm hơn ~140 lần so với 4 (1,5 s so với
    # 10 ms): cùng hiện tượng big.LITTLE như trên điện thoại (xem detector/YoloDetector.kt)
    it = tf.lite.Interpreter(model_content=(OUT_DIR / meta["files"][kind]).read_bytes(), num_threads=4)
    it.allocate_tensors()
    return it, meta["input"]["height"], meta["input"]["width"], len(meta["classes"])


def infer(it, img, h, w):
    """Ảnh BGR -> (hộp xyxy pixel ảnh vào, điểm, lớp), đã NMS."""
    r = min(h / img.shape[0], w / img.shape[1])
    nh, nw = round(img.shape[0] * r), round(img.shape[1] * r)
    top, left = (h - nh) // 2, (w - nw) // 2
    x = letterbox(img, h, w)[..., ::-1].astype(np.float32)[None] / 255.0
    inp, out = it.get_input_details()[0], it.get_output_details()[0]
    it.set_tensor(inp["index"], x)
    it.invoke()
    y = it.get_tensor(out["index"])[0]  # (4+nc, N), tọa độ chuẩn hóa theo ô vào
    scores = y[4:].max(0)
    cls = y[4:].argmax(0)
    keep = scores > 0.001
    b, scores, cls = y[:4, keep].T, scores[keep], cls[keep]
    if len(scores) > 3000:
        idx = np.argsort(-scores)[:3000]
        b, scores, cls = b[idx], scores[idx], cls[idx]
    cx, cy, bw, bh = b[:, 0] * w, b[:, 1] * h, b[:, 2] * w, b[:, 3] * h
    xyxy = np.stack([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], 1)
    xyxy = (xyxy - [left, top, left, top]) / r
    xyxy[:, [0, 2]] = xyxy[:, [0, 2]].clip(0, img.shape[1])
    xyxy[:, [1, 3]] = xyxy[:, [1, 3]].clip(0, img.shape[0])
    keep = nms(xyxy, scores, cls, 0.7)[:300]
    return xyxy[keep], scores[keep], cls[keep]


def nms(boxes, scores, cls, thr):
    off = boxes + (cls[:, None] * 10000.0)  # NMS theo lớp: dời hộp mỗi lớp ra xa nhau
    order = np.argsort(-scores)
    keep = []
    area = (off[:, 2] - off[:, 0]) * (off[:, 3] - off[:, 1])
    while order.size:
        i = order[0]
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(off[i, 0], off[rest, 0])
        yy1 = np.maximum(off[i, 1], off[rest, 1])
        xx2 = np.minimum(off[i, 2], off[rest, 2])
        yy2 = np.minimum(off[i, 3], off[rest, 3])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        iou = inter / (area[i] + area[rest] - inter + 1e-9)
        order = rest[iou <= thr]
    return np.array(keep, dtype=int)


def iou_matrix(a, b):
    xx1 = np.maximum(a[:, None, 0], b[None, :, 0])
    yy1 = np.maximum(a[:, None, 1], b[None, :, 1])
    xx2 = np.minimum(a[:, None, 2], b[None, :, 2])
    yy2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
    aa = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    ab = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / (aa[:, None] + ab[None, :] - inter + 1e-9)


class Scorer:
    """Gom kết quả từng ảnh rồi tính mAP50 và mAP50-95 (COCO, nội suy 101 điểm)."""

    def __init__(self, nc):
        self.nc = nc
        self.tp, self.conf, self.cls = [], [], []
        self.n_gt = np.zeros(nc, int)

    def add(self, pb, ps, pc, gb, gc):
        for c in gc:
            self.n_gt[c] += 1
        tp = np.zeros((len(ps), len(IOUS)), bool)
        if len(ps) and len(gc):
            ious = iou_matrix(pb, gb)
            ious[pc[:, None] != gc[None, :]] = 0
            order = np.argsort(-ps)
            best = ious.max(1)
            for k, t in enumerate(IOUS):
                used = np.zeros(len(gc), bool)
                for i in order[best[order] >= t]:  # hộp không chồng nhãn nào đủ IoU thì chắc chắn là FP
                    cand = np.where((ious[i] >= t) & ~used)[0]
                    if cand.size:
                        j = cand[np.argmax(ious[i, cand])]
                        used[j] = True
                        tp[i, k] = True
        self.tp.append(tp)
        self.conf.append(ps)
        self.cls.append(pc)

    def result(self):
        tp, conf, cls = np.concatenate(self.tp), np.concatenate(self.conf), np.concatenate(self.cls)
        aps = []
        for c in range(self.nc):
            if self.n_gt[c] == 0:
                continue
            m = cls == c
            order = np.argsort(-conf[m])
            t = tp[m][order]
            ap = []
            for k in range(len(IOUS)):
                ctp = np.cumsum(t[:, k])
                cfp = np.cumsum(~t[:, k])
                rec = ctp / self.n_gt[c]
                prec = ctp / np.maximum(ctp + cfp, 1)
                prec = np.maximum.accumulate(prec[::-1])[::-1] if len(prec) else prec
                rs = np.linspace(0, 1, 101)
                q = [prec[np.searchsorted(rec, r, side="left")] if np.searchsorted(rec, r, side="left") < len(prec)
                     else 0.0 for r in rs]
                ap.append(float(np.mean(q)))
            aps.append(ap)
        aps = np.array(aps)
        return {"map50": round(float(aps[:, 0].mean()), 4), "map50_95": round(float(aps.mean()), 4),
                "n_gt": int(self.n_gt.sum())}


def labels(img_path, w, h):
    lp = Path(img_path).parent.parent / "labels" / (Path(img_path).stem + ".txt")
    if not lp.exists():
        return np.zeros((0, 4)), np.zeros(0, int)
    rows = [r.split() for r in lp.read_text().splitlines() if r.strip()]
    if not rows:
        return np.zeros((0, 4)), np.zeros(0, int)
    a = np.array([[float(v) for v in r[:5]] for r in rows])
    cx, cy, bw, bh = a[:, 1] * w, a[:, 2] * h, a[:, 3] * w, a[:, 4] * h
    return np.stack([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], 1), a[:, 0].astype(int)


def to_band(boxes, top, keep_frac=None):
    """Cắt hộp theo dải [top, đáy); keep_frac: bỏ hộp còn lại ít hơn tỉ lệ diện tích này."""
    b = boxes.copy()
    b[:, 1] = np.maximum(b[:, 1], top)
    b[:, 3] = np.maximum(b[:, 3], top)
    area0 = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    area1 = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    ok = area1 > 0 if keep_frac is None else area1 >= keep_frac * np.maximum(area0, 1e-9)
    return b, ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0, help="chỉ chấm N ảnh đầu (thử nhanh)")
    ap.add_argument("--wide", default="384x640")
    ap.add_argument("--band", default="288x640")
    ap.add_argument("--out", default=str(ROOT / "docs" / "ket_qua_mobile.json"))
    args = ap.parse_args()
    files = sorted(glob.glob(str(DATASET / "test" / "images" / "*")))
    if args.limit:
        files = files[:args.limit]
    report = {"images": len(files), "results": {}}
    for kind in ("fp16", "int8"):
        wide, wh, ww, nc = load_model(args.wide, kind)
        band, bh_, bw_, _ = load_model(args.band, kind)
        sc = {k: Scorer(nc) for k in ("full", "band", "crop")}
        t0 = time.time()
        times = {"wide": [], "band": []}
        for f in files:
            img = cv2.imdecode(np.fromfile(f, np.uint8), cv2.IMREAD_COLOR)
            H, W = img.shape[:2]
            gb, gc = labels(f, W, H)
            t = time.perf_counter()
            pb, ps, pc = infer(wide, img, wh, ww)
            times["wide"].append(time.perf_counter() - t)
            sc["full"].add(pb, ps, pc, gb, gc)
            band_h = min(H, round(W * bh_ / bw_))
            top = H - band_h
            gbb, ok = to_band(gb, top, keep_frac=0.5)
            gbb, gcb = gbb[ok], gc[ok]
            pbb, okp = to_band(pb, top)
            sc["band"].add(pbb[okp], ps[okp], pc[okp], gbb, gcb)
            t = time.perf_counter()
            qb, qs, qc = infer(band, img[top:], bh_, bw_)
            times["band"].append(time.perf_counter() - t)
            qb[:, [1, 3]] += top
            sc["crop"].add(qb, qs, qc, gbb, gcb)
        res = {k: v.result() for k, v in sc.items()}
        res["ms_per_image_pc"] = {k: round(1000 * float(np.median(v)), 1) for k, v in times.items()}
        report["results"][kind] = res
        print(f"{kind}: {json.dumps(res, ensure_ascii=False)}  ({time.time() - t0:.0f} s)", flush=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {args.out}")


if __name__ == "__main__":
    sys.exit(main())
