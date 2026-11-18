"""
Cơ sở dữ liệu SQLite của hệ thống: cấu hình, ma trận camera, nhật ký vi phạm khoảng cách.

File: data/adas.db (tạo tự động). Mỗi thao tác mở một kết nối ngắn nên an toàn khi
luồng giao diện và luồng xử lý video cùng truy cập; chế độ WAL cho phép đọc trong lúc ghi.

Lược đồ:
  video_sources        Danh sách nguồn video/camera
  camera_calibrations  Ma trận camera của từng nguồn: K, H (IPM), R, tiêu cự, chiều cao, góc nghiêng
                       (mỗi lần hiệu chỉnh 1 dòng; dòng mới nhất đang được dùng)
  system_config        Cấu hình hiện hành (mục, tham số, giá trị JSON)
  config_history       Lịch sử thay đổi cấu hình (bản chụp toàn bộ cấu hình + lý do)
  monitoring_sessions  Phiên giám sát (nguồn, mô hình, thiết bị, cấu hình lúc chạy)
  violations           Đợt vi phạm khoảng cách an toàn (thuộc 1 phiên)
  v_session_summary    View thống kê số vi phạm theo phiên
"""

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from adas.stream.sources import normalize_source

from adas.paths import DB_PATH
SCHEMA_VERSION = 4

SCHEMA = """
PRAGMA foreign_keys = ON;

-- Nguồn video/camera đã đăng ký (UC Quản lý nguồn video/camera)
CREATE TABLE IF NOT EXISTS video_sources (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    source_type       TEXT NOT NULL CHECK (source_type IN ('video', 'camera', 'stream', 'image')),
    uri               TEXT NOT NULL UNIQUE, -- đường dẫn file / chỉ số camera / URL luồng
    description       TEXT,
    created_at        TEXT NOT NULL,
    last_used_at      TEXT
);

-- Ma trận camera (UC Cấu hình thông số IPM): mỗi lần hiệu chỉnh 1 dòng, dòng mới nhất đang dùng
CREATE TABLE IF NOT EXISTS camera_calibrations (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id          INTEGER REFERENCES video_sources(id) ON DELETE CASCADE,
    created_at         TEXT NOT NULL,
    -- manual: chấm 4 điểm · auto: quét video · imported: CSDL cũ · pose: chiều cao + chân trời ·
    -- online: tự hoàn thiện khi chạy
    method             TEXT NOT NULL CHECK (method IN ('manual', 'auto', 'imported', 'pose', 'online')),
    frame_width        INTEGER NOT NULL,
    frame_height       INTEGER NOT NULL,
    intrinsic_matrix   TEXT,                -- K 3x3 (JSON): [[f,0,cx],[0,f,cy],[0,0,1]]
    homography_matrix  TEXT NOT NULL,       -- H 3x3 (JSON): pixel ảnh -> mặt đường (mét)
    rotation_matrix    TEXT,                -- R 3x3 (JSON): hệ mặt đường -> hệ camera
    focal_px           REAL,
    horizon_y          REAL,                -- hàng pixel đường chân trời
    camera_height_m    REAL,
    camera_offset_m    REAL,                -- camera nằm sau đầu xe (m)
    pitch_deg          REAL,                -- góc chúc xuống của camera (độ)
    params_json        TEXT NOT NULL,       -- tham số hiệu chỉnh: 4 điểm, W, L, d0, làn, tầm đo...
    note               TEXT
);
CREATE INDEX IF NOT EXISTS idx_calibrations_source ON camera_calibrations(source_id, id);

-- Cấu hình hiện hành: mỗi tham số một dòng, giá trị lưu dạng JSON
CREATE TABLE IF NOT EXISTS system_config (
    section     TEXT NOT NULL,              -- model | calibration | policy | alert | assistant | app
    key         TEXT NOT NULL,              -- tên tham số
    value       TEXT NOT NULL,              -- giá trị (JSON)
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (section, key)
);

-- Lịch sử cấu hình: mỗi lần thay đổi lưu 1 bản chụp đầy đủ
CREATE TABLE IF NOT EXISTS config_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    changed_at   TEXT NOT NULL,
    reason       TEXT NOT NULL,             -- vd: "Hiệu chỉnh IPM", "Trợ lý AI: Mưa to"
    config_json  TEXT NOT NULL
);

-- Phiên giám sát: 1 lần chạy trên 1 nguồn video/camera
CREATE TABLE IF NOT EXISTS monitoring_sessions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at        TEXT NOT NULL,
    ended_at          TEXT,
    source_id         INTEGER REFERENCES video_sources(id) ON DELETE SET NULL,
    source            TEXT NOT NULL,        -- đường dẫn video / chỉ số camera / URL
    source_type       TEXT NOT NULL CHECK (source_type IN ('video', 'camera', 'stream', 'image')),
    model_weights     TEXT,
    device            TEXT,                 -- GPU | CPU
    frame_width       INTEGER,
    frame_height      INTEGER,
    frames_processed  INTEGER NOT NULL DEFAULT 0,
    avg_fps           REAL,
    config_json       TEXT NOT NULL         -- cấu hình tại thời điểm chạy (để truy vết)
);

-- Vi phạm: 1 đợt xe phía trước ở gần hơn ngưỡng an toàn (từ lúc bắt đầu tới khi an toàn trở lại)
CREATE TABLE IF NOT EXISTS violations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          INTEGER NOT NULL REFERENCES monitoring_sessions(id) ON DELETE CASCADE,
    started_at          TEXT NOT NULL,
    ended_at            TEXT,
    video_time_s        REAL,               -- thời điểm trong video (giây)
    duration_s          REAL,               -- thời lượng đợt vi phạm (giây)
    level               TEXT NOT NULL CHECK (level IN ('warning', 'danger')),  -- mức cao nhất
    track_id            INTEGER,
    vehicle_class       TEXT,
    distance_m          REAL NOT NULL,      -- khoảng cách lúc bắt đầu
    min_distance_m      REAL NOT NULL,      -- khoảng cách nhỏ nhất trong đợt
    min_ttc_s           REAL,               -- TTC nhỏ nhất
    closing_speed_kmh   REAL,               -- tốc độ tiếp cận lúc bắt đầu
    ego_speed_kmh       REAL NOT NULL,
    safe_threshold_m    REAL NOT NULL,      -- ngưỡng cảnh báo lúc đó
    danger_threshold_m  REAL NOT NULL,      -- ngưỡng nguy hiểm lúc đó
    legal_min_gap_m     REAL,               -- khoảng cách tối thiểu theo quy định (NULL nếu < 60 km/h)
    road_condition      TEXT,
    weather_factor      REAL,
    snapshot_path       TEXT                -- ảnh bằng chứng (đường dẫn tương đối data/...)
);

CREATE INDEX IF NOT EXISTS idx_violations_session ON violations(session_id);
CREATE INDEX IF NOT EXISTS idx_violations_started ON violations(started_at);
CREATE INDEX IF NOT EXISTS idx_violations_level   ON violations(level);

CREATE VIEW IF NOT EXISTS v_session_summary AS
SELECT s.id, s.started_at, s.ended_at, s.source, s.source_type, s.frames_processed, s.avg_fps,
       COUNT(v.id)                                   AS total_violations,
       COALESCE(SUM(v.level = 'danger'), 0)          AS danger_count,
       COALESCE(SUM(v.level = 'warning'), 0)         AS warning_count,
       MIN(v.min_distance_m)                         AS closest_distance_m,
       COALESCE(SUM(v.duration_s), 0)                AS total_violation_s
FROM monitoring_sessions s
LEFT JOIN violations v ON v.session_id = s.id
GROUP BY s.id;
"""

VIOLATION_FIELDS = (
    "session_id", "started_at", "ended_at", "video_time_s", "duration_s", "level", "track_id",
    "vehicle_class", "distance_m", "min_distance_m", "min_ttc_s", "closing_speed_kmh",
    "ego_speed_kmh", "safe_threshold_m", "danger_threshold_m", "legal_min_gap_m",
    "road_condition", "weather_factor", "snapshot_path",
)


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _probe_size(uri: str):
    """Kích thước khung của nguồn (dùng khi nâng cấp CSDL); mặc định 1280x720 nếu không mở được."""
    from adas.stream.sources import read_first_frame
    frame = read_first_frame(uri)
    return (frame.shape[1], frame.shape[0]) if frame is not None else (1280, 720)


def _flatten_config(cfg: dict) -> List[tuple]:
    """{'policy': {'time_gap_s': 2}, 'speed_kmh': 80} -> [('policy','time_gap_s','2'), ('app','speed_kmh','80')]"""
    rows = []
    for k, v in cfg.items():
        if isinstance(v, dict):
            rows += [(k, kk, json.dumps(vv, ensure_ascii=False)) for kk, vv in v.items()]
        else:
            rows.append(("app", k, json.dumps(v, ensure_ascii=False)))
    return rows


def _unflatten_config(rows: Iterable) -> dict:
    cfg: Dict = {}
    for section, key, value in rows:
        val = json.loads(value)
        if section == "app":
            cfg[key] = val
        else:
            cfg.setdefault(section, {})[key] = val
    return cfg


class Database:
    def __init__(self, path: Path = DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def init_schema(self) -> None:
        with closing(self._connect()) as con:
            con.execute("PRAGMA journal_mode = WAL")
            version = con.execute("PRAGMA user_version").fetchone()[0]
            con.executescript(SCHEMA)
            # Nâng cấp CSDL tạo bởi phiên bản 1: thêm liên kết phiên -> nguồn
            cols = [r[1] for r in con.execute("PRAGMA table_info(monitoring_sessions)")]
            if version < 2 and "source_id" not in cols:
                con.execute("ALTER TABLE monitoring_sessions ADD COLUMN source_id INTEGER "
                            "REFERENCES video_sources(id) ON DELETE SET NULL")
            con.execute("CREATE INDEX IF NOT EXISTS idx_sessions_source ON monitoring_sessions(source_id)")
            # Nâng cấp CSDL phiên bản 2: chuyển hiệu chỉnh từ video_sources.calibration_json
            # sang bảng camera_calibrations (kèm ma trận camera), rồi bỏ cột cũ
            src_cols = [r[1] for r in con.execute("PRAGMA table_info(video_sources)")]
            if "calibration_json" in src_cols:
                for r in con.execute("SELECT id, uri, calibration_json FROM video_sources "
                                     "WHERE calibration_json IS NOT NULL").fetchall():
                    size = con.execute("SELECT frame_width, frame_height FROM monitoring_sessions "
                                       "WHERE source_id = ? ORDER BY id DESC LIMIT 1", (r["id"],)).fetchone()
                    self._insert_calibration(con, r["id"], json.loads(r["calibration_json"]),
                                             tuple(size) if size else _probe_size(r["uri"]),
                                             "imported", "Chuyển từ CSDL phiên bản 2")
                con.execute("ALTER TABLE video_sources DROP COLUMN calibration_json")
            # Nâng cấp CSDL phiên bản 3: thêm cách hiệu chỉnh 'pose' / 'online' vào ràng buộc CHECK
            # (SQLite không sửa được CHECK -> dựng lại bảng, giữ nguyên id và dữ liệu)
            sql = con.execute("SELECT sql FROM sqlite_master WHERE name = 'camera_calibrations'").fetchone()[0]
            if "'online'" not in sql:
                con.execute("ALTER TABLE camera_calibrations RENAME TO camera_calibrations_v3")
                con.executescript(SCHEMA)
            if con.execute("SELECT 1 FROM sqlite_master WHERE name = 'camera_calibrations_v3'").fetchone():
                con.execute("INSERT OR IGNORE INTO camera_calibrations SELECT * FROM camera_calibrations_v3")
                con.execute("DROP TABLE camera_calibrations_v3")    # xóa kèm chỉ mục cũ -> tạo lại
                con.execute("CREATE INDEX IF NOT EXISTS idx_calibrations_source "
                            "ON camera_calibrations(source_id, id)")
            con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            con.commit()

    # ------------------------------------------------------------------
    # Ma trận camera
    # ------------------------------------------------------------------

    @staticmethod
    def _insert_calibration(con, source_id, params: dict, frame_size, method: str, note: str) -> int:
        from adas.config import CalibrationConfig, _from_dict
        from adas.distance.ipm import GroundPlaneMapper
        m = GroundPlaneMapper(_from_dict(CalibrationConfig, params), frame_size).model
        dump = lambda v: json.dumps(v) if v is not None else None  # noqa: E731
        cur = con.execute(
            "INSERT INTO camera_calibrations(source_id, created_at, method, frame_width, frame_height, "
            "intrinsic_matrix, homography_matrix, rotation_matrix, focal_px, horizon_y, camera_height_m, "
            "camera_offset_m, pitch_deg, params_json, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (source_id, now_str(), method, frame_size[0], frame_size[1], dump(m["intrinsic_matrix"]),
             dump(m["homography_matrix"]), dump(m["rotation_matrix"]), m["focal_px"], m["horizon_y"],
             m["camera_height_m"], m["camera_offset_m"], m["pitch_deg"],
             json.dumps(params, ensure_ascii=False), note))
        return int(cur.lastrowid)

    def save_calibration(self, source_id: Optional[int], params: dict, frame_size, method: str = "manual",
                         note: str = "") -> int:
        """Lưu 1 lần hiệu chỉnh (tham số + ma trận camera tính từ tham số). Trả về id."""
        with closing(self._connect()) as con, con:
            return self._insert_calibration(con, source_id, params, tuple(frame_size), method, note)

    def latest_calibration(self, source_id: int) -> Optional[sqlite3.Row]:
        with closing(self._connect()) as con:
            return con.execute("SELECT * FROM camera_calibrations WHERE source_id = ? ORDER BY id DESC LIMIT 1",
                               (source_id,)).fetchone()

    def list_calibrations(self) -> List[sqlite3.Row]:
        with closing(self._connect()) as con:
            return con.execute(
                "SELECT c.*, s.name AS source_name, "
                "c.id = (SELECT MAX(id) FROM camera_calibrations c2 WHERE c2.source_id IS c.source_id) AS active "
                "FROM camera_calibrations c LEFT JOIN video_sources s ON s.id = c.source_id "
                "ORDER BY c.id DESC").fetchall()

    # ------------------------------------------------------------------
    # Nguồn video/camera
    # ------------------------------------------------------------------

    def register_source(self, uri: str, source_type: str, name: Optional[str] = None) -> int:
        """Thêm nguồn nếu chưa có (theo uri), cập nhật thời điểm dùng gần nhất. Trả về id."""
        uri = normalize_source(uri)
        ts = now_str()
        with closing(self._connect()) as con, con:
            row = con.execute("SELECT id FROM video_sources WHERE uri = ?", (uri,)).fetchone()
            if row:
                con.execute("UPDATE video_sources SET last_used_at = ? WHERE id = ?", (ts, row["id"]))
                return int(row["id"])
            cur = con.execute(
                "INSERT INTO video_sources(name, source_type, uri, created_at, last_used_at) "
                "VALUES (?, ?, ?, ?, ?)", (name or uri, source_type, uri, ts, ts))
            return int(cur.lastrowid)

    def add_source(self, name: str, source_type: str, uri: str, description: str = "") -> int:
        uri = normalize_source(uri)
        with closing(self._connect()) as con, con:
            cur = con.execute(
                "INSERT INTO video_sources(name, source_type, uri, description, created_at) VALUES (?, ?, ?, ?, ?)",
                (name, source_type, uri, description, now_str()))
            return int(cur.lastrowid)

    def update_source(self, source_id: int, name: str, source_type: str, uri: str, description: str) -> None:
        uri = normalize_source(uri)
        with closing(self._connect()) as con, con:
            con.execute("UPDATE video_sources SET name = ?, source_type = ?, uri = ?, description = ? "
                        "WHERE id = ?", (name, source_type, uri, description, source_id))

    def delete_source(self, source_id: int) -> None:
        """Xóa nguồn khỏi danh sách; các phiên cũ vẫn giữ (source_id -> NULL)."""
        with closing(self._connect()) as con, con:
            con.execute("DELETE FROM video_sources WHERE id = ?", (source_id,))

    def list_sources(self) -> List[sqlite3.Row]:
        with closing(self._connect()) as con:
            return con.execute(
                "SELECT s.*, (SELECT COUNT(*) FROM monitoring_sessions m WHERE m.source_id = s.id) AS sessions, "
                "(SELECT COUNT(*) FROM camera_calibrations c WHERE c.source_id = s.id) AS calibrations "
                "FROM video_sources s ORDER BY COALESCE(s.last_used_at, s.created_at) DESC").fetchall()

    def get_source(self, uri: str) -> Optional[sqlite3.Row]:
        with closing(self._connect()) as con:
            return con.execute("SELECT * FROM video_sources WHERE uri = ?", (normalize_source(uri),)).fetchone()

    # ------------------------------------------------------------------
    # Cấu hình
    # ------------------------------------------------------------------

    def load_config(self) -> Optional[dict]:
        """Trả về dict cấu hình, hoặc None nếu CSDL chưa có cấu hình."""
        with closing(self._connect()) as con:
            rows = con.execute("SELECT section, key, value FROM system_config").fetchall()
        return _unflatten_config(rows) if rows else None

    def save_config(self, cfg: dict, reason: str = "") -> bool:
        """
        Ghi cấu hình hiện hành. Chỉ thêm vào lịch sử khi cấu hình thực sự thay đổi.
        Trả về True nếu có thay đổi.
        """
        snapshot = json.dumps(cfg, ensure_ascii=False, sort_keys=True)
        ts = now_str()
        with closing(self._connect()) as con, con:
            last = con.execute(
                "SELECT config_json FROM config_history ORDER BY id DESC LIMIT 1").fetchone()
            changed = last is None or last["config_json"] != snapshot
            con.executemany(
                "INSERT INTO system_config(section, key, value, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(section, key) DO UPDATE SET value = excluded.value, "
                "updated_at = CASE WHEN value = excluded.value THEN updated_at ELSE excluded.updated_at END",
                [(s, k, v, ts) for s, k, v in _flatten_config(cfg)])
            if changed:
                con.execute("INSERT INTO config_history(changed_at, reason, config_json) VALUES (?, ?, ?)",
                            (ts, reason or "Cập nhật cấu hình", snapshot))
        return changed

    def config_history(self, limit: int = 200) -> List[sqlite3.Row]:
        with closing(self._connect()) as con:
            return con.execute("SELECT * FROM config_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

    # ------------------------------------------------------------------
    # Phiên giám sát
    # ------------------------------------------------------------------

    def start_session(self, source: str, source_type: str, model_weights: str, device: str,
                      frame_width: int, frame_height: int, config: dict,
                      source_id: Optional[int] = None) -> int:
        with closing(self._connect()) as con, con:
            cur = con.execute(
                "INSERT INTO monitoring_sessions(started_at, source_id, source, source_type, model_weights, "
                "device, frame_width, frame_height, config_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (now_str(), source_id, source, source_type, model_weights, device, frame_width, frame_height,
                 json.dumps(config, ensure_ascii=False)))
            return int(cur.lastrowid)

    def end_session(self, session_id: int, frames: int, avg_fps: Optional[float]) -> None:
        with closing(self._connect()) as con, con:
            con.execute("UPDATE monitoring_sessions SET ended_at = ?, frames_processed = ?, avg_fps = ? "
                        "WHERE id = ?", (now_str(), frames, avg_fps, session_id))

    def list_sessions(self) -> List[sqlite3.Row]:
        with closing(self._connect()) as con:
            return con.execute("SELECT * FROM v_session_summary ORDER BY id DESC").fetchall()

    def delete_session(self, session_id: int) -> List[str]:
        """Xóa phiên (và các vi phạm - ON DELETE CASCADE). Trả về đường dẫn ảnh cần xóa."""
        with closing(self._connect()) as con, con:
            snaps = [r[0] for r in con.execute(
                "SELECT snapshot_path FROM violations WHERE session_id = ? AND snapshot_path IS NOT NULL",
                (session_id,))]
            con.execute("DELETE FROM monitoring_sessions WHERE id = ?", (session_id,))
        return snaps

    # ------------------------------------------------------------------
    # Vi phạm
    # ------------------------------------------------------------------

    def insert_violation(self, data: dict) -> int:
        cols = [k for k in VIOLATION_FIELDS if k in data]
        with closing(self._connect()) as con, con:
            cur = con.execute(
                f"INSERT INTO violations({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                [data[k] for k in cols])
            return int(cur.lastrowid)

    def update_violation(self, violation_id: int, fields: dict) -> None:
        cols = [k for k in fields if k in VIOLATION_FIELDS]
        if not cols:
            return
        with closing(self._connect()) as con, con:
            con.execute(f"UPDATE violations SET {', '.join(f'{c} = ?' for c in cols)} WHERE id = ?",
                        [fields[c] for c in cols] + [violation_id])

    def list_violations(self, session_id: Optional[int] = None, level: Optional[str] = None,
                        vehicle_class: Optional[str] = None, date_from: Optional[str] = None,
                        date_to: Optional[str] = None, limit: int = 5000) -> List[sqlite3.Row]:
        """
        Tìm kiếm nhật ký vi phạm. date_from/date_to dạng 'YYYY-MM-DD' (bao gồm cả 2 đầu).
        vehicle_class có thể là 1 lớp hoặc nhiều lớp phân cách dấu phẩy (vd: 'bus,Jeepney').
        """
        sql, args = "SELECT * FROM violations WHERE 1 = 1", []
        if session_id is not None:
            sql += " AND session_id = ?"
            args.append(session_id)
        if level:
            sql += " AND level = ?"
            args.append(level)
        if vehicle_class:
            classes = vehicle_class.split(",")
            sql += f" AND vehicle_class IN ({', '.join('?' * len(classes))})"
            args += classes
        if date_from:
            sql += " AND started_at >= ?"
            args.append(f"{date_from} 00:00:00")
        if date_to:
            sql += " AND started_at <= ?"
            args.append(f"{date_to} 23:59:59")
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with closing(self._connect()) as con:
            return con.execute(sql, args).fetchall()

    def delete_violations(self, ids: List[int]) -> List[str]:
        """Xóa các vi phạm. Trả về đường dẫn ảnh bằng chứng cần xóa."""
        if not ids:
            return []
        marks = ", ".join("?" * len(ids))
        with closing(self._connect()) as con, con:
            snaps = [r[0] for r in con.execute(
                f"SELECT snapshot_path FROM violations WHERE id IN ({marks}) AND snapshot_path IS NOT NULL", ids)]
            con.execute(f"DELETE FROM violations WHERE id IN ({marks})", ids)
        return snaps

    def stats(self) -> dict:
        with closing(self._connect()) as con:
            r = con.execute(
                "SELECT (SELECT COUNT(*) FROM monitoring_sessions) AS sessions, COUNT(*) AS total, "
                "COALESCE(SUM(level = 'danger'), 0) AS danger, COALESCE(SUM(level = 'warning'), 0) AS warning, "
                "MIN(min_distance_m) AS closest FROM violations").fetchone()
        return dict(r)
