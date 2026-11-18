"""
Ghi nhật ký vi phạm khoảng cách theo ĐỢT.

Một đợt vi phạm bắt đầu khi mức cảnh báo ổn định (sau chống nhiễu) chuyển sang
CẢNH BÁO/NGUY HIỂM với một xe phía trước, và kết thúc khi trở về AN TOÀN hoặc
xe phía trước đổi sang xe khác. Trong đợt, hệ thống cập nhật khoảng cách/TTC nhỏ nhất
và mức cao nhất. Chỉ ghi CSDL khi mở đợt, khi nâng mức và khi đóng đợt - không ghi
mỗi khung hình.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from adas.alert.thresholds import RISK_ORDER
from adas.paths import APP_DIR, SNAPSHOT_DIR
from adas.pipeline import FrameResult
from adas.storage.database import Database, now_str



@dataclass
class _Episode:
    id: int
    track_id: Optional[int]
    level: str
    start_t: float
    min_distance: float
    min_ttc: Optional[float]
    snapshot_rel: Optional[str]


class ViolationRecorder:
    def __init__(self, db: Database, session_id: int, weather_factor_fn: Callable[[], float]):
        """weather_factor_fn: hệ số điều kiện hiện hành (có thể đổi giữa phiên qua Trợ lý AI)."""
        self.db = db
        self.session_id = session_id
        self.weather_factor_fn = weather_factor_fn
        self.snap_dir = SNAPSHOT_DIR / f"session_{session_id}"
        self.ep: Optional[_Episode] = None
        self.count = 0

    def update(self, result: FrameResult, t: float, speed_kmh: float, condition: str,
               save_snapshot: Callable[[Path], bool]) -> List[dict]:
        """
        Gọi mỗi khung. save_snapshot(path) -> bool lưu ảnh khung hiện tại (đã vẽ lớp phủ).
        Trả về danh sách sự kiện ('open' / 'update' / 'close') cho giao diện.
        """
        events = []
        lead = result.lead
        active = result.level in ("warning", "danger") and lead is not None

        if self.ep is not None and (not active or lead.det.track_id != self.ep.track_id):
            if result.level in ("warning", "danger") and lead is None:
                return events  # mất dấu xe tạm thời nhưng vẫn đang cảnh báo -> giữ đợt
            events.append(self._close(t))

        if not active:
            return events

        if self.ep is None:
            events.append(self._open(result, t, speed_kmh, condition, save_snapshot))
        else:
            ep = self.ep
            ep.min_distance = min(ep.min_distance, lead.distance_m)
            if lead.ttc_s is not None:
                ep.min_ttc = lead.ttc_s if ep.min_ttc is None else min(ep.min_ttc, lead.ttc_s)
            if RISK_ORDER[result.level] > RISK_ORDER[ep.level]:
                ep.level = result.level
                # Nâng lên NGUY HIỂM: chụp lại ảnh ở thời điểm nguy hiểm nhất
                if ep.snapshot_rel:
                    save_snapshot(APP_DIR / ep.snapshot_rel)
                self.db.update_violation(ep.id, {"level": ep.level, "min_distance_m": ep.min_distance,
                                                 "min_ttc_s": ep.min_ttc})
                events.append(self._event("update", t))
        return events

    def close(self, t: float) -> Optional[dict]:
        return self._close(t) if self.ep is not None else None

    # ------------------------------------------------------------------

    def _open(self, result: FrameResult, t, speed_kmh, condition, save_snapshot) -> dict:
        lead, thr = result.lead, result.thresholds
        data = {
            "session_id": self.session_id,
            "started_at": now_str(),
            "video_time_s": round(t, 2),
            "level": result.level,
            "track_id": lead.det.track_id,
            "vehicle_class": lead.det.class_name,
            "distance_m": round(lead.distance_m, 2),
            "min_distance_m": round(lead.distance_m, 2),
            "min_ttc_s": round(lead.ttc_s, 2) if lead.ttc_s is not None else None,
            "closing_speed_kmh": (round(lead.closing_speed_mps * 3.6, 1)
                                  if lead.closing_speed_mps is not None else None),
            "ego_speed_kmh": speed_kmh,
            "safe_threshold_m": round(thr.safe_m, 2),
            "danger_threshold_m": round(thr.danger_m, 2),
            "legal_min_gap_m": thr.legal_m,
            "road_condition": condition,
            "weather_factor": self.weather_factor_fn(),
        }
        vid = self.db.insert_violation(data)
        snap_rel = None
        path = self.snap_dir / f"violation_{vid}.jpg"
        if save_snapshot(path):
            # tương đối theo thư mục ứng dụng; thư mục ảnh đặt ở nơi khác (vd: khi kiểm thử) thì giữ đường dẫn tuyệt đối
            snap_rel = path.relative_to(APP_DIR).as_posix() if path.is_relative_to(APP_DIR) else path.as_posix()
            self.db.update_violation(vid, {"snapshot_path": snap_rel})
        self.ep = _Episode(id=vid, track_id=lead.det.track_id, level=result.level, start_t=t,
                           min_distance=lead.distance_m, min_ttc=lead.ttc_s, snapshot_rel=snap_rel)
        self.count += 1
        return self._event("open", t)

    def _close(self, t: float) -> dict:
        ep = self.ep
        self.db.update_violation(ep.id, {
            "ended_at": now_str(),
            "duration_s": round(max(t - ep.start_t, 0.0), 2),
            "level": ep.level,
            "min_distance_m": round(ep.min_distance, 2),
            "min_ttc_s": round(ep.min_ttc, 2) if ep.min_ttc is not None else None,
        })
        ev = self._event("close", t)
        self.ep = None
        return ev

    def _event(self, action: str, t: float) -> dict:
        ep = self.ep
        return {"action": action, "id": ep.id, "level": ep.level, "min_distance": ep.min_distance,
                "min_ttc": ep.min_ttc, "duration": max(t - ep.start_t, 0.0)}
