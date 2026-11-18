# -*- coding: utf-8 -*-
"""
Bộ vẽ SVG cho các sơ đồ trong báo cáo: use case, hoạt động có làn (swimlane) và BPMN.

Không cần Java/Graphviz: đo chữ bằng Pillow (font Times New Roman của Windows), xếp nút theo lưới
(làn × hàng/cột) do người viết chỉ định, nối cạnh bằng đường gấp khúc vuông góc.
Mũi tên vẽ bằng đa giác (không dùng <marker>) để Word hiển thị đúng khi chèn file SVG.
"""
import math
from xml.sax.saxutils import escape

from PIL import ImageFont

FONT_FAMILY = "Times New Roman"
FONT_FILES = {(False, False): "C:/Windows/Fonts/times.ttf", (True, False): "C:/Windows/Fonts/timesbd.ttf",
              (False, True): "C:/Windows/Fonts/timesi.ttf", (True, True): "C:/Windows/Fonts/timesbi.ttf"}
_fonts = {}

STROKE = "#1f1f1f"
FILL = "#ffffff"
LANE_HEAD = "#eef2f7"
ACT_FILL = "#f4f8fd"
NOTE_FILL = "#fffbe6"


def _font(size, bold=False, italic=False):
    k = (size, bold, italic)
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(FONT_FILES[(bold, italic)], size)
    return _fonts[k]


def text_w(s, size, bold=False, italic=False):
    return _font(size, bold, italic).getlength(s)


def wrap(text, maxw, size, bold=False):
    out = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            cand = (line + " " + word).strip()
            if line and text_w(cand, size, bold) > maxw:
                out.append(line)
                line = word
            else:
                line = cand
        out.append(line)
    return out


def block_size(lines, size, bold=False):
    return max(text_w(s, size, bold) for s in lines), len(lines) * size * 1.22


class Canvas:
    def __init__(self):
        self.el = []

    def add(self, s):
        self.el.append(s)

    def text(self, x, y, lines, size=14, anchor="middle", bold=False, italic=False, fill="#000",
             bg=False, rotate=None):
        if isinstance(lines, str):
            lines = [lines]
        lh = size * 1.22
        y0 = y - (len(lines) - 1) * lh / 2
        if bg:
            w, h = block_size(lines, size, bold)
            bx = {"middle": x - w / 2, "start": x, "end": x - w}[anchor]
            self.add(f'<rect x="{bx - 3:.1f}" y="{y - h / 2 - 1:.1f}" width="{w + 6:.1f}" height="{h + 2:.1f}" '
                     f'fill="#fff" stroke="none"/>')
        style = f'font-family="{FONT_FAMILY}" font-size="{size}" text-anchor="{anchor}" fill="{fill}"'
        if bold:
            style += ' font-weight="bold"'
        if italic:
            style += ' font-style="italic"'
        tr = f' transform="rotate({rotate} {x:.1f} {y:.1f})"' if rotate else ""
        for i, s in enumerate(lines):
            yy = y0 + i * lh + size * 0.34
            self.add(f'<text x="{x:.1f}" y="{yy:.1f}" {style}{tr}>{escape(s)}</text>')

    def rect(self, x, y, w, h, rx=0, fill=FILL, stroke=STROKE, sw=1.3, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def ellipse(self, cx, cy, rx, ry, fill=FILL, stroke=STROKE, sw=1.3):
        self.add(f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{sw}"/>')

    def line(self, x1, y1, x2, y2, sw=1.3, dash=None, stroke=STROKE):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" '
                 f'stroke-width="{sw}"{d}/>')

    def poly(self, pts, fill="none", stroke=STROKE, sw=1.3, dash=None, closed=False):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        tag = "polygon" if closed else "polyline"
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        self.add(f'<{tag} points="{p}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
                 f'stroke-linejoin="round"{d}/>')

    def arrowhead(self, p_from, p_to, kind="filled", size=10):
        dx, dy = p_to[0] - p_from[0], p_to[1] - p_from[1]
        L = math.hypot(dx, dy) or 1
        ux, uy = dx / L, dy / L
        px, py = -uy, ux
        tip = p_to
        base = (tip[0] - ux * size, tip[1] - uy * size)
        half = size * (0.45 if kind != "triangle" else 0.6)
        a = (base[0] + px * half, base[1] + py * half)
        b = (base[0] - px * half, base[1] - py * half)
        if kind == "filled":
            self.poly([a, tip, b], fill=STROKE, closed=True, sw=1)
        elif kind == "open":
            self.poly([a, tip, b], sw=1.3)
        elif kind == "triangle":
            self.poly([a, tip, b], fill="#fff", closed=True, sw=1.3)

    def svg(self, w, h):
        body = "\n".join(self.el)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
                f'viewBox="0 0 {w:.0f} {h:.0f}">\n<rect width="100%" height="100%" fill="#fff"/>\n{body}\n</svg>\n')


# ======================================================================
# Sơ đồ hoạt động có làn (orient="v") và BPMN (orient="h")
# ======================================================================

class N:
    """Nút: kind, lane (chỉ số làn), pos (hàng nếu dọc / cột nếu ngang), dc (lệch ngang trong làn, px)."""

    def __init__(self, id, kind, lane, pos, text="", dc=0, w=None, label=None, lab_pos="right"):
        self.id, self.kind, self.lane, self.pos, self.text, self.dc, self.w = id, kind, lane, pos, text, dc, w
        self.label = label   # nhãn ngoài (cổng BPMN, kho dữ liệu)
        self.lab_pos = lab_pos   # kho dữ liệu: "right" | "below"


class E:
    """Cạnh: route = auto | straight | z | side | vh | hv | loop | looptop; s = phía (+1/-1)."""

    def __init__(self, a, b, label=None, route="auto", s=None, off=28, mid=None, style="flow", lab_end=False):
        self.a, self.b, self.label, self.route, self.s, self.off, self.mid = a, b, label, route, s, off, mid
        self.style, self.lab_end = style, lab_end


class Flow:
    FS = 14          # cỡ chữ nút
    LS = 13          # cỡ chữ nhãn cạnh

    def __init__(self, orient, lanes, nodes, edges, lane_size=None, gap=38, act_w=190, task_w=118,
                 pool=None, head=34, pad=22):
        self.o = orient
        self.lanes = lanes
        self.nodes = {n.id: n for n in nodes}
        self.order = nodes
        self.edges = edges
        self.gap = gap
        self.act_w, self.task_w = act_w, task_w
        self.pool = pool
        self.head = head
        self.pad = pad
        for n in nodes:
            self._measure(n)
        self._layout(lane_size)

    # ------------------------------------------------------------------ kích thước nút
    def _measure(self, n):
        fs = self.FS
        k = n.kind
        n.lines = []
        if k in ("act", "task", "sub"):
            maxw = n.w or (self.act_w if k == "act" else self.task_w)
            n.lines = wrap(n.text, maxw, fs)
            tw, th = block_size(n.lines, fs)
            if k == "act":
                n.W, n.H = max(tw + 26, 90), max(th + 16, 38)
            else:
                n.W, n.H = max(tw + 20, (n.w or self.task_w) + 20), max(th + 22, 62)
        elif k == "decision":
            if n.text:
                n.lines = wrap(n.text, n.w or 120, fs)
                tw, th = block_size(n.lines, fs)
                H = max(2 * th + 16, 46)
                n.W, n.H = max(tw / (1 - th / H) + 18, 64), H
            else:
                n.W = n.H = 34
        elif k == "merge":
            n.W = n.H = 30
        elif k == "start":
            n.W = n.H = 22
        elif k == "end":
            n.W = n.H = 26
        elif k == "bar":
            L = n.w or 150
            n.W, n.H = (L, 7) if self.o == "v" else (7, L)
        elif k in ("bstart", "bend", "binter"):
            n.W = n.H = 36
        elif k in ("xor", "and"):
            n.W = n.H = 46
        elif k == "store":
            n.W, n.H = 62, 52
        elif k == "doc":
            n.W, n.H = 44, 54
        elif k == "note":
            n.lines = wrap(n.text, n.w or 170, 13)
            tw, th = block_size(n.lines, 13)
            n.W, n.H = tw + 22, th + 14
        else:
            raise ValueError(k)
        # Nhãn ngoài (cổng / sự kiện / kho dữ liệu) chiếm thêm chỗ theo chiều dọc
        lw = 95 if k in ("bstart", "bend", "binter", "xor", "and") else 130
        n.lab_lines = wrap(n.label, lw, 13) if n.label else []

    # ------------------------------------------------------------------ xếp lưới
    def _layout(self, lane_size):
        nl = len(self.lanes)
        if self.o == "v":
            self.lane_w = lane_size or [300] * nl
            npos = max(n.pos for n in self.order) + 1
            row_h = [0] * npos
            for n in self.order:
                row_h[n.pos] = max(row_h[n.pos], n.H)
            y = self.head + self.pad + (self.head if self.pool else 0)
            self.pos_c = []
            for r in range(npos):
                h = row_h[r] or 20
                self.pos_c.append(y + h / 2)
                y += h + self.gap
            self.H = y - self.gap + self.pad + 6
            x = 10
            self.lane_x = []
            for w in self.lane_w:
                self.lane_x.append(x)
                x += w
            self.W = x + 10
            for n in self.order:
                n.cx = self.lane_x[n.lane] + self.lane_w[n.lane] / 2 + n.dc
                n.cy = self.pos_c[n.pos]
        else:
            strip = self.head + (self.head if self.pool else 0)
            npos = max(n.pos for n in self.order) + 1
            col_w = [0] * npos
            for n in self.order:
                col_w[n.pos] = max(col_w[n.pos], n.W)
            x = 10 + strip + self.pad
            self.pos_c = []
            pre = [0] * npos   # chừa chỗ cho nhãn đặt ở góc dưới-trái của cổng
            for n in self.order:
                if n.kind in ("xor", "and") and n.lab_lines:
                    pre[n.pos] = max(pre[n.pos], max(text_w(t, 13) for t in n.lab_lines) - 10)
            for c in range(npos):
                w = col_w[c] or 20
                x += pre[c]
                self.pos_c.append(x + w / 2)
                x += w + self.gap
            self.W = x - self.gap + self.pad + 30
            self.lane_h = lane_size or [150] * nl
            y = 10
            self.lane_y = []
            for h in self.lane_h:
                self.lane_y.append(y)
                y += h
            self.H = y + 10
            for n in self.order:
                n.cx = self.pos_c[n.pos]
                n.cy = self.lane_y[n.lane] + self.lane_h[n.lane] / 2 + n.dc

    # ------------------------------------------------------------------ toạ độ trừu tượng (m: dọc dòng chảy, c: ngang)
    def _mc(self, n):
        if self.o == "v":
            return n.cy, n.cx, n.H / 2, n.W / 2
        return n.cx, n.cy, n.W / 2, n.H / 2

    def _xy(self, p):
        m, c = p
        return (c, m) if self.o == "v" else (m, c)

    def _route(self, e):
        a, b = self.nodes[e.a], self.nodes[e.b]
        am, ac, ahm, ahc = self._mc(a)
        bm, bc, bhm, bhc = self._mc(b)
        out_main = (am + ahm, ac)
        in_main = (bm - bhm, bc)
        if a.kind == "bar":
            out_main = (am + ahm, min(max(bc, ac - ahc + 8), ac + ahc - 8))
        if b.kind == "bar":
            in_main = (bm - bhm, min(max(ac, bc - bhc + 8), bc + bhc - 8))

        def side(n_m, n_c, hc, s):
            return (n_m, n_c + s * hc)

        r = e.route
        if r == "auto":
            if b.pos > a.pos:
                if abs(bc - ac) < 1 or a.kind == "bar" or b.kind == "bar":
                    r = "straight"
                elif b.kind == "merge":
                    r = "vh"
                elif a.kind in ("decision", "xor", "and"):
                    r = "side"
                else:
                    r = "z"
            elif b.pos == a.pos:
                r = "same"
            else:
                r = "loop"
        e._r = r
        sgn = e.s if e.s is not None else (1 if bc >= ac else -1)
        if r == "straight":
            pts = [out_main, (in_main[0], out_main[1])]
        elif r == "same":
            s = 1 if bc > ac else -1
            pts = [side(am, ac, ahc, s), side(bm, bc, bhc, -s)]
        elif r == "z":
            mid = e.mid if e.mid is not None else in_main[0] - 15
            if self.o == "h" and e.mid is None:
                mid = in_main[0] - 15
            pts = [out_main, (mid, ac), (mid, bc), in_main]
        elif r == "side":     # ra cạnh bên của nút nguồn, rẽ vào đỉnh nút đích
            pts = [side(am, ac, ahc, sgn), (am, bc), in_main]
        elif r == "vh":       # đi theo dòng chảy tới ngang nút đích, rẽ vào cạnh bên
            s = 1 if ac > bc else -1
            pts = [out_main, (bm, ac), side(bm, bc, bhc, s)]
        elif r == "hv_side":  # ra cạnh bên nút nguồn, đi tới ngang nút đích, vào cạnh bên nút đích
            s = sgn
            c_out = (max if s > 0 else min)(ac + s * ahc, bc + s * bhc) + s * e.off
            pts = [side(am, ac, ahc, s), (am, c_out), (bm, c_out), side(bm, bc, bhc, s)]
        elif r == "loop":     # quay ngược lên: ra cạnh bên, vòng ngoài, vào cạnh bên nút đích
            s = e.s if e.s is not None else 1
            c_out = (max if s > 0 else min)(ac + s * ahc, bc + s * bhc) + s * e.off
            pts = [side(am, ac, ahc, s), (am, c_out), (bm, c_out), side(bm, bc, bhc, s)]
        elif r == "looptop":  # quay ngược lên, vào đỉnh nút đích
            s = e.s if e.s is not None else 1
            c_out = (max if s > 0 else min)(ac + s * ahc, bc + s * bhc) + s * e.off
            top = bm - bhm - 16
            pts = [side(am, ac, ahc, s), (am, c_out), (top, c_out), (top, bc), in_main]
        elif r == "down_side":  # đi xuống từ đáy nút nguồn tới ngang nút đích rồi vào cạnh bên (vh với phía chọn)
            pts = [out_main, (bm, ac), side(bm, bc, bhc, -sgn)]
        else:
            raise ValueError(r)
        # bỏ điểm trùng
        clean = [pts[0]]
        for p in pts[1:]:
            if abs(p[0] - clean[-1][0]) > 0.5 or abs(p[1] - clean[-1][1]) > 0.5:
                clean.append(p)
        return [self._xy(p) for p in clean]

    # ------------------------------------------------------------------ vẽ
    def draw(self):
        cv = Canvas()
        self._draw_lanes(cv)
        for n in self.order:
            self._draw_node(cv, n)
        for e in self.edges:
            self._draw_edge(cv, e)
        return cv.svg(self.W, self.H)

    def _draw_lanes(self, cv):
        if self.o == "v":
            top, bot = 10, self.H - 6
            if self.pool:
                cv.rect(self.lane_x[0], top, self.W - 20, bot - top, fill="#fff", sw=1.4)
                cv.rect(self.lane_x[0], top, self.W - 20, self.head, fill=LANE_HEAD, sw=1.4)
                cv.text(self.W / 2, top + self.head / 2, self.pool, size=15, bold=True)
                top += self.head
            for i, name in enumerate(self.lanes):
                x, w = self.lane_x[i], self.lane_w[i]
                cv.rect(x, top, w, bot - top, fill="#fff", sw=1.2)
                cv.rect(x, top, w, self.head, fill=LANE_HEAD, sw=1.2)
                cv.text(x + w / 2, top + self.head / 2, name, size=15, bold=True)
        else:
            left = 10
            right = self.W - 10
            if self.pool:
                cv.rect(left, self.lane_y[0], right - left, self.H - 20, fill="#fff", sw=1.4)
                cv.rect(left, self.lane_y[0], self.head, self.H - 20, fill=LANE_HEAD, sw=1.4)
                cv.text(left + self.head / 2, self.lane_y[0] + (self.H - 20) / 2, self.pool, size=15, bold=True,
                        rotate=-90)
                left += self.head
            for i, name in enumerate(self.lanes):
                y, h = self.lane_y[i], self.lane_h[i]
                cv.rect(left, y, right - left, h, fill="#fff", sw=1.2)
                cv.rect(left, y, self.head, h, fill=LANE_HEAD, sw=1.2)
                cv.text(left + self.head / 2, y + h / 2, wrap(name, h - 16, 14, True), size=14, bold=True,
                        rotate=-90)

    def _draw_node(self, cv, n):
        x, y, W, H = n.cx, n.cy, n.W, n.H
        k = n.kind
        if k == "act":
            cv.rect(x - W / 2, y - H / 2, W, H, rx=12, fill=ACT_FILL)
            cv.text(x, y, n.lines, size=self.FS)
        elif k in ("task", "sub"):
            cv.rect(x - W / 2, y - H / 2, W, H, rx=9, fill=ACT_FILL)
            cv.text(x, y - (5 if k == "sub" else 0), n.lines, size=self.FS)
            if k == "sub":
                cv.rect(x - 7, y + H / 2 - 16, 14, 14, fill="#fff", sw=1)
                cv.line(x - 4, y + H / 2 - 9, x + 4, y + H / 2 - 9, sw=1)
                cv.line(x, y + H / 2 - 13, x, y + H / 2 - 5, sw=1)
        elif k in ("decision", "merge", "xor", "and"):
            cv.poly([(x, y - H / 2), (x + W / 2, y), (x, y + H / 2), (x - W / 2, y)], fill="#fff", closed=True,
                    sw=1.4)
            if n.lines:
                cv.text(x, y, n.lines, size=self.FS)
            if k == "xor":
                d = 9
                cv.line(x - d, y - d, x + d, y + d, sw=3)
                cv.line(x - d, y + d, x + d, y - d, sw=3)
            if k == "and":
                d = 11
                cv.line(x - d, y, x + d, y, sw=3)
                cv.line(x, y - d, x, y + d, sw=3)
        elif k == "start":
            cv.ellipse(x, y, 11, 11, fill=STROKE)
        elif k == "end":
            cv.ellipse(x, y, 13, 13, fill="#fff", sw=1.6)
            cv.ellipse(x, y, 8, 8, fill=STROKE)
        elif k == "bar":
            cv.rect(x - W / 2, y - H / 2, W, H, fill=STROKE, sw=1)
        elif k == "bstart":
            cv.ellipse(x, y, 18, 18, fill="#fff", sw=1.6)
        elif k == "bend":
            cv.ellipse(x, y, 18, 18, fill="#fff", sw=4)
        elif k == "binter":
            cv.ellipse(x, y, 18, 18, fill="#fff", sw=1.4)
            cv.ellipse(x, y, 14, 14, fill="#fff", sw=1.4)
        elif k == "store":
            rx, ry = W / 2, 8
            top, bot = y - H / 2 + ry, y + H / 2 - ry
            cv.add(f'<path d="M{x - rx:.1f},{top:.1f} L{x - rx:.1f},{bot:.1f} A{rx:.1f},{ry} 0 0 0 {x + rx:.1f},'
                   f'{bot:.1f} L{x + rx:.1f},{top:.1f}" fill="#fff" stroke="{STROKE}" stroke-width="1.3"/>')
            cv.ellipse(x, top, rx, ry, fill="#fff")
            cv.add(f'<path d="M{x - rx:.1f},{top + 7:.1f} A{rx:.1f},{ry} 0 0 0 {x + rx:.1f},{top + 7:.1f}" '
                   f'fill="none" stroke="{STROKE}" stroke-width="1"/>')
        elif k == "doc":
            f = 12
            cv.poly([(x - W / 2, y - H / 2), (x + W / 2 - f, y - H / 2), (x + W / 2, y - H / 2 + f),
                     (x + W / 2, y + H / 2), (x - W / 2, y + H / 2)], fill="#fff", closed=True)
            cv.poly([(x + W / 2 - f, y - H / 2), (x + W / 2 - f, y - H / 2 + f), (x + W / 2, y - H / 2 + f)])
        elif k == "note":
            f = 10
            cv.poly([(x - W / 2, y - H / 2), (x + W / 2 - f, y - H / 2), (x + W / 2, y - H / 2 + f),
                     (x + W / 2, y + H / 2), (x - W / 2, y + H / 2)], fill=NOTE_FILL, closed=True, sw=1)
            cv.text(x, y, n.lines, size=13)
        if n.lab_lines:
            lh = 13 * 1.22 * len(n.lab_lines)
            if k in ("store", "doc") and n.lab_pos == "below":
                cv.text(x, y + H / 2 + 6 + lh / 2, n.lab_lines, size=13)
            elif k in ("store", "doc"):   # bên phải: tránh đường liên kết dữ liệu dọc
                cv.text(x + W / 2 + 6, y + 4, n.lab_lines, size=13, anchor="start")
            elif k in ("bstart", "bend", "binter") and self.o == "v":   # bố cục dọc: bên phải sự kiện
                cv.text(x + W / 2 + 8, y, n.lab_lines, size=13, anchor="start")
            elif k in ("bstart", "bend", "binter"):   # phía trên sự kiện: tránh cạnh rẽ ngay sau sự kiện
                cv.text(x, y - H / 2 - 6 - lh / 2, n.lab_lines, size=13)
            elif k in ("xor", "and"):   # góc dưới-trái: tránh cạnh đi ra từ đỉnh / đáy cổng và cạnh vào
                cv.text(x - 12, y + H / 2 + lh / 2 - 2, n.lab_lines, size=13, anchor="end")
            else:
                cv.text(x, y - H / 2 - 6 - lh / 2, n.lab_lines, size=13)

    @staticmethod
    def _clip_box(n, tx, ty):
        dx, dy = tx - n.cx, ty - n.cy
        if dx == 0 and dy == 0:
            return n.cx, n.cy
        t = min(n.W / 2 / abs(dx) if dx else 1e9, n.H / 2 / abs(dy) if dy else 1e9)
        return n.cx + dx * t, n.cy + dy * t

    def _draw_edge(self, cv, e):
        if e.style in ("data", "assoc"):   # liên kết dữ liệu / chú thích: đường thẳng chấm nối hai nút
            a, b = self.nodes[e.a], self.nodes[e.b]
            p, q = self._clip_box(a, b.cx, b.cy), self._clip_box(b, a.cx, a.cy)
            cv.line(*p, *q, dash="3,4", sw=1.3)
            if e.style == "data":
                cv.arrowhead(p, q, "open", 10)
            return
        pts = self._route(e)
        dash = {"flow": None, "data": "3,4", "msg": "7,5"}[e.style]
        cv.poly(pts, dash=dash, sw=1.3)
        cv.arrowhead(pts[-2], pts[-1], "filled" if e.style == "flow" else "open")
        if e.label:
            (x0, y0), (x1, y1) = (pts[-2], pts[-1]) if e.lab_end else (pts[0], pts[1])
            if e._r == "same" and abs(y1 - y0) < 1:   # cạnh ngắn cùng hàng: nhãn ở giữa, phía trên
                cv.text((x0 + x1) / 2, y0 - 11, e.label, size=self.LS, bg=True)
            elif abs(x1 - x0) < 1:     # đoạn dọc
                d = 1 if y1 > y0 else -1
                ly = (y1 - d * 16) if e.lab_end else (y0 + d * 15)
                cv.text(x0 + 6, ly, e.label, size=self.LS, anchor="start", bg=True, italic=False)
            else:
                d = 1 if x1 > x0 else -1
                lx = (x1 - d * 10) if e.lab_end else (x0 + d * 6)
                anchor = ("end" if d > 0 else "start") if e.lab_end else ("start" if d > 0 else "end")
                cv.text(lx, y0 - 10, e.label, size=self.LS, anchor=anchor, bg=True)


# ======================================================================
# Sơ đồ use case
# ======================================================================

class UseCaseDiagram:
    FS = 14

    def __init__(self, W, H, boundary, actors, ucs, links):
        """
        boundary: (x, y, w, h, tiêu đề)
        actors:   [(id, x, y, tên)]
        ucs:      [(id, x, y, chữ)]  hoặc (id, x, y, chữ, bề rộng tối đa)
        links:    [(a, b, kiểu)]   kiểu: assoc | include (a→b) | extend (a→b) | gen (a→b)
        """
        self.W, self.H, self.boundary = W, H, boundary
        self.shapes = {}
        self.actors = actors
        self.ucs = []
        for u in ucs:
            uid, x, y, text = u[:4]
            maxw = u[4] if len(u) > 4 else 170
            lines = wrap(text, maxw, self.FS)
            tw, th = block_size(lines, self.FS)
            rx, ry = max(tw / 2 + 28, 78), max(th / 2 + 15, 26)
            self.ucs.append((uid, x, y, lines, rx, ry))
            self.shapes[uid] = ("e", x, y, rx, ry)
        for aid, x, y, name in actors:
            self.shapes[aid] = ("a", x, y, 30, 48)
        self.links = links

    def _clip(self, sid, tx, ty):
        kind, x, y, rx, ry = self.shapes[sid]
        dx, dy = tx - x, ty - y
        if dx == 0 and dy == 0:
            return x, y
        if kind == "a":   # hộp chữ nhật quanh hình người
            t = min(rx / abs(dx) if dx else 1e9, ry / abs(dy) if dy else 1e9)
            return x + dx * t, y + dy * t
        t = 1 / math.sqrt((dx / rx) ** 2 + (dy / ry) ** 2)
        return x + dx * t, y + dy * t

    def draw(self):
        cv = Canvas()
        bx, by, bw, bh, title = self.boundary
        cv.rect(bx, by, bw, bh, fill="#fff", sw=1.4)
        cv.text(bx + bw / 2, by + 18, title, size=15, bold=True)
        for a, b, kind in self.links:
            _, ax, ay, _, _ = self.shapes[a]
            _, bx2, by2, _, _ = self.shapes[b]
            p = self._clip(a, bx2, by2)
            q = self._clip(b, ax, ay)
            if kind == "assoc":
                cv.line(*p, *q)
            elif kind in ("include", "extend"):
                cv.line(*p, *q, dash="7,5")
                cv.arrowhead(p, q, "open", 12)
                mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
                cv.text(mx, my, f"«{kind}»", size=13, bg=True)
            elif kind == "gen":
                cv.line(*p, *q)
                cv.arrowhead(p, q, "triangle", 14)
        for uid, x, y, lines, rx, ry in self.ucs:
            cv.ellipse(x, y, rx, ry, fill=ACT_FILL)
            cv.text(x, y, lines, size=self.FS)
        for aid, x, y, name in self.actors:
            self._actor(cv, x, y, name)
        return cv.svg(self.W, self.H)

    @staticmethod
    def _actor(cv, x, y, name):
        cv.add(f'<circle cx="{x}" cy="{y - 30}" r="10" fill="#fff" stroke="{STROKE}" stroke-width="1.5"/>')
        cv.line(x, y - 20, x, y + 8, sw=1.5)
        cv.line(x - 17, y - 11, x + 17, y - 11, sw=1.5)
        cv.line(x, y + 8, x - 13, y + 30, sw=1.5)
        cv.line(x, y + 8, x + 13, y + 30, sw=1.5)
        lines = wrap(name, 130, 14, True)
        cv.text(x, y + 42 + (len(lines) - 1) * 8.5, lines, size=14, bold=True, bg=True)
