# -*- coding: utf-8 -*-
"""
Sơ đồ use case tổng quát cho draw.io:
  - usecase_tong_quat.puml   : mã PlantUML (draw.io: Arrange > Insert > Advanced > PlantUML)
  - usecase_tong_quat.drawio : hình UML gốc của draw.io, sửa được từng phần tử
Ghi vào docs/so_do/drawio/.
"""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "drawio"

SYSTEM = "Hệ thống cảnh báo khoảng cách an toàn (YOLOv11 + IPM)"
ACTORS = [   # id, nhãn, tâm x, tâm y
    ("user", "Người dùng\n(tài xế / người vận hành)", 110, 330),
    ("cam", "Camera /\nnguồn video", 930, 170),
    ("ai", "Dịch vụ\nClaude API\n(tùy chọn)", 930, 430),
]
USE_CASES = [   # id, nhãn, tâm y  (xếp để đường nối không cắt nhau)
    ("uc01", "UC01. Quản lý nguồn\nvideo/camera", 120),
    ("uc04", "UC04. Giám sát realtime\n& cảnh báo", 225),
    ("uc02", "UC02. Cấu hình thông số IPM\n(căn chỉnh camera)", 330),
    ("uc03", "UC03. Cấu hình ngưỡng\ncảnh báo", 435),
    ("uc05", "UC05. Quản lý nhật ký\ncảnh báo", 540),
]
LINKS = [("user", u) for u, _, _ in USE_CASES] + [("uc01", "cam"), ("uc04", "cam"), ("uc03", "ai")]


def puml() -> str:
    q = lambda t: t.replace("\n", "\\n")  # noqa: E731
    lines = [
        "@startuml UseCase_TongQuat",
        "left to right direction",
        "skinparam defaultFontName \"Times New Roman\"",
        "skinparam defaultFontSize 14",
        "skinparam shadowing false",
        "skinparam actorStyle default",
        "skinparam usecase {",
        "  BackgroundColor #F4F8FD",
        "  BorderColor #1F1F1F",
        "}",
        "skinparam rectangle {",
        "  BorderColor #1F1F1F",
        "  FontStyle bold",
        "}",
        "",
    ]
    for aid, label, _, _ in ACTORS:
        lines.append(f'actor "{q(label)}" as {aid}')
    lines += ["", f'rectangle "{SYSTEM}" {{']
    for uid, label, _ in USE_CASES:
        lines.append(f'  usecase "{q(label)}" as {uid}')
    lines += ["}", ""]
    for a, b in LINKS:   # tác nhân chính bên trái, tác nhân phụ bên phải
        lines.append(f"{a} -- {b}")
    lines += ["@enduml", ""]
    return "\n".join(lines)


FONT = "fontFamily=Times New Roman;fontSize=14;"


def drawio() -> str:
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    bx, by, bw, bh = 260, 30, 520, 580
    cells.append(
        f'<mxCell id="system" value="{escape(SYSTEM)}" style="rounded=0;whiteSpace=wrap;html=1;container=1;'
        f'collapsible=0;fillColor=#FFFFFF;strokeColor=#1F1F1F;verticalAlign=top;fontStyle=1;spacingTop=6;'
        f'{FONT}fontSize=15;" vertex="1" parent="1">'
        f'<mxGeometry x="{bx}" y="{by}" width="{bw}" height="{bh}" as="geometry"/></mxCell>')
    uw, uh = 270, 72
    for uid, label, cy in USE_CASES:   # use case là phần tử con của khung hệ thống (tọa độ tương đối)
        val = escape(label).replace("\n", "&lt;br&gt;")
        cells.append(
            f'<mxCell id="{uid}" value="{val}" style="ellipse;whiteSpace=wrap;html=1;fillColor=#F4F8FD;'
            f'strokeColor=#1F1F1F;{FONT}" vertex="1" parent="system">'
            f'<mxGeometry x="{(bw - uw) / 2}" y="{cy - by - uh / 2}" width="{uw}" height="{uh}" as="geometry"/>'
            f'</mxCell>')
    for aid, label, cx, cy in ACTORS:
        val = escape(label).replace("\n", "&lt;br&gt;")
        cells.append(
            f'<mxCell id="{aid}" value="{val}" style="shape=umlActor;verticalLabelPosition=bottom;'
            f'verticalAlign=top;html=1;outlineConnect=0;fillColor=#FFFFFF;strokeColor=#1F1F1F;fontStyle=1;{FONT}" '
            f'vertex="1" parent="1"><mxGeometry x="{cx - 15}" y="{cy - 30}" width="30" height="60" as="geometry"/>'
            f'</mxCell>')
    for i, (a, b) in enumerate(LINKS):
        cells.append(
            f'<mxCell id="e{i}" style="endArrow=none;html=1;strokeColor=#1F1F1F;strokeWidth=1.3;" edge="1" '
            f'parent="1" source="{a}" target="{b}"><mxGeometry relative="1" as="geometry"/></mxCell>')
    model = (f'<mxGraphModel dx="1000" dy="650" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" '
             f'arrows="1" fold="1" page="1" pageScale="1" pageWidth="1100" pageHeight="700" math="0" shadow="0">'
             f'<root>{"".join(cells)}</root></mxGraphModel>')
    return ('<mxfile host="app.diagrams.net">'
            f'<diagram id="usecase-tong-quat" name="Use case tổng quát">{model}</diagram></mxfile>\n')


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    (OUT / "usecase_tong_quat.puml").write_text(puml(), encoding="utf-8")
    (OUT / "usecase_tong_quat.drawio").write_text(drawio(), encoding="utf-8")
    print("Đã ghi", OUT)
