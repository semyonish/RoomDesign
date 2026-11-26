"""Every PDF in pdf/, printed with headless Chrome on A4, each page turned to fit its sheet:
«Обмерный план», «План мебели», «План освещения» — the sheets of plan_sketch.py / plans.py, whole apartment and each
room; «Раскладка плитки», «Раскладка обоев» — a summary page and the sheets of tile_layout.py / wallpaper_layout.py;
«Расчёт материалов» — pdf/src/Расчёт материалов.html, its numbers from stats.py and the layouts; «Расчёт плитки» —
tiles, cuts, holes, 45° miters and grout from tile_works.py; «Чертежи» — the sheets of drawings.py, room by room.

    .venv/bin/python plans.py && .venv/bin/python plan_sketch.py --rooms && .venv/bin/python export.py
    .venv/bin/python tile_layout.py && .venv/bin/python tile_works.py
    .venv/bin/python wallpaper_layout.py && .venv/bin/python wallpaper_layout.py --seams
    .venv/bin/python pdfs.py
    .venv/bin/python pdfs.py tiles wallpaper     # just these: plans, tiles, works, wallpaper, seams, materials, drawings
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


def works(tmp):
    """«Расчёт плитки» — tiles of each kind, cut length, holes, 45° miters, grout: renders/layout/tile_works.json."""
    t = json.loads((ROOT / "renders/layout/tile_works.json").read_text())
    Z, T, K = t["zones"], t["total"], t["kinds"]
    am = [z for z in Z if z["kind"] == "amrita"]
    du = next(z for z in Z if z["kind"] == "duna")
    m1 = lambda v: c(v, 1)   # noqa: E731
    cut_all = T["cut_amrita"] + T["cut_duna"]
    n_holes = sum(v for k, v in T["holes"].items() if k != "cutout")
    n_sure = sum(v for k, v in T["holes_sure"].items() if k != "cutout")
    g = T["grout"]
    grout = g["between"] + g["flat"] + g["outer"]
    buy = round(T["amrita"] * 1.05)

    def zone_rows(cols, total=None):
        rows = "".join("<tr>" + "".join(f'<td{" class=r" if i else ""}>{f(z)}</td>' for i, f in enumerate(cols)) +
                       "</tr>" for z in Z)
        if total:
            rows += '<tr class="total">' + "".join(f'<td{" class=r" if i else ""}>{v}</td>'
                                                  for i, v in enumerate(total)) + "</tr>"
        return rows

    tiles_tbl = zone_rows(
        [lambda z: z["title"], lambda z: f'{z["first"]}–{z["last"]}', lambda z: c(z["area"]), lambda z: z["tiles"],
         lambda z: z["whole"], lambda z: z["cut_tiles"]])
    notched = "; ".join(f'{z["title"].split(":")[0]} — {", ".join(n[0] for n in z["notched"])}'
                        for z in Z if z["notched"])
    cuts_tbl = zone_rows(
        [lambda z: z["title"], lambda z: z["cut_tiles"], lambda z: z["cuts"], lambda z: m1(z["straight"]),
         lambda z: len(z["notched"]) or "—", lambda z: m1(z["notch"]) if z["notched"] else "—",
         lambda z: f'<b>{m1(z["cut_m"])}</b>'],
        ["Итого Amrita", sum(z["cut_tiles"] for z in am), sum(z["cuts"] for z in am),
         m1(sum(z["straight"] for z in am)), sum(len(z["notched"]) for z in am), m1(sum(z["notch"] for z in am)),
         m1(T["cut_amrita"])])
    gr = lambda z: z["grout"]   # noqa: E731
    grout_tbl = zone_rows(
        [lambda z: z["title"], lambda z: m1(gr(z)["between"]), lambda z: m1(gr(z)["flat"]) if gr(z)["flat"] else "—",
         lambda z: m1(gr(z)["outer"]) if gr(z)["outer"] else "—",
         lambda z: f'<b>{m1(gr(z)["between"] + gr(z)["flat"] + gr(z)["outer"])}</b>',
         lambda z: m1(gr(z)["inner"]) if gr(z)["inner"] else "—", lambda z: m1(gr(z)["seal"]) if gr(z)["seal"] else "—"],
        ["Итого", m1(g["between"]), m1(g["flat"]), m1(g["outer"]), m1(grout), m1(g["inner"]), m1(g["seal"])])

    def tile_of(h):
        if not h["tiles"]:
            return "—"
        labs = []
        for p in h["tiles"]:
            s = " / ".join(p) + (" (на шве)" if len(p) > 1 else "")
            if s not in labs:
                labs.append(s)
        return ", ".join(labs)

    def holes_tbl(rooms):
        rows = "".join(
            f'<tr><td>{h["item"]}</td><td>{K[h["kind"]][0]}</td><td class="r">{K[h["kind"]][1]}</td>'
            f'<td class="r">{h["n"]}</td><td>{h["where"]}</td><td>{tile_of(h)}</td><td>{t["place"][h["place"]]}</td></tr>'
            for h in t["holes"] if h["room"] in rooms)
        return ('<table class="holes"><tr><th>Прибор</th><th>Что проходит</th><th class="r">Отверстие</th><th class="r">Шт</th>'
                f'<th>Где</th><th>Плитка №</th><th>Место</th></tr>{rows}</table>')

    cls = "".join(f'<tr><td>{name}</td><td class="r">{T["holes_sure"][k]}</td>'
                  f'<td class="r">{T["holes"][k] - T["holes_sure"][k]}</td><td class="r"><b>{T["holes"][k]}</b></td></tr>'
                  for k, name in t["classes"])
    miters = "".join(f'<tr><td>{x["room"]}</td><td>{x["where"]}</td><td class="r">{c(x["cm"], 1)}</td></tr>'
                     for x in t["miters"])
    wc = T["without_cabinets"]
    html = f"""
<h1>Расчёт плитки</h1>
<div class="sub">Сколько плитки, подрезки, отверстий, запилов 45° и затирки. Считано по «Раскладке плитки»,
  номера плиток те же · {DATE}</div>
<div class="summary">
  <div class="card"><div class="k">Amrita 60×120, серо-бежевый мат</div><div class="v">{T["amrita"]} <small>плиток</small></div>
    <div class="d">по раскладке, {c(T["amrita_area"], 1)} м²; купить ≈ {buy} (≈ 5% на бой)</div></div>
  <div class="card"><div class="k">Duna Magnum White Carving 60×120</div><div class="v">{T["duna"]} <small>плиток</small></div>
    <div class="d">стена за ванной, {c(du["area"])} м²; купить {T["duna"] + 1}</div></div>
  <div class="card"><div class="k">Подрезка</div><div class="v">{m1(cut_all)} <small>м</small></div>
    <div class="d">Amrita {m1(T["cut_amrita"])} м + Duna {m1(T["cut_duna"])} м</div></div>
  <div class="card"><div class="k">Отверстия</div><div class="v">{n_holes} <small>шт</small></div>
    <div class="d">из них {n_sure} — по плану, остальные ждут решения; + {T["holes"]["cutout"]} прямоугольных выреза</div></div>
  <div class="card"><div class="k">Запил 45°</div><div class="v">{c(T["miter_corner"], 1)} <small>м угла</small></div>
    <div class="d">= {c(2 * T["miter_corner"], 1)} м запиленных кромок (по две плитки на угол)</div></div>
  <div class="card"><div class="k">Затирка, шов 1 мм</div><div class="v">{round(grout)} <small>м</small></div>
    <div class="d">+ внутренние углы {round(g["inner"])} м (затирка или силикон); силикон по ванне и столешнице {m1(g["seal"])} м</div></div>
</div>

<h2>1. Плитка по видам и зонам</h2>
<table>
  <tr><th>Зона</th><th class="r">Номера</th><th class="r">м²</th><th class="r">Плиток</th><th class="r">Целых</th><th class="r">Режется</th></tr>
  {tiles_tbl}
  <tr class="total"><td>Итого Amrita</td><td class="r">1–{am[-1]["last"]}</td><td class="r">{c(T["amrita_area"])}</td>
    <td class="r">{T["amrita"]}</td><td class="r">{sum(z["whole"] for z in am)}</td><td class="r">{sum(z["cut_tiles"] for z in am)}</td></tr>
</table>
<ul>
  <li><b>Amrita</b> (Global Tile, 60×120, матовый серо-бежевый) — полы прихожей, кухни-гостиной, лоджий и санузлов, стены
    санузлов до потолка, короба, экран ванны, фартук. <b>Duna</b> — только стена за ванной, от борта до потолка.</li>
  <li>Обрезки идут в дело в своей комнате, плитку не поворачивают (прожилки вдоль плитки). Если носить обрезки между
    комнатами, хватит {T["shared"]} плиток Amrita.</li>
  <li>Без плитки за шкафами до потолка (колонна стирки и сушки, шкаф над коробом туалета, пенал) плиток Amrita нужно
    {wc["amrita"]}.</li>
</ul>

<h2>2. Подрезка</h2>
<table>
  <tr><th>Зона</th><th class="r">Режется плиток</th><th class="r">Резов</th><th class="r">Прямые резы, м</th>
    <th class="r">Фигурных кусков</th><th class="r">Их вырезы, м</th><th class="r">Всего, м</th></tr>
  {cuts_tbl}
</table>
<ul>
  <li><b>Как считано.</b> Каждая плитка режется по листам «Раскрой» прямыми резами на всю ширину отрезаемого куска,
    как режет плиткорез. Фигурные куски (Г- и П-образные: у дверей санузлов, заходы в проёмы, у короба стояка, экран
    над низким коробом) режутся ещё и по контуру выреза, болгаркой; эти метры в отдельной колонке.</li>
  <li><b>Фигурные куски:</b> {notched}.</li>
  <li>Резы под отверстия и запилы 45° сюда не входят: они в разделах 3 и 4. Запил делают по кромке, которая уже
    подрезана, поэтому плиточник считает его отдельной работой.</li>
  <li>Без плитки за шкафами до потолка подрезка Amrita ≈ {m1(wc["cut_amrita"])} м.</li>
</ul>

<h2>3. Отверстия и вырезы</h2>
<table>
  <tr><th>Размер</th><th class="r">Место есть в плане</th><th class="r">Ждут решения</th><th class="r">Всего</th></tr>
  {cls}
</table>
<p style="font-size:9pt;color:#6b645c">Диаметры типовые: точный размер коронки — по фитингу на месте. «Предложено» —
  место есть, но его ещё не утвердили. «Места в плане нет» — прибор есть, а куда выходят трубы и розетки, не
  решено. «Плитка №» — номер куска по «Раскладке плитки».</p>
<h3 style="font-size:11pt;margin:10pt 0 2pt">Ванная</h3>
{holes_tbl({"ванная", "ванная, туалет"})}
<h3 style="font-size:11pt;margin:10pt 0 2pt">Туалет</h3>
{holes_tbl({"туалет"})}
<h3 style="font-size:11pt;margin:10pt 0 2pt">Кухня</h3>
{holes_tbl({"кухня"})}
<ul>
  <li><b>Унитазы</b> — Grohe Rapid SL: слив на 23, шпильки М12 через 18 на 33, промывочная труба на 37, клавиша —
    центр на 100 (высоты от чистого пола). Все отверстия под унитаз попадают в одну плитку (ванная 64б, туалет 103).</li>
  <li><b>Фартук:</b> подрозетники в рамке стоят через 71 мм, между отверстиями Ø 68 остаётся перемычка 3 мм. Обычно
    вместо отдельных отверстий режут один паз: 6,8 × 13,9 см под двойную рамку и 6,8 × 28,1 см под рамку на 4.</li>
  <li>Дюбели под крепёж (кронштейны полотенцесушителей, зеркал, стойки душа, держатели) не считаны: их сверлят при
    монтаже приборов.</li>
</ul>

<h2>4. Запил под 45°</h2>
<table>
  <tr><th>Помещение</th><th>Внешний угол</th><th class="r">Длина, см</th></tr>
  {miters}
  <tr class="total"><td>Итого</td><td>угла / запиленных кромок</td><td class="r">{c(T["miter_corner"] * 100, 1)} / {c(T["miter_corner"] * 200, 1)}</td></tr>
</table>
<ul>
  <li>Запил нужен на каждом внешнем углу, где плитка встречает плитку. На каждом таком углу запиливают обе плитки,
    поэтому кромок вдвое больше, чем длина угла. Остальные углы внутренние, запил там не нужен.</li>
  <li>В туалете верх короба без плитки (на нём стоит шкаф в одной плоскости с лицом), запила нет. Нижний край экрана ванны
    над нишей для ног — заводской кромкой вниз.</li>
</ul>

<h2>5. Затирка</h2>
<table>
  <tr><th>Зона</th><th class="r">Швы между плитками</th><th class="r">Стыки зон</th><th class="r">Внешние углы</th>
    <th class="r">Затирка, м</th><th class="r">Внутр. углы</th><th class="r">Силикон</th></tr>
  {grout_tbl}
</table>
<ul>
  <li><b>Затирка</b> — швы 1 мм между всеми кусками по раскладке, плюс стыки двух облицованных зон в одной плоскости
    (плитка прихожей с плиткой санузлов в проёмах, лицо высокого и низкого короба) и швы по запилам внешних углов.</li>
  <li><b>Внутренние углы</b> (стена–стена, стена–пол, короба и экран со стенами, фартук в углах короба стояка) —
    затирка или санитарный силикон: в санузлах обычно силикон.</li>
  <li><b>Силикон:</b> плитка по борту ванны (стены над бортом и верх экрана) — {m1(sum(z["grout"]["seal"] for z in Z if z["key"] in ("bath", "duna")))} м,
    фартук по столешнице — {m1(next(z for z in Z if z["key"] == "splash")["grout"]["seal"])} м.</li>
  <li>Полы прихожей, кухни-гостиной и лоджий по стенам закрывает плинтус, на ламинат в проёмах — порог; эти края не
    затираются. Плитка за шкафами до потолка в счёте; без неё швов меньше.</li>
</ul>

<div class="flag"><b>Решить до укладки, иначе отверстия придётся сверлить по готовой плитке.</b> В туалете не задано, куда
  выходят вода и слив раковины (правая стена или лицо короба). За колонной стирки и сушки не заданы вода, слив и
  розетки: в плане розеток нет совсем, а нужны две, IP44. Выводы кабеля полотенцесушителей и зеркал — только
  предложение. Люк в экране ванны и проводные датчики протечки ещё не утверждены.</div>
<div class="flag">Не считано: трубы радиаторов через плитку пола кухни-гостиной, если они выходят из пола (+2 отверстия на
  радиатор), и розетки или выводы, которых нет в плане.</div>
"""
    secs = f'<section class="text">{html}</section>'
    page = tmp / "Расчёт плитки.html"
    page.write_text(f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Расчёт плитки</title>'
                    f'<style>{CSS} section.text table {{ font-size: 8.5pt; }} table.holes {{ break-inside: auto; }}'
                    f' table.holes tr {{ break-inside: avoid; }} table.holes td:nth-child(1) {{ width: 21%; }}'
                    f' table.holes td:nth-child(5) {{ width: 22%; }} h2, h3 {{ break-after: avoid; }}</style></head>'
                    f'<body>{secs}</body></html>')
    pdf = OUT / "Расчёт плитки.pdf"
    print_pdf(page, pdf, tmp)
    print(pdf)


def wallpaper(tmp, src="wallpaper.json", name="Раскладка обоев", compare=False):
    """«Раскладка обоев» — its own layout (A4 landscape, vector drawings): wallpaper_pdf.py."""
    import wallpaper_pdf
    w = json.loads((ROOT / "renders/layout" / src).read_text())
    html = tmp / f"{name}.html"
    html.write_text(wallpaper_pdf.document(w, DATE, compare))
    pdf = OUT / f"{name}.pdf"
    print_pdf(html, pdf, tmp)
    print(pdf)


def wallpaper_seams(tmp):
    """The layout by walls (wallpaper_layout.py --seams): «Раскладка обоев — меньше стыков», the plan alone, as
    «Раскладка обоев» is; «Стыки обоев — сравнение раскладок», how it changes the joints of the main layout."""
    wallpaper(tmp, "wallpaper_seams.json", "Раскладка обоев — меньше стыков")
    wallpaper(tmp, "wallpaper_seams.json", "Стыки обоев — сравнение раскладок", compare=True)


def drawings(tmp):
    """«Чертежи» — drawings.py: each room's plan and walls with sizes, then the sheets copied into its folder
    (зеркало, полотенцесушитель, каркас короба, короб с бойлером), rooms in their folder order."""
    sheets = []
    for room in sorted(p for p in (SHEETS / "Чертежи").iterdir() if p.is_dir()):
        sheets += [(f"{room.name.split(' ', 1)[1]}: {cap}", f) for cap, f in numbered(f"Чертежи/{room.name}")]
    build("Чертежи", "Чертежи", "", sheets, tmp)


def main():
    docs = {"plans": plans, "tiles": tiles, "works": works, "wallpaper": wallpaper, "seams": wallpaper_seams,
            "materials": materials, "drawings": drawings}
    names = sys.argv[1:] or list(docs)
    if set(names) - set(docs):
        sys.exit(f"unknown: {', '.join(sorted(set(names) - set(docs)))}; choose from {', '.join(docs)}")
    with tempfile.TemporaryDirectory() as d:
        for n in names:
            docs[n](Path(d))


if __name__ == "__main__":
    main()
