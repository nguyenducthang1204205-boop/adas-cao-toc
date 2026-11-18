"""
Nguồn khung hình: file video hành trình, camera trực tiếp (USB/RTSP/HTTP), ảnh tĩnh.
"""

import threading
import time
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class FrameSource:
    is_live = False
    is_image = False
    fps = 30.0
    total_frames = 0
    width = 0
    height = 0
    name = ""
    last_decode_ms = 0.0   # thời gian giải mã khung gần nhất (tầng Video Stream)

    def read(self) -> Tuple[bool, Optional[np.ndarray], float]:
        """Trả về (ok, frame BGR, thời điểm t tính bằng giây)."""
        raise NotImplementedError

    def release(self) -> None:
        pass


class VideoFileSource(FrameSource):
    def __init__(self, path: str, realtime: bool = True):
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise IOError(f"Không mở được video: {path}")
        self.name = Path(path).name
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.realtime = realtime
        self.frame_idx = -1
        self._start_wall: Optional[float] = None

    def read(self):
        now = time.perf_counter()
        if self._start_wall is None:
            self._start_wall = now
        elif self.realtime:
            # Bám thời gian thực: nếu xử lý chậm thì bỏ qua khung; nếu nhanh thì chờ
            expected = int((now - self._start_wall) * self.fps)
            while self.frame_idx + 1 < expected:
                if not self.cap.grab():
                    return False, None, 0.0
                self.frame_idx += 1
            wait = (self.frame_idx + 1) / self.fps - (now - self._start_wall)
            if wait > 0:
                time.sleep(wait)

        t0 = time.perf_counter()
        ok, frame = self.cap.read()
        self.last_decode_ms = (time.perf_counter() - t0) * 1000
        if not ok:
            return False, None, 0.0
        self.frame_idx += 1
        return True, frame, self.frame_idx / self.fps

    def restart_clock(self) -> None:
        """Gọi sau khi tạm dừng để không bị bỏ khung hàng loạt."""
        self._start_wall = time.perf_counter() - (self.frame_idx + 1) / self.fps

    def release(self):
        self.cap.release()


class CameraSource(FrameSource):
    """Luồng camera trực tiếp - luôn lấy khung mới nhất để giảm độ trễ."""
    is_live = True

    def __init__(self, spec):
        backend = cv2.CAP_DSHOW if isinstance(spec, int) else cv2.CAP_ANY
        self.cap = cv2.VideoCapture(spec, backend)
        if not self.cap.isOpened():
            raise IOError(f"Không kết nối được camera: {spec}")
        self.name = f"Camera {spec}" if isinstance(spec, int) else str(spec)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        if self.fps > 120 or self.fps < 1:
            self.fps = 30.0
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._frame = None
        self._t = 0.0
        self._seq = 0
        self._last_seq = 0
        self._running = True
        self._cond = threading.Condition()
        self._thread = threading.Thread(target=self._grab_loop, daemon=True)
        self._thread.start()

    def _grab_loop(self):
        t0 = time.perf_counter()
        while self._running:
            t1 = time.perf_counter()
            ok, frame = self.cap.read()
            self.last_decode_ms = (time.perf_counter() - t1) * 1000
            with self._cond:
                if not ok:
                    self._running = False
                else:
                    self._frame, self._t = frame, time.perf_counter() - t0
                    self._seq += 1
                self._cond.notify_all()

    def read(self):
        with self._cond:
            self._cond.wait_for(lambda: self._seq != self._last_seq or not self._running, timeout=5.0)
            if self._seq == self._last_seq:
                return False, None, 0.0
            self._last_seq = self._seq
            return True, self._frame, self._t

    def release(self):
        self._running = False
        self._thread.join(timeout=1.0)
        self.cap.release()


class ImageSource(FrameSource):
    is_image = True

    def __init__(self, path: str):
        data = np.fromfile(path, dtype=np.uint8)  # hỗ trợ đường dẫn có dấu tiếng Việt
        self.frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if self.frame is None:
            raise IOError(f"Không đọc được ảnh: {path}")
        self.name = Path(path).name
        self.height, self.width = self.frame.shape[:2]
        self.total_frames = 1
        self._done = False

    def read(self):
        if self._done:
            return False, None, 0.0
        self._done = True
        return True, self.frame.copy(), 0.0


SOURCE_TYPE_VI = {"video": "File video", "camera": "Camera USB", "stream": "Camera IP / luồng", "image": "Ảnh"}


def classify_source(spec: str) -> str:
    """Phân loại nguồn: 'camera' | 'stream' | 'image' | 'video' (không cần mở nguồn)."""
    spec = spec.strip()
    if spec.isdigit():
        return "camera"
    if spec.lower().startswith(("rtsp://", "http://", "https://", "udp://")):
        return "stream"
    if Path(spec).suffix.lower() in IMAGE_EXTS:
        return "image"
    return "video"


def normalize_source(spec: str) -> str:
    """Chuẩn hóa đường dẫn file (tuyệt đối, dấu '\\') để 1 nguồn chỉ có 1 bản ghi trong CSDL."""
    spec = spec.strip()
    if classify_source(spec) in ("video", "image"):
        return str(Path(spec).resolve())
    return spec


def probe_source(spec: str) -> dict:
    """Kiểm tra kết nối: mở nguồn, đọc 1 khung. Trả về thông tin hoặc ném IOError."""
    src = open_source(spec, realtime=False)
    try:
        ok, frame, _ = src.read()
        if not ok:
            raise IOError("Kết nối được nhưng không đọc được khung hình")
        h, w = frame.shape[:2]
        return {"width": w, "height": h, "fps": round(src.fps or 0, 1),
                "frames": getattr(src, "total_frames", 0), "frame": frame}
    finally:
        src.release()


def find_cameras(max_index: int = 5) -> List[int]:
    """Dò các camera USB đang cắm (chỉ số 0..max_index-1)."""
    try:  # chỉ số không có camera sinh cảnh báo của OpenCV - tắt cho gọn (2 = chỉ báo lỗi)
        cv2.setLogLevel(2)
    except AttributeError:
        pass
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened() and cap.read()[0]:
            found.append(i)
        cap.release()
    return found


def open_source(spec: str, realtime: bool = True) -> FrameSource:
    spec = spec.strip()
    kind = classify_source(spec)
    if kind == "camera":
        return CameraSource(int(spec))
    if kind == "stream":
        return CameraSource(spec)
    if kind == "image":
        return ImageSource(spec)
    if not Path(spec).is_file():
        raise IOError(f"Không tìm thấy file video: {spec}")
    return VideoFileSource(spec, realtime=realtime)


def read_first_frame(spec: str) -> Optional[np.ndarray]:
    """Lấy 1 khung để hiệu chỉnh IPM khi chưa chạy giám sát."""
    try:
        src = open_source(spec, realtime=False)
    except IOError:
        return None
    try:
        ok, frame, _ = src.read()
        return frame if ok else None
    finally:
        src.release()
