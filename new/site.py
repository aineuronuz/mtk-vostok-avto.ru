"""Новый многостраничный сайт МТК Восток-Авто (Юрий 05.10.2026: «как mercedes-benz.com», сине-белый, многостраничный,
каталог с фильтрами, машины из КП с ценой на сегодня, частые вопросы).

Собирает docs/ — основной адрес mtk-vostok-avto.ru (Юрий одобрил 06.10.2026; до того был /new/, закрыт от поиска) из:
  ~/auto-china/catalog/cars_data.py — 92 модели каталога (цены «Авто»);
  new/data/models.json — описания моделей; new/data/kp_cars.json + new/price.py — машины из КП и расчёт под ключ;
  new/data/faq.json — частые вопросы; new/src/s.css, s.js — оформление.
Курс: ЦБ — cbr-xml-daily.ru; курс юаня для расчёта — new/data/kurs.json (см. vtb_rate()).
Запуск: python3 new/site.py [--offline]
"""
import hashlib
import html
import importlib.util
import json
import math
import re
import shutil
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent          # репозиторий mtk-vostok-avto.ru
NEW = ROOT / "new"
DATA = NEW / "data"
OUT = ROOT / "docs"                                    # docs/foto/, docs/assets/, CNAME — не трогаются
IMG = OUT / "img"
BASE = "/"
SITE = "https://mtk-vostok-avto.ru"
PREVIEW = False                                         # True — noindex, для пробной версии
AC = Path.home() / "auto-china"
CARS = AC / "catalog" / "cars"
CARS_MTK = AC / "catalog" / "cars_plate_mtk"           # те же фото с номером «ВОСТОК-АВТО», как в каталоге МТК
MTK = AC / "mtk"
MAIN_IMG = ROOT / "docs" / "assets" / "img"            # фото основного сайта (выданные, специалисты)
BOOKMAN = "/usr/share/fonts/opentype/urw-base35/URWBookman-Demi.otf"
TODAY = date.today()
E = html.escape

sys.path.insert(0, str(AC / "catalog"))
import cars_data  # noqa: E402

_spec = importlib.util.spec_from_file_location("mtk_build", ROOT / "build.py")
_mb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mb)
TEAM = _mb.TEAM
MAX_HREF = "https://max.ru/u/f9LHodD0cOLQzwPoUyWBoejqc5iq940FAYmSIsMAm8Hr1FcNu85zWG126zY"
CHANNEL = "https://t.me/mtk_vostok_avto"

MENU = [("katalog/", "Каталог"), ("avto/", "Авто в Китае"), ("kak-kupit/", "Как купить"), ("stoimost/", "Стоимость"),
        ("vydannye/", "Выданные"), ("voprosy/", "Вопросы"), ("kontakty/", "Контакты")]
PAGES = []                                              # (путь, приоритет) — для sitemap.xml
MIN_YEAR = 2022                                         # машины 2021 года не показывать (Юрий 06.10.2026)


# ---------- мелочи ----------
def nb(s):
    return s.replace(" ", "&nbsp;")


def rub(v):
    return f"{round(v):,}".replace(",", "&nbsp;") + "&nbsp;₽"


def mln(v):
    return f"{v / 1e6:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def price_range(a, b):
    return f"от {mln(a)}" + (f" до {mln(b)}" if b else "") + "&nbsp;млн&nbsp;₽"


def ddmm(d):
    return d.strftime("%d.%m.%Y")


def plural(n, one, few, many):
    n = abs(n) % 100
    if 10 < n < 20:
        return many
    n %= 10
    return one if n == 1 else few if 2 <= n <= 4 else many


def slugify(s):
    tr = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя", ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))
    s = "".join(tr.get(c, c) for c in s.lower())
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def webp(src, dst, w, q=74, crop=None):
    """Картинка в webp не шире w; пересобирается, только если исходник новее."""
    dst = Path(dst)
    if dst.exists() and dst.stat().st_mtime >= Path(src).stat().st_mtime:
        with Image.open(dst) as im:
            return im.size
    dst.parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(src).convert("RGB")
    if crop:
        im = im.crop(crop)
    if im.width > w:
        im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    im.save(dst, quality=q, method=6)
    return im.size


def u(path=""):
    return BASE + path


# ---------- курс ----------
def cbr_rates(offline=False):
    """ЦБ: юань и евро на сегодня; при сбое — последние сохранённые."""
    keep = DATA / "rates.json"
    if not offline:
        try:
            with urllib.request.urlopen("https://www.cbr-xml-daily.ru/daily_json.js", timeout=20) as r:
                d = json.load(r)
            res = {"date": d["Date"][:10], "cny": d["Valute"]["CNY"]["Value"] / d["Valute"]["CNY"]["Nominal"],
                   "eur": d["Valute"]["EUR"]["Value"]}
            keep.write_text(json.dumps(res, ensure_ascii=False, indent=1))
            return res
        except Exception as e:  # noqa: BLE001
            print("ЦБ недоступен:", e)
    return json.loads(keep.read_text())


def vtb_rate(cbr):
    """Курс юаня для расчёта. Если в kurs.json есть курс ВТБ на сегодня (присланный Юрием) — он.
    Иначе — ЦБ × наценка ВТБ, снятая с последнего курса Юрия (сайт ВТБ с сервера за границей не открывается)."""
    k = json.loads((DATA / "kurs.json").read_text())
    if k.get("date") == TODAY.isoformat():
        return k["vtb"], "ВТБ"
    m = k["vtb"] / k["cbr_cny"]
    return round(cbr["cny"] * m, 2), "ВТБ, оценка"


# ---------- оформление ----------
def fonts():
    from fontTools import subset
    (OUT / "fonts").mkdir(parents=True, exist_ok=True)
    uni = (list(range(0x20, 0x7F)) + list(range(0xA0, 0x100)) + list(range(0x400, 0x460))
           + [0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x201E, 0x2026, 0x2116, 0x20BD, 0x2192, 0x2190, 0x2009, 0x202F, 0x2713, 0x00D7, 0x2212])
    for src, name in ((Path.home() / ".fonts/gf/GolosText[wght].ttf", "golos"), (Path.home() / ".fonts/gf/Inter[opsz,wght].ttf", "inter")):
        dst = OUT / "fonts" / f"{name}.woff2"
        if dst.exists():
            continue
        o = subset.Options()
        o.flavor = "woff2"
        o.layout_features = ["kern", "liga", "calt", "tnum", "case"]
        f = subset.load_font(str(src), o)
        s = subset.Subsetter(o)
        s.populate(unicodes=uni)
        s.subset(f)
        subset.save_font(f, str(dst), o)


def brand():
    """Круглый логотип и надпись как на обложке КП: «ВОСТОК-АВТО» (Bookman) и под ней в ту же ширину
    «МЕЖДУНАРОДНАЯ ТРАНСПОРТНАЯ КОМПАНИЯ» — синяя для белой шапки и белая для тёмной."""
    lg = Image.open(MTK / "logo" / "colors" / "MTK-logo-cvet-03-krupnee.png").convert("RGBA")
    lg = lg.crop(lg.getchannel("A").point(lambda v: 255 if v > 200 else 0).getbbox())
    for px in (64, 128, 192):
        lg.resize((px, px), Image.LANCZOS).save(IMG / f"logo{px}.webp", quality=90, method=6)
    lg.resize((128, 128), Image.LANCZOS).save(IMG / "logo128.png", optimize=True)
    lg.resize((64, 64), Image.LANCZOS).save(OUT / "favicon.png", optimize=True)
    ti = Image.new("RGBA", (180, 180), (245, 247, 251, 255))
    ti.alpha_composite(lg.resize((164, 164), Image.LANCZOS), (8, 8))
    ti.convert("RGB").save(OUT / "apple-touch-icon.png", optimize=True)

    W = 840                                           # 3× от 280 px на экране
    nm = Image.open(MTK / "kp" / "nazvanie" / "vostok-avto-gradient.png").convert("RGBA")
    nm = nm.resize((W, round(nm.height * W / nm.width)), Image.LANCZOS)
    text = "МЕЖДУНАРОДНАЯ ТРАНСПОРТНАЯ КОМПАНИЯ"
    f = ImageFont.truetype(BOOKMAN, round(W * 0.0405))
    ls = (W - f.getlength(text)) / (len(text) - 1)
    top, bot = f.getbbox("М")[1], f.getbbox("М")[3]
    gap = round(W * 0.03)
    H = nm.height + gap + (bot - top) + 4
    for name, col in (("b", None), ("w", (255, 255, 255, 255))):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        if col:
            wn = Image.new("RGBA", nm.size, col)
            wn.putalpha(nm.getchannel("A"))
            im.alpha_composite(wn)
        else:
            im.alpha_composite(nm)
        d = ImageDraw.Draw(im)
        for i, c in enumerate(text):
            d.text((f.getlength(text[:i]) + i * ls, nm.height + gap - top), c, font=f, fill=col or (0x2b, 0x57, 0x97, 255))
        im.save(IMG / f"name_{name}.png", optimize=True)
    return W // 3, round(H / 3)


NW = NH = 0


def logo_html(cls="logo"):
    return (f'<a class="{cls}" href="{u()}" aria-label="МТК Восток-Авто — на главную"><picture><source type="image/webp" srcset="{u("img/logo64.webp")} 1x, {u("img/logo128.webp")} 2x, {u("img/logo192.webp")} 3x">'
            f'<img class="lg" src="{u("img/logo128.png")}" alt="" width="64" height="64"></picture>'
            f'<span class="nm"><img class="w" src="{u("img/name_w.png")}" alt="Восток-Авто — международная транспортная компания" width="{NW}" height="{NH}">'
            f'<img class="b" src="{u("img/name_b.png")}" alt="" width="{NW}" height="{NH}"></span></a>')


ASSET_V = ""


def page(path, title, desc, body, active=None, jsonld=None, og=None, prio="0.6"):
    canon = SITE + u(path)
    menu = "".join(f'<a href="{u(p)}"{" class=\"on\"" if p == active else ""}>{t}</a>' for p, t in MENU)
    ld = "".join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>' for j in (jsonld or []))
    og_img = SITE + u(og or "img/og.jpg")
    cat_links = "".join(f'<a href="{u("katalog/?cat=" + k)}">{t}</a>' for k, t, *_ in DIRS)
    team_links = "".join(f'<a href="tel:+{re.sub(r"[^0-9]", "", p["tel"])}">{p["name"].split()[0]}: {nb(p["tel"])}</a>' for p in TEAM)
    s = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
{'<meta name="robots" content="noindex,nofollow">' if PREVIEW else ''}
<link rel="canonical" href="{canon}">
<meta property="og:type" content="website"><meta property="og:locale" content="ru_RU"><meta property="og:site_name" content="МТК Восток-Авто">
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}"><meta property="og:url" content="{canon}"><meta property="og:image" content="{og_img}">
<meta name="theme-color" content="#0b1f45">
<link rel="icon" type="image/png" href="{u("favicon.png")}"><link rel="apple-touch-icon" href="{u("apple-touch-icon.png")}">
<link rel="preload" href="{u("fonts/golos.woff2")}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{u("s.css")}?v={ASSET_V}">
{ld}
</head>
<body>
<header class="hdr" id="hdr"><div class="hrow">{logo_html()}<nav class="menu">{menu}</nav><a class="cta" href="{u("kontakty/")}">Написать специалисту</a>
<button class="burger" type="button" aria-label="Меню"><i></i><i></i></button></div></header>
<nav class="drawer"><a href="{u()}">Главная</a>{menu}<a class="btn w" href="{u("kontakty/")}">Написать специалисту</a></nav>
<main>
{body}
</main>
<footer><div class="wrap">
<div class="fcols">
<div>{logo_html()}<p class="fabout">Привозим новые и&nbsp;б/у автомобили из&nbsp;Китая под&nbsp;ключ: подбор, проверка, договор, доставка, растаможка и&nbsp;электронный ПТС. Работаем с&nbsp;Китаем с&nbsp;2016 года.</p></div>
<div><h4>Разделы</h4><nav>{"".join(f'<a href="{u(p)}">{t}</a>' for p, t in MENU)}</nav></div>
<div><h4>Каталог</h4><nav>{cat_links}<a href="{u("avto/")}">Авто в Китае</a></nav></div>
<div><h4>Связаться</h4><nav>{team_links}<a href="{CHANNEL}">Telegram-канал</a></nav></div>
</div>
<div class="fbot"><span>© {TODAY.year} МТК Восток-Авто · Международная транспортная компания</span><span>Цены под ключ пересчитаны {ddmm(TODAY)}</span></div>
</div></footer>
<script src="{u("s.js")}?v={ASSET_V}" defer></script>
</body>
</html>
"""
    dst = OUT / path / "index.html"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(s)
    PAGES.append((path, prio))


def crumbs(*items):
    out = [f'<a href="{u()}">Главная</a>']
    for href, t in items:
        out.append(f'<span><a href="{u(href)}">{t}</a></span>' if href else f'<span>{t}</span>')
    return f'<nav class="crumbs" aria-label="Навигация">{"".join(out)}</nav>'


def bc_ld(*items):
    el = [{"@type": "ListItem", "position": 1, "name": "Главная", "item": SITE + u()}]
    for i, (href, t) in enumerate(items, 2):
        el.append({"@type": "ListItem", "position": i, "name": html.unescape(re.sub("<[^>]+>", "", t)), "item": SITE + u(href)})
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": el}


ARROWS = ('<div class="arrows"><button type="button" data-reel="{id}" data-d="-1" aria-label="Назад"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M15 5l-7 7 7 7"/></svg></button>'
          '<button type="button" data-reel="{id}" data-d="1" aria-label="Вперёд"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M9 5l7 7-7 7"/></svg></button></div>')
SVG_L = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M15 5l-7 7 7 7"/></svg>'
SVG_R = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 5l7 7-7 7"/></svg>'


# ---------- данные: каталог ----------
# направление каталога: ключ, подпись, категория cars_data, фото раздела, топливо
DIRS = [("ev", "Электро", "ЭЛЕКТРО", 0, "ev"), ("hyb", "Гибриды", "ГИБРИДЫ", 1, "hybrid"),
        ("fwd", "Бензин", "МОНОПРИВОД", 2, "petrol"), ("awd", "Полный привод", "ПОЛНЫЙ ПРИВОД", 3, "petrol")]
DIR_TEXT = {"ev": "Новые электромобили, которые проходят по&nbsp;льготному утильсбору: 30-минутная мощность мотора до&nbsp;58,84&nbsp;кВт.",
            "hyb": "Гибриды Toyota с&nbsp;пробегом 3–5 лет: мощность системы до&nbsp;160&nbsp;л.с., утильсбор льготный.",
            "fwd": "Бензиновые машины 3–5 лет до&nbsp;160&nbsp;л.с.: Volkswagen, Toyota, Honda, Mazda, BMW, Audi и&nbsp;другие.",
            "awd": "Полный привод до&nbsp;160&nbsp;л.с. с&nbsp;пробегом 3–5 лет: Subaru и&nbsp;Mitsubishi под&nbsp;льготный утильсбор."}
FUEL_RU = {"ev": "Электро", "erev": "Гибрид EREV", "hybrid": "Гибрид", "petrol": "Бензин", "ice": "Бензин"}


def load_models():
    extra = json.loads((DATA / "models.json").read_text()) if (DATA / "models.json").exists() else {}
    out, seen = [], set()
    for key, label, cat, _, fuel in DIRS:
        c = next(x for x in cars_data.CATEGORIES if x["cat"] == cat)
        cond = "Новые" if "НОВ" in c.get("cond", "") else "С пробегом 3–5 лет"
        for p in c["pages"]:
            for m in p["cars"]:
                x = extra.get(m["name"], {})
                slug = x.get("slug") or slugify(m["name"])
                while slug in seen:
                    slug += "-2"
                seen.add(slug)
                f = fuel
                if "EREV" in m["engine"]:
                    f = "ev erev"
                photo = CARS_MTK / m["photo"] if (CARS_MTK / m["photo"]).exists() else CARS / m["photo"]
                brand_ = x.get("brand") or m["name"].split()[0]
                out.append(dict(m, slug=slug, dir=key, dir_label=label, fuel=f, cond=cond, awd=key == "awd", brand=brand_,
                                body=x.get("body"), size=x.get("size"), seats=x.get("seats"), china=x.get("china_name"),
                                desc=x.get("desc"), points=x.get("points") or [], src=photo, stem=Path(m["photo"]).stem))
    return out


def model_imgs(m):
    webp(m["src"], IMG / "m" / f'{m["stem"]}_c.webp', 720, 74)
    webp(m["src"], IMG / "m" / f'{m["stem"]}.webp', 1400, 78)


def model_card(m, vt=True):
    sp = " · ".join(x for x in (m["engine"], m["power"]) if x)
    tag = m["dir_label"] if m["dir"] != "fwd" else (m.get("body") or "Бензин").capitalize()
    return (f'<a class="card" href="{u("katalog/" + m["slug"] + "/")}"{" data-vt" if vt else ""} data-cat="{m["dir"]}" data-fuel="{m["fuel"]}" data-body="{E(m.get("body") or "")}"'
            f' data-brand="{E(m["brand"])}" data-price="{m["from"]}" data-name="{E(m["name"])}" data-q="{E((m["name"] + " " + (m.get("china") or "") + " " + m["plant"]).lower())}">'
            f'<div class="im"><img src="{u("img/m/" + m["stem"] + "_c.webp")}" alt="{E(m["name"])}" loading="lazy" width="720" height="424"><span class="tag">{E(tag)}</span></div>'
            f'<div class="t"><h3>{E(m["name"])}</h3><div class="sp">{E(sp)}</div>'
            f'<div class="pr">{price_range(m["from"], m["to"])}<small>ориентир под ключ</small></div></div></a>')


# ---------- данные: машины из КП ----------
CITY_IN = {"Санкт-Петербург": "в Санкт-Петербурге", "Екатеринбург": "в Екатеринбурге", "Пермь": "в Перми", "Ижевск": "в Ижевске",
           "Москва": "в Москве", "Казань": "в Казани"}


def load_kp(rates):
    p = DATA / "kp_cars.json"
    if not p.exists():
        return []
    spec = importlib.util.spec_from_file_location("mtk_price", NEW / "price.py")
    pm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pm)
    cars = [c for c in json.loads(p.read_text()) if not c.get("year") or c["year"] >= MIN_YEAR]
    for c in cars:
        r = pm.calc(c, rates["vtb"], rates["cny"], rates["eur"], TODAY)
        c["price"] = r
        c["total"] = r["total"]
        c["fuel_key"] = {"ice": "petrol", "hybrid": "hybrid", "ev": "ev", "erev": "erev"}.get(c.get("kind"), "petrol")
    cars.sort(key=lambda c: c["total"])
    return cars


def kp_imgs(c):
    d = IMG / "kp" / c["slug"]
    ph = [Path(x) for x in c.get("photos", []) if Path(x).exists()]
    c["imgs"] = []
    for i, src in enumerate(ph, 1):
        webp(src, d / f"{i}.webp", 1400, 72)
        webp(src, d / f"t{i}.webp", 320, 66)
        c["imgs"].append(i)
    if ph:
        webp(ph[0], d / "c.webp", 720, 72)


def kp_line(c):
    bits = []
    if c.get("mileage_km") is not None:
        bits.append(f'{c["mileage_km"]:,} км'.replace(",", " "))
    if c.get("kind") in ("ev", "erev"):
        if c.get("power_hp"):
            bits.append(f'{c["power_hp"]} л.с.')
        if c.get("range_km"):
            bits.append(f'{c["range_km"]} км хода')
    else:
        if c.get("volume_cc"):
            bits.append(f'{c["volume_cc"]} см³')
        if c.get("power_hp"):
            bits.append(f'{c["power_hp"]} л.с.')
    bits.append(c.get("fuel_label") or FUEL_RU.get(c["fuel_key"], ""))
    if c.get("drive"):
        bits.append(c["drive"] + " привод")
    return ", ".join(b for b in bits if b)


def kp_card(c, vt=True):
    city = c.get("city") or ""
    return (f'<a class="card" href="{u("avto/" + c["slug"] + "/")}"{" data-vt" if vt else ""} data-fuel="{c["fuel_key"]}" data-feat="{"awd" if c.get("awd") else ""}"'
            f' data-brand="{E(c.get("brand") or "")}" data-city="{E(city)}" data-price="{c["total"]}" data-year="{c.get("year") or 0}" data-km="{c.get("mileage_km") or 0}"'
            f' data-name="{E(c["title"])}" data-q="{E((c["title"] + " " + (c.get("brand") or "")).lower())}">'
            f'<div class="im"><img src="{u("img/kp/" + c["slug"] + "/c.webp")}" alt="{E(c["title"])}" loading="lazy" width="720" height="540"><span class="tag">{E(city)}</span></div>'
            f'<div class="t"><h3>{E(c["title"])} <span class="yr">{c.get("year") or ""}</span></h3><div class="sp">{E(kp_line(c))}</div>'
            f'<div class="pr">{rub(c["total"])}<small>под ключ {CITY_IN.get(city, "")} на&nbsp;{ddmm(TODAY)}</small></div></div></a>')


# ---------- общие блоки ----------
STEPS = [
    ("01", "Выбор автомобиля", "Выбираете модель из каталога или предлагаете свою, называете бюджет — мы подбираем несколько подходящих вариантов.", None, None),
    ("02", "Подбор и проверка", "Проверяем историю машины по базам Китая и по желанию её состояние на месте, присылаем отчёт, фото и видео.", None, "k_1"),
    ("03", "Договор и оплата", "Высылаем договор, контракт и инвойс. Оплата через банк ВТБ.", "Оплата 1 — предоплата 50 000 ₽<br>Оплата 2 — автомобиль, доставка, погрузка и комиссия банка", None),
    ("04", "Доставка", "Погрузка на автовоз, доставка до границы и дальше — в Ваш город.", None, "d_yaris_1"),
    ("05", "Документы", "Оформляем СБКТС и электронный ПТС.", None, None),
    ("06", "Таможня", "Растаможиваем автомобиль: помогаем оплатить пошлину и сборы, подсказываем суммы и реквизиты.", "Оплата 3 — пошлина, сборы, СВХ и оформление документов", "d_coolray_1"),
    ("07", "Выдача", "Получаете ключи, ЭПТС и таможенные документы и ставите машину на учёт.", "Оплата 4 — остаток 40 000 ₽ за подбор и сопровождение", "d_xrv_1"),
]
DELIV = [("xrv", "Honda XR-V 1.5 Comfort", "2022 · 33 889 км · бензин, 131 л.с.", "Санкт-Петербург", 1769998),
         ("q05", "Changan Qiyuan Q05 506Max", "2025 · 7 000 км · электро, 163 л.с.", "Ижевск", 2214339),
         ("yaris", "Toyota Yaris L 1.5", "2022 · 66 000 км · бензин, 107 л.с.", "Пермь", 1390144),
         ("coolray", "Geely Coolray 1.4T", "2022 · 13 500 км · бензин, 141 л.с.", "Санкт-Петербург", 1247044)]


def nbs(s):
    return s.replace(" — ", "&nbsp;— ").replace(" 000", "&nbsp;000").replace(" ₽", "&nbsp;₽")


def steps_track():
    out = []
    for n, h, p, pay, ph in STEPS:
        if ph:
            out.append(f'<div class="step ph"><img src="{u("img/" + ph + ".webp")}" alt="" loading="lazy"><div><div class="n">{n}</div><h3>{h}</h3><p>{nbs(p)}</p></div></div>')
        else:
            out.append(f'<div class="step"><div class="n">{n}</div><h3>{h}</h3><p>{nbs(p)}</p>' + (f'<div class="pay">{nbs(pay)}</div>' if pay else "") + '</div>')
    return "".join(out)


def deliv_cards():
    return "".join(
        f'<article class="dc rv"><img src="{u("img/d_" + k + "_1.webp")}" alt="{E(n)}" loading="lazy"><img src="{u("img/d_" + k + "_2.webp")}" alt="" loading="lazy">'
        f'<div class="t"><div><h3>{n}</h3><div class="sp">{s} · выдача: {c}</div></div><div class="pr">{rub(p)}<small>итог под ключ</small></div></div></article>'
        for k, n, s, c, p in DELIV)


def team_cards():
    out = []
    for p in TEAM:
        bt = f'<a href="https://t.me/{p["tg"]}">Telegram</a><a href="https://wa.me/{p["wa"]}">WhatsApp</a>'
        if p["mx"] and p["mx"] != "phone":
            bt += f'<a href="{MAX_HREF}">MAX</a>'
        tel = "+" + re.sub(r"\D", "", p["tel"])
        mx = '<span class="mx">Этот же номер — в MAX</span>' if p["mx"] == "phone" else ""
        out.append(f'<div class="who rv"><img src="{u("img/" + p["img"] + ".webp")}" alt="{p["name"]}" loading="lazy" width="96" height="96">'
                   f'<h3>{p["name"]}</h3><div class="r">{p["note"]}</div><a class="ph" href="tel:{tel}">{nb(p["tel"])}</a>{mx}<div class="bt">{bt}</div></div>')
    return "".join(out)


PAYS = f"""<div class="pays" id="pays">
<div class="pay4"><div class="c">1</div><h3>Предоплата</h3><div class="s">50&nbsp;000&nbsp;₽</div><p>При подписании договора&nbsp;— в&nbsp;счёт подбора и&nbsp;сопровождения сделки (всего 90&nbsp;000&nbsp;₽).</p></div>
<div class="pay4"><div class="c">2</div><h3>Оплата автомобиля</h3><div class="s">По&nbsp;курсу ВТБ</div><p>Через ВТБ по&nbsp;контракту и&nbsp;инвойсу. С&nbsp;этой оплаты автомобиль Ваш.</p><ul><li><b>Автомобиль</b> в&nbsp;Китае</li><li><b>Доставка</b> автовозом в&nbsp;Россию</li><li><b>Погрузка</b> и&nbsp;доставка по&nbsp;Китаю</li><li><b>Комиссия банка</b> 2%</li></ul></div>
<div class="pay4"><div class="c">3</div><h3>Таможня</h3><div class="s">По&nbsp;прибытии</div><p>Пошлина, сборы, склад временного хранения и&nbsp;оформление документов.</p><ul><li><b>Утильсбор</b> льготный: 3&nbsp;400&nbsp;₽ до&nbsp;3&nbsp;лет, 5&nbsp;200&nbsp;₽ от&nbsp;3 до&nbsp;5</li><li><b>СБКТС и ЭПТС</b>, растаможка&nbsp;— 80&nbsp;000&nbsp;₽</li></ul></div>
<div class="pay4"><div class="c">4</div><h3>При выдаче</h3><div class="s">40&nbsp;000&nbsp;₽</div><p>Остаток за&nbsp;подбор и&nbsp;сопровождение. Получаете ключи, ЭПТС и&nbsp;таможенные документы.</p></div>
</div>"""


def faq_items(items):
    return "".join(f'<details class="qa"><summary>{E(q["q"])}</summary><div class="a">{"".join("<p>" + E(x) + "</p>" for x in q["a"].split(chr(10)) if x.strip())}</div></details>' for q in items)


def faq_ld(items):
    return {"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q["q"], "acceptedAnswer": {"@type": "Answer", "text": q["a"]}} for q in items]}


def fin_block():
    return f"""<section class="fin"><picture><source media="(max-width:760px)" srcset="{u("img/road_m.webp")}"><img class="bg" id="finbg" src="{u("img/road.webp")}" alt="" loading="lazy"></picture>
<div class="wrap"><h2 class="rv">Ваш автомобиль<br>из&nbsp;Китая. Под&nbsp;ключ.</h2><p class="rv d1">Новые машины, подборки и&nbsp;выданные автомобили&nbsp;— в&nbsp;нашем Telegram-канале.</p>
<div class="btns rv d2"><a class="btn w" href="{CHANNEL}">Telegram-канал <span class="ar">→</span></a><a class="btn o" href="{u("kontakty/")}">Написать специалисту</a></div></div></section>"""


ORG = {"@context": "https://schema.org", "@type": "AutoDealer", "name": "МТК Восток-Авто", "alternateName": "Международная транспортная компания «Восток-Авто»",
       "url": SITE + "/", "logo": SITE + BASE + "img/logo192.webp", "foundingDate": "2016",
       "description": "Подбор, проверка, доставка и растаможка новых и б/у автомобилей из Китая под ключ для частных покупателей.",
       "areaServed": "RU", "telephone": TEAM[0]["tel"], "sameAs": [CHANNEL]}


# ---------- страницы ----------
def home(models, kp, rates, faq):
    slides, dots = [], []
    for i, k in enumerate((2, 1, 3)):
        webp(CARS / f"hero_sec{k}.jpg", IMG / f"hero{k}.webp", 2200, 74)
        webp(CARS / f"hero_sec{k}.jpg", IMG / f"hero{k}_m.webp", 1400, 74)
        slides.append(f'<picture><source media="(max-width:760px)" srcset="{u(f"img/hero{k}_m.webp")}"><img src="{u(f"img/hero{k}.webp")}" alt="" '
                      f'{"fetchpriority=\"high\"" if i == 0 else "loading=\"lazy\""} width="2200" height="1228"></picture>')
        dots.append("<i></i>")
    decks = []
    for i, (key, label, cat, sec, _) in enumerate(DIRS):
        ms = [m for m in models if m["dir"] == key]
        webp(CARS / f"hero_sec{sec}.jpg", IMG / f"sec{sec}.webp", 2200, 74)
        webp(CARS / f"hero_sec{sec}.jpg", IMG / f"sec{sec}_m.webp", 1100, 74)
        names = "".join(f"<span>{E(m['name'])}</span>" for m in ms[:6])
        lo = min(m["from"] for m in ms)
        decks.append(f'<section class="deck"><picture><source media="(max-width:760px)" srcset="{u(f"img/sec{sec}_m.webp")}"><img src="{u(f"img/sec{sec}.webp")}" alt="{label}" loading="lazy"></picture>'
                     f'<div class="wrap"><div class="n">{i + 1:02d} / 04 · {len(ms)} {plural(len(ms), "модель", "модели", "моделей")}</div><h2>{label}</h2><p>{DIR_TEXT[key]}</p>'
                     f'<div class="ms">{names}</div><div class="row"><a class="btn w" href="{u("katalog/?cat=" + key)}">Смотреть {len(ms)} {plural(len(ms), "модель", "модели", "моделей")} <span class="ar">→</span></a>'
                     f'<div class="pr">от {mln(lo)} млн ₽<small>ориентир под ключ</small></div></div></div></section>')
    reel = ""
    if kp:
        pick = sorted(kp, key=lambda c: c.get("kp_date_iso", ""), reverse=True)[:12]
        reel = f"""<section class="sec dark" id="avto">
<div class="wrap shead"><div><p class="kick l rv">Авто в Китае</p><h2 class="h2 rv d1">Реальные машины<br><em>с&nbsp;ценой на&nbsp;сегодня</em></h2>
<p class="lead rv d2">Конкретные автомобили, которые мы нашли и&nbsp;посчитали для&nbsp;клиентов. Цена под&nbsp;ключ пересчитывается каждый день по&nbsp;курсу юаня.</p></div>{ARROWS.format(id="reel1")}</div>
<div class="reel" id="reel1">{"".join(kp_card(c) for c in pick)}</div>
<div class="wrap"><a class="more" href="{u("avto/")}">Все {len(kp)} {plural(len(kp), "машина", "машины", "машин")} с&nbsp;ценой <span class="ar">→</span></a></div></section>"""
    faq5 = [q for q in faq if not q.get("confirm")][:6]
    body = f"""
<section class="hero" id="top">
  <div class="slides">{"".join(slides)}</div><div class="shade"></div>
  <div class="wrap hc" id="hc">
    <p class="kick l">МТК Восток-Авто · с 2016 года</p>
    <h1>Автомобили из&nbsp;Китая.<br><span>Под ключ.</span></h1>
    <p class="sub">Новые и&nbsp;б/у под&nbsp;льготный утильсбор. Подбираем, проверяем, везём, растаможиваем и&nbsp;передаём Вам с&nbsp;электронным ПТС.</p>
    <div class="btns"><a class="btn w" href="{u("katalog/")}">Смотреть каталог <span class="ar">→</span></a><a class="btn o" href="{u("avto/")}">Авто в Китае</a></div>
    <a class="rate" href="{u("stoimost/")}"><i></i>Курс юаня для расчёта на&nbsp;{ddmm(TODAY)}: <b>{f"{rates['vtb']:.2f}".replace(".", ",")}&nbsp;₽</b></a>
  </div>
  <div class="dots">{"".join(dots)}</div><div class="hint" aria-hidden="true"></div>
</section>
<section class="intro"><div class="wrap">
  <p class="words" id="words">Автомобиль из&nbsp;Китая&nbsp;— это не&nbsp;только цена в&nbsp;объявлении. Это *проверка,* *договор,* *доставка,* *таможня* и&nbsp;*документы.* Всё это&nbsp;— наша работа: от&nbsp;выбора модели до&nbsp;выдачи ключей.</p>
  <div class="stats">
    <div class="rv"><b>50–65</b><span>дней от&nbsp;оплаты до&nbsp;выдачи&nbsp;— ориентир по&nbsp;договору</span></div>
    <div class="rv d1"><b data-n="{len(models)}">{len(models)}</b><span>моделей в&nbsp;каталоге под&nbsp;льготный утильсбор</span></div>
    <div class="rv d2"><b data-n="{len(kp) or 7}">{len(kp) or 7}</b><span>{"машин из&nbsp;Китая с&nbsp;ценой на&nbsp;сегодня" if kp else "этапов от&nbsp;выбора до&nbsp;постановки на&nbsp;учёт"}</span></div>
    <div class="rv d3"><b data-n="2016" data-from="1990">2016</b><span>с&nbsp;этого года работаем с&nbsp;Китаем</span></div>
  </div>
</div></section>
<div class="decks">{"".join(decks)}</div>
{reel}
<section class="grow" id="grow"><div class="st"><div class="fr" id="fr">
  <picture><source media="(max-width:760px)" srcset="{u("img/road_m.webp")}"><img src="{u("img/road.webp")}" alt="Дорога из Китая в Россию" loading="lazy"></picture>
  <div class="gt wrap"><p class="kick l">Доставка</p><h2>Из&nbsp;Китая&nbsp;—<br>в&nbsp;ваш город</h2><p>Санкт-Петербург, Екатеринбург, Пермь, Ижевск и&nbsp;другие города. Автовозом до&nbsp;границы и&nbsp;дальше&nbsp;— к&nbsp;Вам.</p></div>
</div></div></section>
<section class="how" id="how"><div class="st">
  <div class="wrap hh"><div><p class="kick">Как проходит сделка</p><h2 class="h2">Семь шагов<br>от&nbsp;выбора <em>до&nbsp;ключей</em></h2></div>
  <p>Срок от&nbsp;оплаты до&nbsp;выдачи&nbsp;— обычно 50–65&nbsp;дней. <a class="more" href="{u("kak-kupit/")}">Подробно <span class="ar">→</span></a></p></div>
  <div class="track" id="track">{steps_track()}</div><div class="wrap"><div class="prog" id="prog"><i></i></div></div>
</div></section>
<section class="sec"><div class="wrap">
  <p class="kick rv">Стоимость</p><h2 class="h2 rv d1">Одна цена&nbsp;— <em>под&nbsp;ключ</em></h2>
  <p class="lead rv d2">Автомобиль, доставка, растаможка, документы и&nbsp;наши услуги. Платите в&nbsp;четыре этапа по&nbsp;договору, без&nbsp;скрытых платежей.</p>
  {PAYS}
  <p class="note rv"><a class="more" href="{u("stoimost/")}">Из&nbsp;чего складывается цена и&nbsp;курс на&nbsp;сегодня <span class="ar">→</span></a></p>
</div></section>
<section class="sec bg" id="delivered"><div class="wrap">
  <div class="shead"><div><p class="kick rv">Наша работа</p><h2 class="h2 rv d1">Выданные <em>автомобили</em></h2></div><a class="more rv" href="{u("vydannye/")}">Все выданные <span class="ar">→</span></a></div>
  <div class="dgrid">{deliv_cards()}</div>
</div></section>
<section class="sec"><div class="wrap">
  <div class="shead"><div><p class="kick rv">Вопросы</p><h2 class="h2 rv d1">Что спрашивают <em>чаще всего</em></h2></div><a class="more rv" href="{u("voprosy/")}">Все вопросы <span class="ar">→</span></a></div>
  <div class="faq rv">{faq_items(faq5)}</div>
</div></section>
<section class="sec bg" id="contacts"><div class="wrap">
  <p class="kick rv">Связаться</p><h2 class="h2 rv d1">Напишите <em>специалисту</em></h2>
  <p class="lead rv d2">Расскажите, какую машину и&nbsp;в&nbsp;какой город хотите,&nbsp;— подберём варианты и&nbsp;посчитаем стоимость под&nbsp;ключ.</p>
  <div class="tgrid">{team_cards()}</div>
</div></section>
{fin_block()}"""
    page("", "МТК Восток-Авто — автомобили из Китая под ключ: каталог, цены, доставка",
         f"Новые и б/у автомобили из Китая под льготный утильсбор: {len(models)} моделей в каталоге, реальные машины с ценой под ключ на сегодня, проверка, договор, доставка, растаможка, ЭПТС.",
         body, jsonld=[ORG, faq_ld(faq5)] if faq5 else [ORG], prio="1.0")


def catalog_page(models):
    tiles = "".join(f'<button class="tile" type="button" data-v="{k}"><img src="{u(f"img/sec{sec}_m.webp")}" alt="" loading="lazy"><div><b>{t}</b>'
                    f'<small>{sum(m["dir"] == k for m in models)} {plural(sum(m["dir"] == k for m in models), "модель", "модели", "моделей")}</small></div></button>'
                    for k, t, _, sec, _ in DIRS)
    bodies = sorted({m["body"] for m in models if m.get("body")}, key=lambda b: -sum(m.get("body") == b for m in models))
    brands = sorted({m["brand"] for m in models})
    pmax = math.ceil(max(m["from"] for m in models) / 1e5) * 1e5
    body = f"""
<section class="phead"><div class="wrap">{crumbs((None, "Каталог"))}
<h1 class="rv in">{len(models)} моделей<br>под <em>льготный утильсбор</em></h1>
<p class="lead">Цена в&nbsp;карточке&nbsp;— ориентир под&nbsp;ключ. Точную сумму на&nbsp;конкретный автомобиль считаем по&nbsp;курсу дня. Не&nbsp;нашли свою модель&nbsp;— привезём любую под&nbsp;заказ.</p>
<div class="tiles" data-f="cat">{tiles}</div></div></section>
<section class="sec tight"><div class="wrap lay">
<aside class="flt" aria-label="Фильтры">
<h4>Поиск</h4><input type="search" data-f="q" placeholder="Модель или марка">
<h4>Кузов</h4><div class="chips" data-f="body">{"".join(f'<button class="chip" type="button" data-v="{E(b)}">{E(b.capitalize())}</button>' for b in bodies)}</div>
<h4>Марка</h4><select data-f="brand"><option value="">Любая</option>{"".join(f"<option>{E(b)}</option>" for b in brands)}</select>
<h4>Цена под ключ</h4><input type="range" data-f="price" min="1000000" max="{int(pmax)}" step="100000" value="{int(pmax)}"><div class="rng"><span>до</span><b data-out="price">любая</b></div>
<button class="btn ob sm reset" type="button" data-reset>Сбросить фильтры</button>
<button class="btn b sm reset fbtn" type="button" data-fopen>Показать</button>
</aside>
<div>
<div class="lhead"><span class="cnt">Найдено: <b id="cnt">{len(models)}</b></span><span style="display:flex;gap:10px"><button class="btn ob sm fbtn" type="button" data-fopen>Фильтры</button>
<select data-sort aria-label="Сортировка"><option value="price-asc">Сначала дешевле</option><option value="price-desc">Сначала дороже</option><option value="name-asc">По названию</option></select></span></div>
<div class="list" data-list>{"".join(model_card(m) for m in models)}</div>
<p class="empty" id="empty">По&nbsp;таким условиям моделей нет. <a class="more" href="#" data-reset>Сбросить фильтры</a></p>
<p class="note">Цены&nbsp;— ориентир под&nbsp;ключ в&nbsp;Санкт-Петербурге: автомобиль, доставка, растаможка, документы и&nbsp;наши услуги. Курс юаня в&nbsp;каталоге&nbsp;— на&nbsp;дату выпуска каталога; точную цену конкретной машины считаем по&nbsp;курсу дня.</p>
</div></div></section>
{fin_block()}"""
    ld = [bc_ld(("katalog/", "Каталог")),
          {"@context": "https://schema.org", "@type": "ItemList", "name": "Каталог автомобилей из Китая под льготный утильсбор",
           "itemListElement": [{"@type": "ListItem", "position": i, "url": SITE + u("katalog/" + m["slug"] + "/"), "name": m["name"]} for i, m in enumerate(models, 1)]}]
    page("katalog/", f"Каталог автомобилей из Китая под ключ — {len(models)} моделей под льготный утильсбор | МТК Восток-Авто",
         "Электромобили, гибриды, бензиновые и полноприводные машины из Китая с ценой под ключ: фильтры по кузову, марке и бюджету.",
         body, active="katalog/", jsonld=ld, prio="0.9")


def model_page(m, models, kp):
    found = [c for c in kp if c.get("catalog_name") == m["name"]]
    same = [x for x in models if x["dir"] == m["dir"] and x["slug"] != m["slug"]]
    same.sort(key=lambda x: abs(x["from"] - m["from"]))
    tags = [m["dir_label"] if m["dir"] != "fwd" else "Бензин", (m.get("body") or "").capitalize(), m["cond"], "Полный привод" if m["awd"] else None]
    if "erev" in m["fuel"]:
        tags[0] = "Электро и EREV"
    util = ("3&nbsp;400&nbsp;₽ — льготный: 30-минутная мощность мотора до&nbsp;58,84&nbsp;кВт" if m["dir"] == "ev"
            else "5&nbsp;200&nbsp;₽ — льготный: возраст 3–5 лет, до&nbsp;160&nbsp;л.с.")
    rows = [("Двигатель", E(m["engine"])), ("Мощность" + (" и запас хода" if m["dir"] == "ev" else ""), E(m["power"])),
            ("Производитель", E(m["plant"])), ("Кузов", E((m.get("body") or "").capitalize()) or None),
            ("Мест", str(m["seats"]) if m.get("seats") else None), ("Состояние", m["cond"]), ("Утильсбор", util),
            ("Срок", "50–65 дней от&nbsp;оплаты до&nbsp;выдачи"), ("Цена под ключ", price_range(m["from"], m["to"]))]
    spec = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows if v)
    desc = (f'<p class="desc">{E(m["desc"])}</p>' if m.get("desc") else
            f'<p class="desc">{E(m["name"])} — {m["dir_label"].lower()} из&nbsp;Китая под&nbsp;льготный утильсбор. Подберём конкретную машину, проверим и&nbsp;привезём под&nbsp;ключ.</p>')
    pts = "".join(f"<li>{E(p)}</li>" for p in m["points"])
    fblock = ""
    if found:
        fblock = f"""<section class="sec bg" id="found"><div class="wrap"><p class="kick rv">Авто в Китае</p>
<h2 class="h2 rv d1">{E(m["name"])}: <em>найденные машины</em></h2><p class="lead rv d2">Конкретные автомобили этой модели, которые мы нашли и&nbsp;посчитали. Цена под&nbsp;ключ&nbsp;— по&nbsp;курсу на&nbsp;{ddmm(TODAY)}.</p>
<div class="grid" style="margin-top:46px">{"".join(kp_card(c) for c in found[:6])}</div>
{f'<p class="note"><a class="more" href="{u("avto/?q=" + E(m["name"].split()[1].lower()))}">Все машины этой модели <span class="ar">→</span></a></p>' if len(found) > 6 else ""}</div></section>"""
    body = f"""
<section class="mhero"><div class="wrap">{crumbs(("katalog/", "Каталог"), ("katalog/?cat=" + m["dir"], m["dir_label"]), (None, E(m["name"])))}
<div class="mgrid"><div>
<h1>{E(m["name"])}</h1>{f'<p class="cn">{E(m["china"])}</p>' if m.get("china") else f'<p class="cn">{E(m["plant"])}</p>'}
<div class="tags">{"".join(f"<span>{E(t)}</span>" for t in tags if t)}</div>
<div class="big">{price_range(m["from"], m["to"])}<small>ориентир под&nbsp;ключ в&nbsp;Санкт-Петербурге</small></div>
<div class="btns"><a class="btn w" href="{u("kontakty/")}">Подобрать такую машину <span class="ar">→</span></a>{f'<a class="btn o" href="#found">Найденные машины · {len(found)}</a>' if found else ""}</div>
</div><div class="mpic"><img src="{u("img/m/" + m["stem"] + ".webp")}" alt="{E(m["name"])}" width="1400" height="824"></div></div>
</div></section>
<section class="sec"><div class="wrap cols">
<div class="rv">{desc}<ul class="pts">{pts}</ul>
<p class="note">Фото&nbsp;— пример модели. Цвет, комплектация и&nbsp;год конкретной машины&nbsp;— по&nbsp;Вашему запросу: присылаем фото, отчёт о&nbsp;проверке и&nbsp;итог до&nbsp;рубля.</p></div>
<div class="rv d1"><table class="spec">{spec}</table></div>
</div></section>
{fblock}
<section class="sec"><div class="wrap"><div class="shead"><div><p class="kick rv">Похожие модели</p><h2 class="h2 rv d1">{m["dir_label"]}: <em>ещё варианты</em></h2></div>
<a class="more rv" href="{u("katalog/?cat=" + m["dir"])}">Весь раздел <span class="ar">→</span></a></div>
<div class="grid" style="margin-top:46px">{"".join(model_card(x) for x in same[:3])}</div></div></section>
{fin_block()}"""
    ld = [bc_ld(("katalog/", "Каталог"), ("katalog/" + m["slug"] + "/", m["name"])),
          {"@context": "https://schema.org", "@type": "Product", "name": m["name"] + " из Китая под ключ", "brand": {"@type": "Brand", "name": m["brand"]},
           "image": SITE + u("img/m/" + m["stem"] + ".webp"), "description": html.unescape(re.sub("<[^>]+>", "", m.get("desc") or DIR_TEXT[m["dir"]])),
           "category": m["dir_label"],
           "offers": {"@type": "AggregateOffer", "priceCurrency": "RUB", "lowPrice": m["from"], "highPrice": m["to"] or m["from"],
                      "offerCount": max(1, len(found)), "availability": "https://schema.org/PreOrder", "seller": {"@type": "Organization", "name": "МТК Восток-Авто"}}}]
    page(f'katalog/{m["slug"]}/', f'{m["name"]} из Китая под ключ — {html.unescape(price_range(m["from"], m["to"]))} | МТК Восток-Авто',
         f'{m["name"]} из Китая под льготный утильсбор: {m["engine"]}, {m["power"]}. Цена под ключ {html.unescape(price_range(m["from"], m["to"]))}, подбор, проверка, доставка и растаможка.',
         body, active="katalog/", jsonld=ld, og="img/m/" + m["stem"] + ".webp", prio="0.8")


def avto_page(kp, rates):
    brands = sorted({c.get("brand") or "" for c in kp} - {""})
    cities = sorted({c.get("city") or "" for c in kp} - {""})
    years = sorted({c.get("year") for c in kp if c.get("year")})
    pmax = math.ceil(max(c["total"] for c in kp) / 1e5) * 1e5
    fuels = [(k, t) for k, t in (("petrol", "Бензин"), ("hybrid", "Гибрид"), ("ev", "Электро"), ("erev", "Гибрид EREV")) if any(c["fuel_key"] == k for c in kp)]
    body = f"""
<section class="phead"><div class="wrap">{crumbs((None, "Авто в Китае"))}
<h1 class="rv in">Авто в&nbsp;Китае<br><em>с&nbsp;ценой на&nbsp;сегодня</em></h1>
<p class="lead">Реальные машины, которые мы нашли и&nbsp;посчитали для&nbsp;клиентов летом и&nbsp;осенью. Цена под&nbsp;ключ пересчитана {ddmm(TODAY)} по&nbsp;курсу юаня {f"{rates['vtb']:.2f}".replace(".", ",")}&nbsp;₽. Если машину уже продали&nbsp;— найдём такую&nbsp;же.</p>
</div></section>
<section class="sec tight"><div class="wrap lay">
<aside class="flt" aria-label="Фильтры">
<h4>Поиск</h4><input type="search" data-f="q" placeholder="Модель или марка">
<h4>Топливо</h4><div class="chips" data-f="fuel">{"".join(f'<button class="chip" type="button" data-v="{k}">{t}</button>' for k, t in fuels)}</div>
<h4>Привод</h4><div class="chips" data-f="feat"><button class="chip" type="button" data-v="awd">Только полный</button></div>
<h4>Марка</h4><select data-f="brand"><option value="">Любая</option>{"".join(f"<option>{E(b)}</option>" for b in brands)}</select>
<h4>Цена под ключ</h4><input type="range" data-f="price" min="1000000" max="{int(pmax)}" step="100000" value="{int(pmax)}"><div class="rng"><span>до</span><b data-out="price">любая</b></div>
<h4>Год и пробег</h4><div class="two"><select data-f="ymin"><option value="">Год от</option>{"".join(f'<option value="{y}">{y}</option>' for y in years)}</select>
<select data-f="kmmax"><option value="">Пробег до</option>{"".join(f'<option value="{k}">{k // 1000} тыс. км</option>' for k in (10000, 30000, 50000, 80000, 120000))}</select></div>
<h4>Город выдачи</h4><select data-f="city"><option value="">Любой</option>{"".join(f"<option>{E(c)}</option>" for c in cities)}</select>
<button class="btn ob sm reset" type="button" data-reset>Сбросить фильтры</button>
<button class="btn b sm reset fbtn" type="button" data-fopen>Показать</button>
</aside>
<div>
<div class="lhead"><span class="cnt">Найдено: <b id="cnt">{len(kp)}</b></span><span style="display:flex;gap:10px"><button class="btn ob sm fbtn" type="button" data-fopen>Фильтры</button>
<select data-sort aria-label="Сортировка"><option value="price-asc">Сначала дешевле</option><option value="price-desc">Сначала дороже</option><option value="year-desc">Сначала новее</option><option value="km-asc">Меньше пробег</option></select></span></div>
<div class="list" data-list>{"".join(kp_card(c) for c in kp)}</div>
<p class="empty" id="empty">По&nbsp;таким условиям машин нет. <a class="more" href="#" data-reset>Сбросить фильтры</a></p>
<p class="note">Цена под&nbsp;ключ: автомобиль, доставка, комиссия банка, пошлина и&nbsp;сборы, утильсбор, СБКТС и&nbsp;ЭПТС, склад и&nbsp;наши услуги. Курс юаня меняется каждый день&nbsp;— вместе с&nbsp;ним меняется и&nbsp;цена. Объявления в&nbsp;Китае живут недолго: если машину продали, подберём такую&nbsp;же по&nbsp;году, пробегу и&nbsp;цене.</p>
</div></div></section>
{fin_block()}"""
    ld = [bc_ld(("avto/", "Авто в Китае")),
          {"@context": "https://schema.org", "@type": "ItemList", "name": "Автомобили из Китая с ценой под ключ",
           "itemListElement": [{"@type": "ListItem", "position": i, "url": SITE + u("avto/" + c["slug"] + "/"), "name": c["title"]} for i, c in enumerate(kp, 1)]}]
    page("avto/", "Авто из Китая с ценой под ключ на сегодня — реальные машины | МТК Восток-Авто",
         f"{len(kp)} реальных машин из Китая с фото и ценой под ключ, пересчитанной по курсу юаня на {ddmm(TODAY)}. Фильтры по марке, топливу, приводу, году и пробегу.",
         body, active="avto/", jsonld=ld, prio="0.9")


def car_page(c, kp, models, rates):
    city = c.get("city") or ""
    imgs, sl = c["imgs"], c["slug"]
    main = "".join(f'<img {"src" if i == 1 else "data-src"}="{u(f"img/kp/{sl}/{i}.webp")}" alt="{E(c["title"])}, фото {i}"{"" if i == 1 else " loading=\"lazy\""}>' for i in imgs)
    th = "".join(f'<img src="{u(f"img/kp/{sl}/t{i}.webp")}" alt="" loading="lazy">' for i in imgs)
    p = c["price"]
    brk = "".join(f"<tr><td>{E(k)}</td><td>{rub(v)}</td></tr>" for k, v in p["lines"])
    kv = [("Год", c.get("year")), ("Пробег", f'{c["mileage_km"]:,} км'.replace(",", " ") if c.get("mileage_km") is not None else None),
          ("Двигатель", (f'{c["volume_cc"] / 1000:.1f} л'.replace(".", ",") if c.get("volume_cc") else c.get("fuel_label"))),
          ("Мощность", f'{c["power_hp"]} л.с.' if c.get("power_hp") else None)]
    rows = [("Год выпуска", f'{c["year"]}' + (f', {c["month"]:02d} месяц' if c.get("month") else "") if c.get("year") else None),
            ("Пробег", kv[1][1]), ("Топливо", c.get("fuel_label")), ("Объём двигателя", f'{c["volume_cc"]} см³' if c.get("volume_cc") else None),
            ("Мощность", f'{c["power_hp"]} л.с.' + (f' ({c["power_kw"]} кВт)' if c.get("power_kw") else "") if c.get("power_hp") else None),
            ("Батарея", f'{c["battery_kwh"]} кВт·ч' if c.get("battery_kwh") else None), ("Запас хода", f'{c["range_km"]} км' if c.get("range_km") else None),
            ("Коробка", c.get("transmission")), ("Привод", c.get("drive")), ("Кузов", (c.get("body") or "").capitalize() or None), ("Цвет", c.get("color")),
            ("Комплектация", c.get("trim")), ("Цена в Китае", f'{c["car_cny"]:,} ¥'.replace(",", " ") if c.get("car_cny") else None),
            ("Город выдачи", city)]
    spec = "".join(f"<tr><th>{k}</th><td>{E(str(v))}</td></tr>" for k, v in rows if v)
    model = next((m for m in models if m["name"] == c.get("catalog_name")), None)
    sim = [x for x in kp if x["slug"] != c["slug"] and (x.get("catalog_name") == c.get("catalog_name") and c.get("catalog_name"))]
    sim += [x for x in kp if x["slug"] != c["slug"] and x not in sim and x.get("brand") == c.get("brand")]
    sim += sorted([x for x in kp if x["slug"] != c["slug"] and x not in sim], key=lambda x: abs(x["total"] - c["total"]))
    body = f"""
<section class="phead"><div class="wrap">{crumbs(("avto/", "Авто в Китае"), (None, E(c["title"])))}
<h1 class="rv in">{E(c["title"])} <em>{c.get("year") or ""}</em></h1>
<div class="kv">{"".join(f"<div><small>{k}</small><b>{E(str(v))}</b></div>" for k, v in kv if v)}</div>
</div></section>
<section class="sec tight"><div class="wrap cols">
<div><div class="gal"><div class="gmain">{main}<span class="gn"></span><button class="pv" type="button" aria-label="Предыдущее фото">{SVG_L}</button><button class="nx" type="button" aria-label="Следующее фото">{SVG_R}</button></div>
<div class="gth">{th}</div></div>
<h2 class="h2" style="font-size:clamp(28px,2.6vw,38px);margin-top:50px">Характеристики</h2><table class="spec" style="margin-top:20px">{spec}</table>
{f'<p class="note"><a class="more" href="{u("katalog/" + model["slug"] + "/")}">О модели {E(model["name"])} в каталоге <span class="ar">→</span></a></p>' if model else ""}</div>
<div><div class="box pbox"><p class="kick">Итого под ключ {CITY_IN.get(city, "")}</p><div class="tot">{rub(p["total"])}</div>
<p class="rt">По&nbsp;курсу юаня {f"{rates['vtb']:.2f}".replace(".", ",")}&nbsp;₽ на&nbsp;{ddmm(TODAY)}. Цена пересчитывается каждый день.</p>
<details><summary>Из чего складывается цена</summary><table class="brk">{brk}</table></details>
<div class="btns"><a class="btn b" href="{u("kontakty/")}">Заказать этот автомобиль</a><a class="btn ob" href="{u("kontakty/")}">Подобрать похожий</a></div>
<p class="sold">Объявления в&nbsp;Китае живут недолго. Если эту машину уже продали, найдём такую&nbsp;же: год, пробег и&nbsp;цена будут близки.</p></div></div>
</div></section>
<section class="sec bg"><div class="wrap"><div class="shead"><div><p class="kick rv">Похожие авто</p><h2 class="h2 rv d1">Ещё варианты <em>с&nbsp;ценой</em></h2></div>{ARROWS.format(id="reel2")}</div></div>
<div class="reel" id="reel2">{"".join(kp_card(x, vt=True) for x in sim[:10])}</div></section>
<div class="lbox"><img alt=""><button class="x" type="button" aria-label="Закрыть"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
<button class="pv" type="button" aria-label="Назад">{SVG_L}</button><button class="nx" type="button" aria-label="Вперёд">{SVG_R}</button></div>"""
    ld = [bc_ld(("avto/", "Авто в Китае"), ("avto/" + c["slug"] + "/", c["title"])),
          {"@context": "https://schema.org", "@type": ["Product", "Car"], "name": f'{c["title"]} {c.get("year") or ""}'.strip(),
           "brand": {"@type": "Brand", "name": c.get("brand") or ""}, "model": c.get("model"), "vehicleModelDate": str(c.get("year") or ""),
           "mileageFromOdometer": {"@type": "QuantitativeValue", "value": c.get("mileage_km"), "unitCode": "KMT"},
           "fuelType": c.get("fuel_label"), "image": [SITE + u(f'img/kp/{c["slug"]}/{i}.webp') for i in imgs[:5]],
           "offers": {"@type": "Offer", "priceCurrency": "RUB", "price": p["total"], "priceValidUntil": (TODAY + timedelta(days=1)).isoformat(),
                      "availability": "https://schema.org/PreOrder", "seller": {"@type": "Organization", "name": "МТК Восток-Авто"}}}]
    page(f'avto/{c["slug"]}/', f'{c["title"]} {c.get("year") or ""} из Китая — {html.unescape(rub(p["total"]))} под ключ | МТК Восток-Авто',
         f'{c["title"]} {c.get("year") or ""}, {html.unescape(kp_line(c))}. Цена под ключ {CITY_IN.get(city, "")} на {ddmm(TODAY)}: {html.unescape(rub(p["total"]))}. Фото, характеристики и расчёт.',
         body, active="avto/", jsonld=ld, og=f'img/kp/{c["slug"]}/1.webp', prio="0.7")


def how_page(faq):
    tl = []
    for n, h, p, pay, ph in STEPS:
        img = ph or {"01": "sec2", "03": "d_q05_2", "05": "d_xrv_2"}.get(n)
        tl.append(f'<div class="ts rv"><div class="c">{n}</div><div><h3>{h}</h3><p>{nbs(p)}</p>{f"<span class=pay>{nbs(pay)}</span>" if pay else ""}</div>'
                  f'<div class="ph"><img src="{u("img/" + (img + "_m" if img.startswith("sec") else img) + ".webp")}" alt="" loading="lazy"></div></div>')
    docs = ["Договор на&nbsp;подбор и&nbsp;сопровождение", "Контракт и&nbsp;инвойс от&nbsp;продавца", "Чек об&nbsp;оплате через ВТБ", "Таможенные документы",
            "СБКТС и&nbsp;электронный ПТС", "Ключи и&nbsp;всё, что положено к&nbsp;машине"]
    qs = [q for q in faq if q.get("group") in ("О компании и договоре", "Сроки и доставка") and not q.get("confirm")][:5]
    body = f"""
<section class="phead"><div class="wrap">{crumbs((None, "Как купить"))}
<h1 class="rv in">Как купить автомобиль<br><em>из&nbsp;Китая под&nbsp;ключ</em></h1>
<p class="lead">Семь шагов от&nbsp;выбора до&nbsp;ключей. Срок от&nbsp;оплаты до&nbsp;выдачи&nbsp;— обычно 50–65&nbsp;дней. На&nbsp;каждом шаге Вы знаете, что уже сделано и&nbsp;что дальше.</p></div></section>
<section class="sec tight"><div class="wrap"><div class="tl">{"".join(tl)}</div></div></section>
<section class="sec bg"><div class="wrap cols"><div><p class="kick rv">Документы</p><h2 class="h2 rv d1">Что Вы <em>получаете</em></h2>
<p class="lead rv d2">Все платежи&nbsp;— по&nbsp;договору и&nbsp;через банк. После выдачи машину ставят на&nbsp;учёт в&nbsp;ГИБДД как обычную.</p></div>
<ul class="pts rv d1">{"".join(f"<li>{d}</li>" for d in docs)}</ul></div></section>
{f'<section class="sec"><div class="wrap"><p class="kick rv">Вопросы</p><h2 class="h2 rv d1">Коротко <em>о&nbsp;главном</em></h2><div class="faq">{faq_items(qs)}</div><p class="note"><a class="more" href="{u("voprosy/")}">Все вопросы <span class="ar">→</span></a></p></div></section>' if qs else ""}
{fin_block()}"""
    page("kak-kupit/", "Как купить автомобиль из Китая под ключ — 7 шагов | МТК Восток-Авто",
         "Как проходит покупка машины из Китая: выбор, проверка, договор и оплата через ВТБ, доставка, СБКТС и ЭПТС, растаможка, выдача. Срок 50–65 дней.",
         body, active="kak-kupit/", jsonld=[bc_ld(("kak-kupit/", "Как купить"))] + ([faq_ld(qs)] if qs else []), prio="0.8")


def price_page(kp, rates):
    ex = next((c for c in kp if "kicks" in c["slug"]), kp[0] if kp else None)
    exb = ""
    if ex:
        exb = f"""<section class="sec bg"><div class="wrap cols"><div><p class="kick rv">Пример</p><h2 class="h2 rv d1">{E(ex["title"])} <em>{ex.get("year") or ""}</em></h2>
<p class="lead rv d2">Так выглядит расчёт конкретной машины на&nbsp;{ddmm(TODAY)}: каждая строка&nbsp;— отдельный платёж, ничего сверху.</p>
<p class="rv d2" style="margin-top:26px"><a class="btn b" href="{u("avto/" + ex["slug"] + "/")}">Смотреть машину <span class="ar">→</span></a></p></div>
<div class="box rv d1"><table class="brk">{"".join(f"<tr><td>{E(k)}</td><td>{rub(v)}</td></tr>" for k, v in ex["price"]["lines"])}
<tr><td><b>Итого под ключ</b></td><td><b>{rub(ex["total"])}</b></td></tr></table></div></div></section>"""
    v = rates["vtb"]
    svc = [("Проверка машины", 1300, "Осмотр на&nbsp;месте с&nbsp;отчётом, фото и&nbsp;видео"), ("Оклейка элементов", 2500, "Капот, стойки, фары, зеркала"),
           ("Полная оклейка", 3500, "Плёнка среднего класса"), ("Полная оклейка премиум", 5500, "Премиальная плёнка")]
    body = f"""
<section class="phead"><div class="wrap">{crumbs((None, "Стоимость"))}
<h1 class="rv in">Стоимость&nbsp;— <em>под&nbsp;ключ</em></h1>
<p class="lead">Автомобиль, доставка, растаможка, документы и&nbsp;наши услуги. Платите в&nbsp;четыре этапа по&nbsp;договору, без&nbsp;скрытых платежей.</p>
<div class="rates"><div style="border-color:rgba(255,255,255,.2)"><small style="color:rgba(255,255,255,.65)">Курс юаня для расчёта на {ddmm(TODAY)}</small><b style="color:#fff">{f"{v:.2f}".replace(".", ",")}&nbsp;₽</b></div>
<div style="border-color:rgba(255,255,255,.2)"><small style="color:rgba(255,255,255,.65)">Юань по ЦБ — для пошлины</small><b style="color:#fff">{f"{rates['cny']:.4f}".replace(".", ",")}&nbsp;₽</b></div>
<div style="border-color:rgba(255,255,255,.2)"><small style="color:rgba(255,255,255,.65)">Евро по ЦБ — для пошлины</small><b style="color:#fff">{f"{rates['eur']:.2f}".replace(".", ",")}&nbsp;₽</b></div></div>
</div></section>
<section class="sec"><div class="wrap"><p class="kick rv">Платежи</p><h2 class="h2 rv d1">Четыре этапа <em>оплаты</em></h2>{PAYS}
<p class="note rv">Оплачивается отдельно: постановка на&nbsp;учёт в&nbsp;ГИБДД и&nbsp;страховка&nbsp;— по&nbsp;тарифам ГИБДД и&nbsp;страховой.</p></div></section>
{exb}
<section class="sec"><div class="wrap"><p class="kick rv">Дополнительно</p><h2 class="h2 rv d1">Услуги <em>по&nbsp;желанию</em></h2>
<div class="svc">{"".join(f'<div class="rv"><b>{t}</b><span>{y:,}&nbsp;¥</span><p>≈&nbsp;{rub(y * v)} по&nbsp;курсу дня · {d}</p></div>'.replace(",", "&nbsp;") for t, y, d in svc)}</div></div></section>
{fin_block()}"""
    page("stoimost/", "Стоимость автомобиля из Китая под ключ: из чего складывается цена | МТК Восток-Авто",
         f"Из чего складывается цена машины из Китая под ключ: автомобиль, доставка, комиссия банка, пошлина, утильсбор, СБКТС и ЭПТС, услуги. Курс юаня на {ddmm(TODAY)}.",
         body, active="stoimost/", jsonld=[bc_ld(("stoimost/", "Стоимость"))], prio="0.8")


def deliv_page():
    body = f"""
<section class="phead"><div class="wrap">{crumbs((None, "Выданные"))}
<h1 class="rv in">Выданные <em>автомобили</em></h1>
<p class="lead">Машины, которые мы привезли и&nbsp;передали владельцам. Цены&nbsp;— итог под&nbsp;ключ по&nbsp;договору.</p></div></section>
<section class="sec tight"><div class="wrap"><div class="dgrid" style="margin-top:0">{deliv_cards()}</div>
<p class="note">Новые выдачи&nbsp;— в&nbsp;нашем <a class="more" href="{CHANNEL}">Telegram-канале <span class="ar">→</span></a></p></div></section>
{fin_block()}"""
    page("vydannye/", "Выданные автомобили из Китая — наши клиенты | МТК Восток-Авто",
         "Автомобили из Китая, которые мы привезли и передали владельцам: модель, год, пробег, город выдачи и итог под ключ по договору.",
         body, active="vydannye/", jsonld=[bc_ld(("vydannye/", "Выданные"))], prio="0.6")


def faq_page(faq):
    groups = []
    for g in dict.fromkeys(q["group"] for q in faq):
        items = [q for q in faq if q["group"] == g]
        groups.append(f'<div class="fgroup"><h2 class="rv">{E(g)}</h2><div class="faq" style="margin-top:20px">{faq_items(items)}</div></div>')
    body = f"""
<section class="phead"><div class="wrap">{crumbs((None, "Вопросы"))}
<h1 class="rv in">Частые <em>вопросы</em></h1>
<p class="lead">Оплата, сроки, таможня, утильсбор, проверка машины и&nbsp;документы. Не&nbsp;нашли ответ&nbsp;— напишите специалисту.</p></div></section>
<section class="sec tight"><div class="wrap" style="max-width:1100px">{"".join(groups)}
<p class="note" style="margin-top:50px"><a class="btn b" href="{u("kontakty/")}">Задать свой вопрос <span class="ar">→</span></a></p></div></section>
{fin_block()}"""
    page("voprosy/", "Частые вопросы об автомобилях из Китая под ключ | МТК Восток-Авто",
         "Ответы на частые вопросы: оплата через ВТБ, сроки доставки, таможня и утильсбор, проверка машины, СБКТС и ЭПТС, электромобили и гибриды.",
         body, active="voprosy/", jsonld=[bc_ld(("voprosy/", "Вопросы")), faq_ld(faq)], prio="0.8")


def contacts_page():
    body = f"""
<section class="phead"><div class="wrap">{crumbs((None, "Контакты"))}
<h1 class="rv in">Напишите <em>специалисту</em></h1>
<p class="lead">Расскажите, какую машину и&nbsp;в&nbsp;какой город хотите,&nbsp;— подберём варианты и&nbsp;посчитаем стоимость под&nbsp;ключ.</p></div></section>
<section class="sec tight"><div class="wrap"><div class="tgrid" style="margin-top:0">{team_cards()}</div>
<div class="box rv" style="margin-top:22px;display:flex;flex-wrap:wrap;gap:20px;align-items:center;justify-content:space-between"><div><h3>Telegram-канал МТК Восток-Авто</h3>
<p style="color:var(--muted);margin-top:6px">Новые машины, подборки и&nbsp;выданные автомобили.</p></div><a class="btn b" href="{CHANNEL}">Открыть канал <span class="ar">→</span></a></div></div></section>
{fin_block()}"""
    page("kontakty/", "Контакты — МТК Восток-Авто, автомобили из Китая под ключ",
         "Специалисты МТК Восток-Авто: Юрий Золотарев, Глеб Цепелев (Северо-Запад), Иван Сергеев (Урал и Поволжье). Telegram, WhatsApp, MAX, телефон.",
         body, active="kontakty/", jsonld=[bc_ld(("kontakty/", "Контакты")), ORG], prio="0.7")


def extras(models, kp, rates):
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(
        f"<url><loc>{SITE}{u(p)}</loc><lastmod>{TODAY.isoformat()}</lastmod><priority>{pr}</priority></url>\n" for p, pr in PAGES) + "</urlset>\n")
    lines = [f"# МТК Восток-Авто", "", "> Международная транспортная компания «Восток-Авто»: новые и б/у автомобили из Китая под ключ для частных покупателей в России — "
             "подбор, проверка, договор, оплата через ВТБ, доставка, растаможка, СБКТС и ЭПТС. Работаем с Китаем с 2016 года. Срок от оплаты до выдачи 50–65 дней.", "",
             f"Курс юаня для расчёта на {ddmm(TODAY)}: {rates['vtb']:.2f} ₽.", "", "## Разделы", ""]
    lines += [f"- [{t}]({SITE}{u(p)})" for p, t in MENU]
    lines += ["", f"## Каталог ({len(models)} моделей, цена под ключ — ориентир)", ""]
    lines += [f"- [{m['name']}]({SITE}{u('katalog/' + m['slug'] + '/')}): {m['engine']}, {m['power']}; {html.unescape(price_range(m['from'], m['to']))}" for m in models]
    if kp:
        lines += ["", f"## Авто в Китае ({len(kp)} машин, цена под ключ на {ddmm(TODAY)})", ""]
        lines += [f"- [{c['title']} {c.get('year') or ''}]({SITE}{u('avto/' + c['slug'] + '/')}): {kp_line(c)}; {c['total']:,} ₽ под ключ, {c.get('city') or ''}".replace(",", " ") for c in kp]
    lines += ["", "## Контакты", ""] + [f"- {p['name']} — {p['note']}: {p['tel']}, Telegram @{p['tg']}" for p in TEAM] + [f"- Telegram-канал: {CHANNEL}", ""]
    (OUT / "llms.txt").write_text("\n".join(lines))
    (OUT / "404.html").write_text(f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Страница не найдена — МТК Восток-Авто</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<script>var p=location.pathname;if(p.indexOf("/new/")===0)location.replace(p.slice(4)+location.search+location.hash)</script></head>
<body style="font-family:sans-serif;text-align:center;padding:80px 20px"><h1>Страница не найдена</h1><p><a href="{u()}">На главную МТК Восток-Авто</a></p></body></html>
""")
    (OUT / "robots.txt").write_text("User-agent: *\nDisallow: /\n" if PREVIEW else f"User-agent: *\nAllow: /\nSitemap: {SITE}{u('sitemap.xml')}\n")


def main():
    global NW, NH, ASSET_V
    offline = "--offline" in sys.argv
    IMG.mkdir(parents=True, exist_ok=True)
    fonts()
    NW, NH = brand()
    css, js = (NEW / "src" / "s.css").read_text(), (NEW / "src" / "s.js").read_text()
    ASSET_V = hashlib.md5((css + js).encode()).hexdigest()[:8]
    (OUT / "s.css").write_text(css)
    (OUT / "s.js").write_text(js)
    road = MTK / "kp" / "fon_a4_polnyy.jpg"
    webp(road, IMG / "road.webp", 1600, 74, crop=(0, 700, 1400, 1700))
    webp(road, IMG / "road_m.webp", 900, 74)
    Image.open(CARS / "hero_sec2.jpg").convert("RGB").resize((1200, 670), Image.LANCZOS).save(IMG / "og.jpg", quality=82)
    for n in ("d_xrv_1", "d_xrv_2", "d_q05_1", "d_q05_2", "d_yaris_1", "d_yaris_2", "d_coolray_1", "d_coolray_2", "yura", "gleb", "ivan"):
        shutil.copy2(MAIN_IMG / f"{n}.webp", IMG / f"{n}.webp")
    kicks = ROOT.parent / "foto-inbox-mtk" / "kicks-xv-2022"
    webp(kicks / "1.jpg", IMG / "k_1.webp", 1280, 74)
    for k in range(4):
        webp(CARS / f"hero_sec{k}.jpg", IMG / f"sec{k}.webp", 2200, 74)
        webp(CARS / f"hero_sec{k}.jpg", IMG / f"sec{k}_m.webp", 1100, 74)

    cbr = cbr_rates(offline)
    vtb, src = vtb_rate(cbr)
    rates = {"vtb": vtb, "vtb_src": src, "cny": cbr["cny"], "eur": cbr["eur"], "cbr_date": cbr["date"]}
    models = load_models()
    for m in models:
        model_imgs(m)
    kp = load_kp(rates)
    for c in kp:
        kp_imgs(c)
    kp = [c for c in kp if c.get("imgs")]
    live = {c["slug"] for c in kp}
    for d in (OUT / "avto", IMG / "kp"):                # страницы и фото машин, которых больше нет в списке
        for x in (d.iterdir() if d.exists() else []):
            if x.is_dir() and x.name not in live:
                shutil.rmtree(x)
    faq = json.loads((DATA / "faq.json").read_text()) if (DATA / "faq.json").exists() else []

    PAGES.clear()
    home(models, kp, rates, faq)
    catalog_page(models)
    for m in models:
        model_page(m, models, kp)
    if kp:
        avto_page(kp, rates)
        for c in kp:
            car_page(c, kp, models, rates)
    how_page(faq)
    price_page(kp, rates)
    deliv_page()
    if faq:
        faq_page(faq)
    contacts_page()
    extras(models, kp, rates)
    (DATA / "last_build.json").write_text(json.dumps({"date": TODAY.isoformat(), "rates": rates, "models": len(models), "kp": len(kp), "pages": len(PAGES)}, ensure_ascii=False, indent=1))
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"страниц {len(PAGES)}, моделей {len(models)}, машин {len(kp)}, курс {vtb} ({src}), ЦБ {cbr['cny']:.4f}/{cbr['eur']:.2f}, всего {size / 1e6:.1f} МБ")


if __name__ == "__main__":
    main()
