"""Every PDF in pdf/, printed with headless Chrome on A4, each page turned to fit its sheet:
«Обмерный план», «План мебели», «План освещения» — the sheets of plan_sketch.py / plans.py, whole apartment and each
room; «Раскладка плитки», «Раскладка обоев» — a summary page and the sheets of tile_layout.py / wallpaper_layout.py;
«Расчёт материалов» — pdf/src/Расчёт материалов.html, its numbers from stats.py and the layouts.

    .venv/bin/python plans.py && .venv/bin/python plan_sketch.py --rooms && .venv/bin/python export.py
    .venv/bin/python tile_layout.py && .venv/bin/python wallpaper_layout.py && .venv/bin/python pdfs.py
    .venv/bin/python pdfs.py tiles wallpaper     # just these: plans, tiles, wallpaper, materials
"""
import datetime
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

from export import ROOMS as NAMES

ROOT = Path(__file__).resolve().parent
SHEETS, PLANS, OUT = ROOT / "renders/Рендеры", ROOT / "renders/plan", ROOT / "pdf"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DATE = datetime.date.today().strftime("%d.%m.%Y")

CSS = """
@page land { size: A4 landscape; margin: 9mm 10mm 8mm; }
@page port { size: A4 portrait; margin: 9mm 10mm 8mm; }
@page text { size: A4 portrait; margin: 16mm 15mm; }
:root { --ink: #1d1b19; --muted: #6b645c; --line: #d9d3ca; --soft: #f4f1ec; --accent: #8a6a3f; }
* { box-sizing: border-box; }
html, body { margin: 0; background: #fff; font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; color: var(--ink); }
section { display: flex; flex-direction: column; break-after: page; }
section:last-child { break-after: auto; }
section.land { page: land; height: 192mm; }
section.port { page: port; height: 279mm; }
section.text { page: text; display: block; font-size: 10pt; line-height: 1.4; }
.head { display: flex; justify-content: space-between; align-items: baseline; font-size: 10pt;
        border-bottom: 0.8pt solid #1d1b19; padding-bottom: 2mm; margin-bottom: 3mm; }
.head b { font-size: 12pt; }
.head span { color: #6b645c; font-size: 8.5pt; }
.img { flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; }
.img img { max-width: 100%; max-height: 100%; object-fit: contain; }
h1 { font-size: 19pt; margin: 0 0 2pt; }
.sub { color: var(--muted); margin-bottom: 12pt; }
h2 { font-size: 13pt; margin: 16pt 0 6pt; padding-bottom: 3pt; border-bottom: 1.5pt solid var(--ink); }
.summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6pt; margin: 4pt 0 6pt; }
.card { background: var(--soft); border-radius: 4pt; padding: 8pt 9pt; }
.card .k { font-size: 8.5pt; color: var(--muted); }
.card .v { font-size: 18pt; font-weight: 700; margin: 2pt 0 1pt; white-space: nowrap; }
.card .v small { font-size: 11pt; font-weight: 600; }
.card .d { font-size: 8pt; color: var(--muted); line-height: 1.3; }
table { width: 100%; border-collapse: collapse; margin: 4pt 0 6pt; break-inside: avoid; }
th, td { padding: 3.5pt 6pt; border-bottom: 0.6pt solid var(--line); vertical-align: top; }
th { text-align: left; font-size: 8.5pt; color: var(--muted); font-weight: 600; border-bottom: 1pt solid var(--ink); }
td.r, th.r { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
tr.total td { font-weight: 700; border-top: 1pt solid var(--ink); border-bottom: none; }
ul { margin: 4pt 0; padding-left: 14pt; break-inside: avoid; }
li { margin: 2.5pt 0; }
.flag { border-left: 2.5pt solid var(--accent); padding: 4pt 8pt; background: #faf6ef; margin: 6pt 0; font-size: 9pt;
        break-inside: avoid; }
"""


def c(v, d=2):  # Russian decimal comma
    return f"{v:.{d}f}".replace(".", ",")


def print_pdf(html, pdf, tmp):
    OUT.mkdir(exist_ok=True)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--user-data-dir={tmp / 'chrome-profile'}", f"--print-to-pdf={pdf}", html.as_uri()],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def build(name, title, summary_html, sheets, tmp):
    """sheets: (caption, png); with a summary page first when summary_html is given."""
    secs = [f'<section class="text">{summary_html}</section>'] if summary_html else []
    n = len(sheets) + len(secs)
    for i, (caption, src) in enumerate(sheets, len(secs) + 1):
        w, h = Image.open(src).size
        kind = "land" if w / h > 1.05 else "port"
        secs.append(f'<section class="{kind}"><div class="head"><b>{title} — {caption}</b>'
                    f'<span>Квартира · {DATE} · лист {i} из {n}</span></div>'
                    f'<div class="img"><img src="{src.as_uri()}"></div></section>')
    html = tmp / f"{name}.html"
    html.write_text(f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>{name}</title>'
                    f'<style>{CSS}</style></head><body>{"".join(secs)}</body></html>')
    pdf = OUT / f"{name}.pdf"
    print_pdf(html, pdf, tmp)
    print(pdf, n)


def numbered(folder):
    """Sheets named «NN caption.png», in order."""
    return [(f.stem.split(" ", 1)[1], f) for f in sorted((SHEETS / folder).glob("*.png"))]


# each loggia right after its room
ORDER = ["hall", "kitchen_living", "loggia_kitchen", "bedroom_1", "loggia_bedroom_1", "study", "bedroom_2",
         "bathroom", "toilet"]
PLAN_DOCS = [  # (pdf name, sheet for the whole apartment, prefix of the room sheets)
    ("Обмерный план", "plan", ""),
    ("План мебели", "furniture", "furniture_"),
    ("План освещения", "lights", "lights_"),
]


def plans(tmp):
    for name, whole, prefix in PLAN_DOCS:
        pages = [(room, PLANS / (f"{whole}.png" if not rid else f"{prefix}{rid}.png"))
                 for rid, room in [("", "Вся квартира")] + [(rid, NAMES[rid]) for rid in ORDER]]
        build(name, name, "", [(room, src) for room, src in pages if src.exists()], tmp)


def materials(tmp):
    pdf = OUT / "Расчёт материалов.pdf"
    print_pdf(OUT / "src/Расчёт материалов.html", pdf, tmp)
    print(pdf)


def tiles(tmp):
    t = json.loads((ROOT / "renders/layout/tiles.json").read_text())
    G = {g["key"]: g for g in t["groups"]}
    amrita = [g for g in t["groups"] if g["key"] != "duna"]
    n_am = sum(g["tiles"] for g in amrita)
    a_am = sum(g["area"] for g in amrita)
    saved = sum(g["tiles"] - g["without_cabinets"]["tiles"] for g in amrita if g["without_cabinets"])
    rows = "".join(
        f'<tr><td>{g["title"]}</td><td class="r">{g["first"]}–{g["last"]}</td><td class="r">{c(g["area"])}</td>'
        f'<td class="r">{g["pieces"]}</td><td class="r">{g["whole"]}</td><td class="r">{g["tiles"]}</td></tr>'
        for g in amrita)
    d = G["duna"]
    html = f"""
<h1>Раскладка плитки</h1>
<div class="sub">Полы, стены санузлов, короба, экран ванны, фартук — каждый кусок пронумерован · {DATE}</div>
<div class="summary">
  <div class="card"><div class="k">Amrita 60×120 по раскладке</div><div class="v">{n_am} <small>плиток</small></div>
    <div class="d">{c(a_am, 1)} м² уложено; обрезки — в той же комнате</div></div>
  <div class="card"><div class="k">Купить Amrita с запасом ≈ 5% на бой</div><div class="v">≈ {round(n_am * 1.05)} <small>плиток</small></div>
    <div class="d">≈ {c(round(n_am * 1.05) * 0.72, 1)} м²</div></div>
  <div class="card"><div class="k">Duna — стена за ванной</div><div class="v">{d["tiles"]} <small>плиток</small></div>
    <div class="d">{c(d["area"])} м², номера Д1–Д{d["last"]}; с запасом — {d["tiles"] + 1}</div></div>
</div>
<h2>Amrita: плитки по зонам</h2>
<table>
  <tr><th>Зона</th><th class="r">Номера</th><th class="r">м²</th><th class="r">Кусков</th><th class="r">Целых</th><th class="r">Плиток</th></tr>
  {rows}
  <tr class="total"><td>Итого</td><td class="r">1–{amrita[-1]["last"]}</td><td class="r">{c(a_am)}</td>
    <td class="r">{sum(g["pieces"] for g in amrita)}</td><td class="r">{sum(g["whole"] for g in amrita)}</td><td class="r">{n_am}</td></tr>
</table>
<ul>
  <li><b>Как читать номера.</b> Номер — плитка, из которой вырезан кусок: «12» — целая плитка, «12а», «12б» — куски
    плитки 12. Красным — подрезка, под номером её размер (длина × высота по плитке, см); «вырез» — кусок не прямоугольный
    (вокруг двери, угла). Как резать каждую плитку — листы «Раскрой». Количество плиток — последний номер.</li>
  <li><b>Проёмы прихожей.</b> Во входной двери плитка заходит на 8 см до шва y −8. В проёмах кабинета, спальни 2 и
    спальни 1 — целая плитка 120, её заводской край внутри проёма: швы x −112,2 и 247,8. Стена прихожей косая, поэтому
    заход у кабинета 6,9–7,9 см, у спальни 2 — 8,2–9,1, у спальни 1 — 7,8; дальше в проёме ламинат.</li>
  <li><b>Обрезки используются только в своей комнате</b>, плитку не поворачивают (прожилки вдоль плитки).
    Если носить обрезки между комнатами, хватит {t["shared"]} плиток.</li>
  <li><b>Без плитки за шкафами до потолка</b> (колонна стирки и сушки, шкаф над коробом, пенал) — на {saved} плиток
    меньше: ванная {G["bath"]["without_cabinets"]["tiles"]}, туалет {G["toilet"]["without_cabinets"]["tiles"]},
    всего {n_am - saved}.</li>
  <li><b>Короба:</b> лицо, верх и торец короба инсталляции и лицо и верх низкого короба в ванной; в туалете — только лицо
    короба (верх — ГКЛ под шкаф). Экран ванны и подступенок — плиткой стен, швы в линию со стеной.</li>
  <li>Кусок тоньше 3 см присоединяется к соседнему в ряду (у борта ванны: 33 вместо 32 + 1).</li>
</ul>
<div class="flag">Узкие куски, которые стоит решить до укладки: в проёмах ванной и туалета плитка прихожей заходит на 2 см,
  а её шов — на 1 см от стены, поэтому остаётся полоса 80 × 1 (куски 2б, 2в). Лучше довести плитку санузлов до шва
  прихожей. У двери ванной с одной стороны полоса 3,5 см (61б, 67б, 70б): её закроет наличник, если он есть со стороны
  ванной.</div>
<div class="flag">Фартук под вопросом: если будет панель — минус 4 плитки ({G["splash"]["first"]}–{G["splash"]["last"]}).</div>
"""
    build("Раскладка плитки", "Раскладка плитки", html, numbered("Раскладка плитки"), tmp)


def plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    return few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


VISIBLE = {"54355-3": 100.69, "54355-7": 28.48}   # m² of wall under wallpaper, from stats.py


def wallpaper(tmp):
    w = json.loads((ROOT / "renders/layout/wallpaper.json").read_text())
    W, L = w["width"] / 100, w["length"] / 100
    size = f"{c(W)} × {c(L)} м"
    word = lambda n: plural(n, "рулон", "рулона", "рулонов")
    rolls = lambda n: f'{n} <small>{word(n)}</small>'

    def row(r, cls="", art=True):
        return (f'<tr class="{cls}"><td>{r["name"]}</td><td>{r["article"] if art else ""}</td>'
                f'<td class="r">Р{r["first"]}–Р{r["last"]}</td><td class="r">{r["strips"]}</td>'
                f'<td class="r">{r["pieces"]}</td><td class="r">{c(r["cut"])}</td><td class="r">{r["rolls"]}</td></tr>')
    rows = ""
    for a in w["articles"]:
        rs = [r for r in w["rooms"] if r["article"] == a["article"]]
        rows += "".join(row(r) for r in rs)
        if len(rs) > 1:
            rows += row(dict(a, name=f'Итого {a["article"]}', pieces=sum(r["pieces"] for r in rs)), "total", art=False)
    A = {a["article"]: a for a in w["articles"]}
    a3, a7 = A["54355-3"], A["54355-7"]
    narrow = [(r["name"].lower(), r["list"][-1]) for r in w["rooms"]
              if len(r["list"][-1]["pieces"]) == 1 and r["list"][-1]["rest"] > 500]
    narrow = ", ".join(f'{n} — Р{l["roll"]} (полоса {l["pieces"][0]["strip"]}, {c(l["pieces"][0]["width"], 0)} см)'
                       for n, l in narrow)
    html = f"""
<h1>Раскладка обоев</h1>
<div class="sub">{w["product"]}, рулон {size}, однотонные, раппорт 0 · кабинет — 54355-7, остальные комнаты — 54355-3 ·
  каждая полоса пронумерована, с рулоном, из которого режется · {DATE}</div>
<div class="summary">
  <div class="card"><div class="k">54355-3 — прихожая, кухня-гостиная, спальни 1 и 2</div><div class="v">{rolls(a3["rolls"])}</div>
    <div class="d">Р{a3["first"]}–Р{a3["last"]} · стены {c(VISIBLE["54355-3"], 1)} м² · с переносом остатков между
      комнатами — {a3["rolls_shared"]}</div></div>
  <div class="card"><div class="k">54355-7 — кабинет</div><div class="v">{rolls(a7["rolls"])}</div>
    <div class="d">Р{a7["first"]}–Р{a7["last"]} · стены {c(VISIBLE["54355-7"], 1)} м²</div></div>
  <div class="card"><div class="k">Всего по раскладке</div><div class="v">{rolls(w["rolls"])}</div>
    <div class="d">{size}; каждая комната — из своих рулонов</div></div>
</div>
<h2>По комнатам</h2>
<table>
  <tr><th>Комната</th><th>Артикул</th><th class="r">Рулоны</th><th class="r">Полос</th><th class="r">Кусков</th><th class="r">Отрезано, м²</th><th class="r">Рулонов</th></tr>
  {rows}
  <tr class="total"><td>Всего</td><td></td><td class="r">Р1–Р{w["rolls"]}</td><td class="r">{sum(r["strips"] for r in w["rooms"])}</td>
    <td class="r">{sum(r["pieces"] for r in w["rooms"])}</td><td class="r">{c(sum(r["cut"] for r in w["rooms"]))}</td><td class="r">{w["rolls"]}</td></tr>
</table>
<ul>
  <li><b>Полоса</b> — высота стены 270 + 10 на подрезку = 280 см, из рулона {c(L)} м выходят 3 полосы и остаток 165:
    он идёт на куски над дверями (63) и под окнами (88). Поэтому рулонов столько же, сколько троек полных полос.</li>
  <li><b>Артикулы не смешиваются:</b> рулоны Р{a3["first"]}–Р{a3["last"]} — 54355-3, Р{a7["first"]}–Р{a7["last"]} — 54355-7
    (кабинет). Прихожая и кухня-гостиная разделены на внешнем углу у арки: стена ТВ — кухня-гостиная, стена с дверями
    спальни 2 и кабинета — прихожая; у каждой свои рулоны.</li>
  <li><b>Последний рулон уходит на одну узкую полосу</b>: {narrow}; от него остаётся 7,25 м. Если остатки 54355-3
    переносить между прихожей, кухней-гостиной и спальнями — хватит {a3["rolls_shared"]} {word(a3["rolls_shared"])}
    вместо {a3["rolls"]}. В кабинете так не сэкономить: {a7["rolls_shared"]} {word(a7["rolls_shared"])} и там, и так.</li>
  <li><b>Как клеить.</b> Полосы идут слева направо от красной стрелки — от края шкафа, за которым обоев нет, или от
    угла; на углу полоса режется вдоль, её остаток начинает следующую стену. Цвет полосы на развёртке — её рулон; на
    листах «Раскрой рулонов» — что режется из каждого рулона по порядку.</li>
  <li><b>Обоев нет</b> за шкафами-купе и распашными шкафами, за кухней и колонной холодильника, за шкафом в нише и
    коробом стояка; проёмы дверей (до 217) и окон вычтены, откосы не считаны. Лоджии — покраска.</li>
  <li>Если натяжной потолок ставят раньше и обои идут до профиля (≈ 265), полоса 275 — рулонов столько же.</li>
</ul>
<div class="flag">Размер рулона {size} и раппорт 0 — по карточкам магазинов; сверьте с этикеткой. Рулоны одного
  артикула берите из одной партии (номер партии на этикетке), иначе на стыках может быть видна разница в оттенке.</div>
"""
    build("Раскладка обоев", "Раскладка обоев", html, numbered("Раскладка обоев"), tmp)


def main():
    docs = {"plans": plans, "tiles": tiles, "wallpaper": wallpaper, "materials": materials}
    names = sys.argv[1:] or list(docs)
    if set(names) - set(docs):
        sys.exit(f"unknown: {', '.join(sorted(set(names) - set(docs)))}; choose from {', '.join(docs)}")
    with tempfile.TemporaryDirectory() as d:
        for n in names:
            docs[n](Path(d))


if __name__ == "__main__":
    main()
