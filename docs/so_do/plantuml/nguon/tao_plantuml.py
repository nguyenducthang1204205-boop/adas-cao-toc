# -*- coding: utf-8 -*-
"""
Dựng toàn bộ sơ đồ PlantUML của đồ án và gom vào một file draw.io.

    python docs/so_do/plantuml/nguon/tao_plantuml.py [tên_sơ_đồ ...]

Đầu vào : nguon/*.puml (nội dung sơ đồ, chưa có phần định dạng chung)
Đầu ra  : docs/so_do/plantuml/
            *.puml                  - mã PlantUML hoàn chỉnh (dán được vào draw.io / plantuml.com)
            svg/*.svg, png/*.png    - ảnh dựng sẵn (PNG 200 dpi để chèn Word)
            SO_DO_PLANTUML.drawio   - mỗi sơ đồ một trang; nhấp đúp vào sơ đồ để sửa mã PlantUML

Cần Java và plantuml.jar: đặt biến môi trường PLANTUML_JAR (mặc định tìm plantuml.jar cạnh script)
và JAVA (mặc định java của Android Studio). Không cần Graphviz: dùng bộ bố cục Smetana có sẵn.
"""
import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
JAVA = os.environ.get("JAVA", r"C:\Program Files\Android\Android Studio\jbr\bin\java.exe")
JAR = os.environ.get("PLANTUML_JAR", str(HERE / "plantuml.jar"))

THEME = """!pragma layout smetana
skinparam defaultFontName "Times New Roman"
skinparam defaultFontSize 14
skinparam shadowing false
skinparam backgroundColor #FFFFFF
skinparam ArrowColor #1F1F1F
skinparam ArrowFontSize 13
skinparam RoundCorner 12
skinparam ActorBorderColor #1F1F1F
skinparam ActorBackgroundColor #FFFFFF
skinparam UsecaseBorderColor #1F1F1F
skinparam UsecaseBackgroundColor #F4F8FD
skinparam RectangleBorderColor #1F1F1F
skinparam RectangleFontStyle bold
skinparam PackageBorderColor #5A5A5A
skinparam PackageBackgroundColor #FAFBFC
skinparam ClassBorderColor #1F1F1F
skinparam ClassBackgroundColor #F4F8FD
skinparam ClassHeaderBackgroundColor #E3ECF6
skinparam ClassAttributeIconSize 0
skinparam ActivityBorderColor #1F1F1F
skinparam ActivityBackgroundColor #F4F8FD
skinparam ActivityDiamondBorderColor #1F1F1F
skinparam ActivityDiamondBackgroundColor #FFFFFF
skinparam SwimlaneBorderColor #1F1F1F
skinparam SwimlaneTitleFontStyle bold
skinparam SwimlaneTitleBackgroundColor #EEF2F7
skinparam ParticipantBorderColor #1F1F1F
skinparam ParticipantBackgroundColor #F4F8FD
skinparam SequenceLifeLineBorderColor #7A7A7A
skinparam SequenceGroupBorderColor #5A5A5A
skinparam SequenceGroupHeaderFontStyle bold
skinparam NoteBorderColor #9A8A3A
skinparam NoteBackgroundColor #FFFBE6
skinparam StateBorderColor #1F1F1F
skinparam StateBackgroundColor #F4F8FD
skinparam ComponentBorderColor #1F1F1F
skinparam ComponentBackgroundColor #F4F8FD
skinparam DatabaseBorderColor #1F1F1F
skinparam DatabaseBackgroundColor #FFFFFF
skinparam NodeBorderColor #1F1F1F
skinparam NodeBackgroundColor #FAFBFC
skinparam ArtifactBackgroundColor #FFFFFF
skinparam EntityBorderColor #1F1F1F
skinparam EntityBackgroundColor #F4F8FD
"""

TITLES = {   # tên trang trong draw.io
    "01": "BPMN tổng quát", "02": "BPMN chuẩn bị giám sát", "03": "BPMN giám sát & cảnh báo",
    "04": "UC tổng quát", "05": "UC01 phân rã", "06": "UC02 phân rã", "07": "UC03 phân rã",
    "08": "UC04 phân rã", "09": "UC05 phân rã",
    "10": "Hoạt động UC01", "11": "Hoạt động UC02", "12a": "Hoạt động UC03a", "12b": "Hoạt động UC03b",
    "13": "Hoạt động UC04", "14": "Hoạt động UC05",
    "15": "Tuần tự UC01", "16": "Tuần tự UC02", "17": "Tuần tự UC03", "18": "Tuần tự UC04", "19": "Tuần tự UC05",
    "20": "Lớp thực thể", "21": "ERD CSDL", "22": "Lớp tổng quát", "23": "Lớp xử lý", "24": "Lớp giao diện",
    "25": "Kiến trúc 5 tầng", "26": "Hoạt động xử lý 1 khung", "27": "Triển khai",
    "28": "Trạng thái mức cảnh báo", "29": "Trạng thái đợt vi phạm", "30": "Trạng thái phiên giám sát",
}


def with_theme(text: str) -> str:
    first, rest = text.split("\n", 1)
    return f"{first}\n{THEME}{rest}"


def render(files, fmt, extra=()):
    outdir = OUT / fmt
    outdir.mkdir(exist_ok=True)
    # java.exe giải mã tham số dòng lệnh theo bảng mã ANSI (không có "Đ"): dùng đường dẫn tương đối, chạy tại OUT
    jar = os.path.relpath(JAR, OUT) if Path(JAR).is_relative_to(OUT) else JAR
    r = subprocess.run([JAVA, "-DPLANTUML_LIMIT_SIZE=16384", "-jar", jar, f"-t{fmt}", "-charset", "UTF-8", *extra, "-o", fmt,
                        *(f.name for f in files)], cwd=OUT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
    return r.returncode == 0


def svg_size(svg: str):
    w = float(re.search(r'width="([\d.]+)px"', svg).group(1))
    h = float(re.search(r'height="([\d.]+)px"', svg).group(1))
    return w, h


def drawio(names):
    pages = []
    for i, name in enumerate(names):
        src = (OUT / f"{name}.puml").read_text(encoding="utf-8")
        svg = (OUT / "svg" / f"{name}.svg").read_text(encoding="utf-8")
        w, h = svg_size(svg)
        img = "data:image/svg+xml," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
        data = json.dumps({"data": src, "config": None}, ensure_ascii=False, indent=2)
        attr = escape(data, {'"': "&quot;", "\n": "&#10;"})
        cell = (f'<UserObject label="" plantUmlData="{attr}" id="puml-{i}">'
                f'<mxCell style="shape=image;noLabel=1;verticalAlign=top;imageAspect=1;editIcon=1;groupPadding=0;'
                f'image={img};" vertex="1" parent="1">'
                f'<mxGeometry x="20" y="20" width="{w:.0f}" height="{h:.0f}" as="geometry"/></mxCell></UserObject>')
        key = name.split("_")[0]
        title = escape(f"{key}. {TITLES.get(key, name)}", {'"': "&quot;"})
        pages.append(
            f'<diagram id="{name}" name="{title}"><mxGraphModel grid="0" page="1" pageScale="1" '
            f'pageWidth="{w + 40:.0f}" pageHeight="{h + 40:.0f}" math="0" shadow="0"><root>'
            f'<mxCell id="0"/><mxCell id="1" parent="0"/>{cell}</root></mxGraphModel></diagram>')
    xml = f'<mxfile host="app.diagrams.net">{"".join(pages)}</mxfile>\n'
    (OUT / "SO_DO_PLANTUML.drawio").write_text(xml, encoding="utf-8")


def main(only):
    srcs = sorted(HERE.glob("*.puml"))
    if only:
        srcs = [s for s in srcs if s.stem in only or s.stem.split("_")[0] in only]
    files = []
    for s in srcs:
        out = OUT / s.name
        out.write_text(with_theme(s.read_text(encoding="utf-8")), encoding="utf-8")
        files.append(out)
    ok = render(files, "svg") and render(files, "png", ["-Sdpi=200"])
    for f in files:
        print(("✔ " if (OUT / "svg" / f"{f.stem}.svg").exists() else "✖ ") + f.stem)
    if ok:
        drawio([p.stem for p in sorted(OUT.glob("*.puml"))])
        print("Đã ghi", OUT / "SO_DO_PLANTUML.drawio")


if __name__ == "__main__":
    main(set(sys.argv[1:]))
