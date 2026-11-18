# -*- coding: utf-8 -*-
"""Xuất các file draw.io (drawio/*.drawio) ra PNG để chèn vào quyển đồ án.

    python nguon/xuat_png_drawio.py [tiền tố…]

Mỗi file được vẽ bằng chính bộ hiển thị của draw.io (viewer-static.min.js) trong Microsoft Edge
chạy ẩn (Playwright, kênh "msedge"), rồi chụp đúng vùng sơ đồ với tỉ lệ 2x.
Kết quả: drawio/png/<tên>.png
"""


import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "drawio"
OUT = SRC / "png"
VIEWER = "https://viewer.diagrams.net/js/viewer-static.min.js"


PAGE = ('<!doctype html><html><head><meta charset="utf-8"></head>'
        '<body style="margin:0;background:#ffffff"><div id="g"></div>'
        f'<script src="{VIEWER}"></script></body></html>')

# Dựng viewer mới cho mỗi sơ đồ ở tỉ lệ 1:1 (auto-fit tắt), tắt chế độ "lazy" của GraphViewer
RENDER = """(xml) => new Promise((res, rej) => {
  const old = document.getElementById('g');
  const el = document.createElement('div');
  el.id = 'g';
  el.style.width = '6000px';
  old.replaceWith(el);
  el.setAttribute('data-mxgraph', JSON.stringify({xml: xml, toolbar: '', lightbox: false, nav: false,
                                                  border: 16, highlight: 'none', zoom: 1,
                                                  'auto-fit': false, resize: true}));
  GraphViewer.lazy = false;
  GraphViewer.createViewerForElement(el, () => res(true));
  setTimeout(() => rej(new Error('viewer timeout')), 30000);
})"""


def main(prefixes):
    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted(f for f in SRC.glob("*.drawio") if not prefixes or any(f.name.startswith(p) for p in prefixes))
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(device_scale_factor=2, viewport={"width": 6200, "height": 3000})
        page.set_content(PAGE, wait_until="networkidle")
        page.wait_for_function("typeof GraphViewer !== 'undefined'", timeout=30000)
        for f in files:
            xml = re.search(r"<mxGraphModel.*</mxGraphModel>", f.read_text(encoding="utf-8"), re.S).group(0)
            page.evaluate(RENDER, xml)
            page.wait_for_timeout(300)
            svg = page.locator("#g svg").first
            out = OUT / (f.stem + ".png")
            svg.screenshot(path=str(out), omit_background=False)
            box = svg.bounding_box()
            print(f"{f.stem}: {int(box['width'])}×{int(box['height'])} px (×2)")
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1:])
