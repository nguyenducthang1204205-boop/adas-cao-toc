"""
Sinh icon launcher Android + iOS từ ảnh vector đã render (AppMarkPainter, lib/ui/components.dart).

    cd mobile/app && flutter test test_preview     # -> build/preview/icon_*_1024.png
    python mobile/make_icons.py

Android: icon thích ứng (nền gradient + tiền cảnh trong vùng an toàn) cho Android 8+, kèm lớp đơn sắc cho
icon theo chủ đề (Android 13+) và icon PNG bo góc cho máy cũ. iOS: đủ kích thước AppIcon, không kênh alpha.
"""

from pathlib import Path

from PIL import Image, ImageDraw

APP = Path(__file__).resolve().parent / "app"
SRC = APP / "build" / "preview"
RES = APP / "android" / "app" / "src" / "main" / "res"
IOS = APP / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset"

DENSITY = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}


def rounded(img: Image.Image, radius_ratio: float = 0.22) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=img.width * radius_ratio, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def main():
    full = Image.open(SRC / "icon_1024.png").convert("RGBA")
    bg = Image.open(SRC / "icon_bg_1024.png").convert("RGBA")
    fg = Image.open(SRC / "icon_fg_1024.png").convert("RGBA")
    for name, k in DENSITY.items():
        d = RES / f"mipmap-{name}"
        d.mkdir(parents=True, exist_ok=True)
        legacy = round(48 * k)
        rounded(full.resize((legacy, legacy), Image.LANCZOS)).save(d / "ic_launcher.png")
        layer = round(108 * k)
        bg.resize((layer, layer), Image.LANCZOS).convert("RGB").save(d / "ic_launcher_background.png")
        fgl = fg.resize((layer, layer), Image.LANCZOS)
        fgl.save(d / "ic_launcher_foreground.png")
        # đơn sắc (icon theo chủ đề Android 13+): hình dạng tiền cảnh, màu trắng
        mono = Image.new("RGBA", fgl.size, (255, 255, 255, 0))
        mono.putalpha(fgl.getchannel("A"))
        mono.save(d / "ic_launcher_monochrome.png")
    any26 = RES / "mipmap-anydpi-v26"
    any26.mkdir(exist_ok=True)
    (any26 / "ic_launcher.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <background android:drawable="@mipmap/ic_launcher_background"/>\n'
        '    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>\n'
        '    <monochrome android:drawable="@mipmap/ic_launcher_monochrome"/>\n'
        '</adaptive-icon>\n', encoding="utf-8")
    # iOS: tên file theo Contents.json có sẵn của Flutter
    for f in IOS.glob("Icon-App-*.png"):
        size_part = f.stem.split("-")[-1]                 # vd "83.5x83.5@2x"
        base, scale = size_part.split("@")
        px = round(float(base.split("x")[0]) * int(scale.rstrip("x")))
        full.resize((px, px), Image.LANCZOS).convert("RGB").save(f)  # App Store không nhận kênh alpha
    print("Đã tạo icon Android (adaptive + legacy) và iOS")


if __name__ == "__main__":
    main()
