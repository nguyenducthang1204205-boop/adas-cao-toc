"""
Hệ thiết kế "Night Drive" dùng chung cho bản desktop và mobile (app Android: ui/theme/Theme.kt).

Đổi màu / chữ / biểu tượng ở đây thì sửa cả Theme.kt cho hai bản luôn giống nhau.
Nguyên tắc: nền OLED đen sâu, chữ trắng ngà; xanh / hổ phách / đỏ chỉ dành cho mức rủi ro và luôn đi
kèm chữ + biểu tượng; xanh dương thương hiệu chỉ cho điều khiển tương tác.
Tương phản WCAG đã đo: text 16,4:1, text_secondary 8,2:1, text_tertiary 5,0:1, accent 6,7:1,
danger 5,7:1 trên surface. Chữ trắng trên danger chỉ 3,3:1 -> nền đặc dùng danger_fill (4,8:1).

Module thuần Python (không Qt): gui/rendering và các widget cùng đọc.
"""

FONT_FAMILY = "Be Vietnam Pro"     # OFL, thiết kế cho tiếng Việt; thiếu glyph μ → ↔ ● ✓ ⚠ ↺ ▾
ICON_FAMILY = "Material Icons"     # cùng bộ biểu tượng với bản mobile (Icons.* của Flutter)

C = {
    # nền & bề mặt
    "bg": "#05070a",
    "surface": "#0f141b",
    "surface2": "#161d26",          # thẻ / ô nhập trên surface (surfaceRaised ở mobile)
    "hover": "#1e2733",
    "border": "#222b37",            # ≈ trắng 10 % trên surface
    "border_strong": "#323d4b",
    "glass": "#d60c1117",           # #AARRGGBB - cụm nổi trên video (84 % đục)
    "video_bg": "#05070a",
    # chữ
    "text": "#eef2f6",
    "muted": "#a3aebb",             # textSecondary
    "faint": "#7b8794",             # textTertiary - KHÔNG dùng trên video
    # thương hiệu / tương tác
    "accent": "#4c9eff",
    "accent_hover": "#6aafff",
    "accent_soft": "#1a2d44",       # accent 16 % trên surface
    "on_accent": "#04101f",
    # rủi ro
    "safe": "#2fd27a",
    "warning": "#ffb020",
    "danger": "#ff4d4f",
    "danger_fill": "#d92d20",
    "info": "#9aa8b8",
    "on_warning": "#1a1200",
}

# Mức cảnh báo -> (nền khối đặc, màu chữ, nhãn, câu ngắn, biểu tượng)
LEVEL_STYLE = {
    "safe": (C["safe"], C["on_accent"], "AN TOÀN", "Khoảng cách an toàn", "verified_rounded"),
    "warning": (C["warning"], C["on_warning"], "CẢNH BÁO", "Giữ khoảng cách", "error_outline_rounded"),
    "danger": (C["danger_fill"], "#ffffff", "NGUY HIỂM", "Giảm tốc ngay", "warning_rounded"),
    "idle": (C["surface2"], C["muted"], "CHƯA CHẠY", "", "pause_rounded"),
}

# Mã ký tự Material Icons (bin/cache/artifacts/material_fonts/codepoints của Flutter SDK)
ICONS = {
    "warning_rounded": 0xF02A1, "error_outline_rounded": 0xF712, "verified_rounded": 0xF026E,
    "pause_rounded": 0xF0056, "play_arrow_rounded": 0xF00A0, "stop_rounded": 0xF01DC,
    "directions_car_outlined": 0xEFC6, "speed_outlined": 0xF3C3, "social_distance_outlined": 0xF3B4,
    "wb_sunny_outlined": 0xF4BC, "water_drop_outlined": 0xF0695, "thunderstorm_outlined": 0xF071B,
    "foggy": 0xF0505, "oil_barrel_outlined": 0xF0707, "dark_mode_outlined": 0xEF9F,
    "local_shipping_outlined": 0xF18E, "local_cafe_outlined": 0xF175,
    "straighten_outlined": 0xF3F1, "tune_outlined": 0xF466, "settings_outlined": 0xF36E,
    "volume_up_outlined": 0xF4A8, "volume_off_outlined": 0xF4A7, "folder_open_outlined": 0xF090,
    "videocam_outlined": 0xF48C, "image_outlined": 0xF120, "folder_copy_outlined": 0xF05FF,
    "history_outlined": 0xF102, "smart_toy_outlined": 0xF3A8, "receipt_long_outlined": 0xF2EF,
    "map_outlined": 0xF1AE, "close_rounded": 0xF647, "restart_alt_rounded": 0xF0106,
    "check_circle_rounded": 0xF635, "check_rounded": 0xF636, "add_rounded": 0xF537,
    "edit_outlined": 0xF00D, "delete_outline_rounded": 0xF696, "cable_outlined": 0xEF0D,
    "search_rounded": 0xF013D, "photo_camera_outlined": 0xF29B, "info_outline_rounded": 0xF815,
    "auto_fix_high_outlined": 0xEEAB, "cell_tower_outlined": 0xF05C7, "movie_outlined": 0xF1F5,
    "download_outlined": 0xEFF2, "chevron_right_rounded": 0xF63B, "expand_more_rounded": 0xF720,
    "error_rounded": 0xF713, "circle_rounded": 0xF640, "fiber_manual_record_outlined": 0xF054,
    "notifications_active_outlined": 0xF234, "visibility_outlined": 0xF4A1,
    "record_voice_over_outlined": 0xF2F3, "shield_outlined": 0xF379, "memory_outlined": 0xF1C1,
    "table_chart_outlined": 0xF41D, "timer_outlined": 0xF44A, "description_outlined": 0xEFAE,
    "insights_outlined": 0xF132, "link_rounded": 0xF85A, "arrow_back_rounded": 0xF572,
}

# Điều kiện đường -> biểu tượng (giống conditionIcon / modifierIcon của mobile)
CONDITION_ICONS = {
    "dry": "wb_sunny_outlined", "wet": "water_drop_outlined", "heavy_rain": "thunderstorm_outlined",
    "fog": "foggy", "slippery": "oil_barrel_outlined",
    "night": "dark_mode_outlined", "heavy_vehicle": "local_shipping_outlined", "tired": "local_cafe_outlined",
}


def icon_char(name: str) -> str:
    return chr(ICONS[name])
