# -*- coding: utf-8 -*-
"""
Sinh toàn bộ sơ đồ vào docs/so_do/ (SVG + PNG).

    python docs/so_do/nguon/build.py [tên_sơ_đồ ...]

- Use case, hoạt động, BPMN: vẽ bằng svgdraw.py (Python + Pillow), PNG chụp bằng Microsoft Edge headless.
- Các sơ đồ còn lại: file Mermaid trong nguon/mermaid/*.mmd, dựng bằng mermaid-cli (mmdc) với Edge.
  Đặt biến môi trường MMDC trỏ tới mmdc (vd: node_modules/.bin/mmdc); thiếu thì bỏ qua phần Mermaid.
  Có thể dán nội dung file .mmd vào https://mermaid.live để sửa trực tuyến.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
sys.path.insert(0, str(HERE))

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
SCALE = 2

MERMAID_CONFIG = {
    "theme": "base",
    "look": "classic",
    "themeVariables": {
        "fontFamily": "Times New Roman", "fontSize": "16px",
        "primaryColor": "#f4f8fd", "primaryBorderColor": "#1f1f1f", "primaryTextColor": "#000000",
        "secondaryColor": "#eef2f7", "tertiaryColor": "#ffffff", "lineColor": "#1f1f1f",
        "clusterBkg": "#fafbfc", "clusterBorder": "#7a7a7a", "edgeLabelBackground": "#ffffff",
        "actorBkg": "#f4f8fd", "actorBorder": "#1f1f1f", "noteBkgColor": "#fffbe6", "noteBorderColor": "#9a8a3a",
        "activationBkgColor": "#e6eef8", "signalColor": "#1f1f1f", "labelBoxBkgColor": "#eef2f7",
    },
    "flowchart": {"htmlLabels": False, "wrappingWidth": 400, "curve": "basis", "padding": 12, "nodeSpacing": 40, "rankSpacing": 48},
    "sequence": {"mirrorActors": False, "actorMargin": 40, "messageFontSize": 15, "noteFontSize": 14,
                 "actorFontSize": 15, "wrap": False, "width": 150, "bottomMarginAdj": 10},
    "class": {"htmlLabels": True},
    "er": {"fontSize": 14, "layoutDirection": "TB"},
    "state": {},
}


def svg_to_png(svg: Path, png: Path) -> None:
    head = svg.read_text(encoding="utf-8")[:400]
    w = float(re.search(r'width="([\d.]+)"', head).group(1))
    h = float(re.search(r'height="([\d.]+)"', head).group(1))
    with tempfile.TemporaryDirectory() as td:
        tmp_svg = Path(td) / "d.svg"
        shutil.copy(svg, tmp_svg)
        tmp_png = Path(td) / "d.png"
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--disable-lcd-text",
                        f"--force-device-scale-factor={SCALE}", f"--window-size={int(w)},{int(h)}",
                        f"--screenshot={tmp_png}", tmp_svg.as_uri()],
                       check=True, capture_output=True, timeout=120)
        shutil.copy(tmp_png, png)


def build_python(only):
    import activity
    import bpmn
    import usecase
    for mod in (bpmn, usecase, activity):
        for name, fn in mod.DIAGRAMS.items():
            if only and name not in only:
                continue
            svg = OUT / f"{name}.svg"
            svg.write_text(fn().draw(), encoding="utf-8")
            svg_to_png(svg, OUT / f"{name}.png")
            print("✔", name)


def build_mermaid(only):
    mmdc = os.environ.get("MMDC")
    if not mmdc:
        print("Bỏ qua Mermaid (chưa đặt biến MMDC)")
        return
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "cfg.json").write_text(json.dumps(MERMAID_CONFIG), encoding="utf-8")
        (td / "pup.json").write_text(json.dumps({"executablePath": EDGE.replace("\\", "/"),
                                                 "args": ["--no-sandbox", "--disable-lcd-text"]}), encoding="utf-8")
        for src in sorted((HERE / "mermaid").glob("*.mmd")):
            if only and src.stem not in only:
                continue
            shutil.copy(src, td / "in.mmd")
            r = subprocess.run([mmdc, "-q", "-p", str(td / "pup.json"), "-c", str(td / "cfg.json"),
                                "-b", "white", "-i", str(td / "in.mmd"), "-o", str(td / "out.svg")],
                               capture_output=True, text=True, encoding="utf-8")
            if r.returncode != 0:
                print("✖", src.stem, r.stderr[-1500:])
                continue
            svg = _fix_svg_size((td / "out.svg").read_text(encoding="utf-8"))
            out = OUT / f"{src.stem}.svg"
            out.write_text(svg, encoding="utf-8")
            svg_to_png(out, OUT / f"{src.stem}.png")
            print("✔", src.stem)


def _fix_svg_size(svg: str) -> str:
    """mmdc ghi width="100%" + max-width: đặt kích thước thật theo viewBox để chụp PNG đủ độ phân giải."""
    vb = re.search(r'viewBox="([-\d.]+) ([-\d.]+) ([\d.]+) ([\d.]+)"', svg)
    x0, y0, w, h = (float(vb.group(i)) for i in range(1, 5))
    pad = 24   # mmdc đôi khi tính thiếu chiều cao (dòng cuối của sơ đồ tuần tự bị cắt)
    x0, y0, w, h = x0 - pad, y0 - pad, w + 2 * pad, h + 2 * pad + 30
    head_end = svg.index(">")
    head = svg[:head_end]
    head = head.replace(vb.group(0), f'viewBox="{x0:.1f} {y0:.1f} {w:.1f} {h:.1f}"', 1)
    head = re.sub(r'width="100%"', f'width="{w:.0f}" height="{h:.0f}"', head, count=1)
    head = re.sub(r'max-width:\s*[\d.]+px;?', "", head)
    return head + svg[head_end:]


if __name__ == "__main__":
    only = set(sys.argv[1:])
    build_python(only)
    build_mermaid(only)
