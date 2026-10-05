"""Пробная версия нового сайта МТК (Юрий 05.10.2026: «как mercedes-benz.com, но сине-белый, как в каталогах и КП»).

Шаблон new/index.tpl.html + данные каталога (~/auto-china/catalog/cars_data.py) и фото → docs/new/ (адрес mtk-vostok-avto.ru/new/,
закрыт от поисковиков). Основной сайт не трогает. Запуск: python3 new/build_new.py
"""
import html
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "new"
IMG = OUT / "img"
AC = Path.home() / "auto-china"
CARS = AC / "catalog" / "cars"
KICKS = ROOT.parent / "foto-inbox-mtk" / "kicks-xv-2022"
sys.path.insert(0, str(AC / "catalog"))
import cars_data  # noqa: E402
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("mtk_build", ROOT / "build.py")   # карточки специалистов — те же, что на сайте
_mb = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_mb)
TEAM = _mb.TEAM

E = html.escape


def webp(src, name, w, q=76, crop=None):
    im = Image.open(src).convert("RGB")
    if crop:
        im = im.crop(crop)
    if im.width > w:
        im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    im.save(IMG / f"{name}.webp", quality=q, method=6)
    return im.size


def font():
    """Inter (переменный, с оптическим размером) — только латиница, кириллица и знаки: ~100 КБ вместо 860."""
    from fontTools import subset
    (OUT / "fonts").mkdir(parents=True, exist_ok=True)
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga", "calt", "tnum", "case"]
    f = subset.load_font(str(Path.home() / ".fonts/gf/Inter[opsz,wght].ttf"), opts)
    s = subset.Subsetter(opts)
    s.populate(unicodes=list(range(0x20, 0x7F)) + list(range(0xA0, 0x100)) + list(range(0x400, 0x460))
               + [0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x201E, 0x2026, 0x2116, 0x20BD, 0x2192, 0x2190, 0x00AB, 0x00BB, 0x2009, 0x202F])
    s.subset(f)
    subset.save_font(f, str(OUT / "fonts" / "inter.woff2"), opts)


def name_white():
    """«ВОСТОК-АВТО» белым — для прозрачной шапки над тёмным первым экраном."""
    nm = Image.open(ROOT / "docs" / "assets" / "img" / "mtk_name.png").convert("RGBA")
    w = Image.new("RGBA", nm.size, (255, 255, 255, 0))
    w.putalpha(nm.getchannel("A"))
    w.save(IMG / "name_w.png", optimize=True)
    return nm.width // 2, nm.height // 2


def money(v):
    return f"{v / 1e6:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def catalog():
    tabs, lists, n = [], [], 0
    labels = {"ЭЛЕКТРО": "Электро", "ГИБРИДЫ": "Гибриды", "МОНОПРИВОД": "Бензин", "ПОЛНЫЙ ПРИВОД": "Полный привод"}
    for ci, cat in enumerate(cars_data.CATEGORIES):
        cars = [c for p in cat["pages"] for c in p["cars"]]
        n += len(cars)
        cond = cat.get("cond", "").replace("Б/У", "б/у").replace("НОВЫЙ", "новые").replace("ЛЕТ", "лет")
        note = f"{cond[:1].upper() + cond[1:]} · {cat['sub']}"
        tabs.append(f'<button class="tab" type="button" data-note="{E(note)}">{labels.get(cat["cat"], cat["cat"].title())}<small>{len(cars)}</small></button>')
        cards = []
        for c in cars:
            stem = Path(c["photo"]).stem
            if not (IMG / f"c_{stem}.webp").exists():
                webp(CARS / c["photo"], f"c_{stem}", 720, 72)
            pr = f'от {money(c["from"])}' + (f'–{money(c["to"])}' if c.get("to") else "") + "&nbsp;млн&nbsp;₽"
            cards.append(f'<article class="card"><div class="im"><img src="img/c_{stem}.webp" alt="{E(c["name"])}" loading="lazy" width="720" height="424"></div>'
                         f'<div class="t"><h3>{E(c["name"])}</h3><div class="sp">{E(c["engine"])} · {E(c["power"])}</div>'
                         f'<div class="pr">{pr}<small>ориентир под ключ</small></div></div></article>')
        lists.append(f'<div class="cards">{"".join(cards)}</div>')
    return "".join(tabs), "".join(lists), n


STEPS = [
    ("01", "Выбор автомобиля", "Выбираете модель из каталога или предлагаете свою, называете бюджет — мы подбираем несколько оптимальных вариантов.", None, None),
    ("02", "Подбор и проверка", "Проверяем историю машины по базам и по желанию её состояние на месте, готовим отчёт и присылаем фото и видео.", None, "k_1"),
    ("03", "Договор и оплата", "Высылаем договор, контракт и инвойс. Оплата через банк ВТБ.", "Оплата 1 — предоплата 50 000 ₽<br>Оплата 2 — автомобиль, доставка, погрузка и комиссия банка", None),
    ("04", "Доставка", "Погрузка на автовоз, доставка до границы и дальше — в Ваш город.", None, "d_yaris_1"),
    ("05", "Документы", "Оформляем СБКТС и электронный ПТС.", None, None),
    ("06", "Таможня", "Растаможиваем автомобиль: помогаем оплатить пошлину и сборы, подскажем суммы и реквизиты.", "Оплата 3 — пошлина, сборы, СВХ и оформление документов", "d_coolray_1"),
    ("07", "Выдача", "Получаете ключи, ЭПТС и таможенные документы и ставите машину на учёт.", "Оплата 4 — остаток 40 000 ₽ за подбор и сопровождение", "d_xrv_1"),
]


def steps():
    out = []
    for n, h, p, pay, ph in STEPS:
        nb = lambda s: s.replace(" — ", "&nbsp;— ").replace(" 000", "&nbsp;000").replace(" ₽", "&nbsp;₽")
        if ph:
            src = f"img/{ph}.webp" if ph.startswith("k_") else f"../assets/img/{ph}.webp"
            out.append(f'<div class="step ph"><img src="{src}" alt="" loading="lazy"><div><div class="n" style="color:#fff">{n}</div>'
                       f'<h3>{h}</h3><p>{nb(p)}</p></div></div>')
        else:
            out.append(f'<div class="step"><div class="n">{n}</div><h3>{h}</h3><p>{nb(p)}</p>'
                       + (f'<div class="pay">{nb(pay)}</div>' if pay else "") + '</div>')
    return "".join(out)


# поворот: спереди → слева → сзади → справа → снова спереди (фото из КП Nissan Kicks)
SPIN = [(3, "Вид спереди"), (1, "Спереди слева"), (4, "Слева"), (6, "Сзади слева"), (13, "Сзади"), (5, "Сзади справа"), (2, "Спереди справа"),
        (10, "Салон"), (7, "Сиденья"), (11, "Задний ряд")]
THUMBS = [18, 9, 15, 12]


def kicks():
    for i, _ in SPIN:
        webp(KICKS / f"{i}.jpg", f"k_{i}", 1280, 74)
    for i in THUMBS:
        webp(KICKS / f"{i}.jpg", f"k_{i}", 1280, 74)
    spin = "".join(f'<img src="img/k_{i}.webp" alt="{E(t)}" loading="lazy" width="1280" height="960">' for i, t in SPIN)
    thumbs = "".join(f'<img src="img/k_{i}.webp" alt="" loading="lazy">' for i in THUMBS)
    return spin, thumbs, json.dumps([t for _, t in SPIN], ensure_ascii=False)


DELIV = [("xrv", "Honda XR-V 1.5 Comfort", "2022 · 33 889 км · бензин, 131 л.с.", "Санкт-Петербург", "1 769 998"),
         ("q05", "Changan Qiyuan Q05 506Max", "2025 · 7 000 км · электро, 163 л.с.", "Ижевск", "2 214 339"),
         ("yaris", "Toyota Yaris L 1.5", "2022 · 66 000 км · бензин, 107 л.с.", "Пермь", "1 390 144"),
         ("coolray", "Geely Coolray 1.4T", "2022 · 13 500 км · бензин, 141 л.с.", "Санкт-Петербург", "1 247 044")]


def deliv():
    return "".join(
        f'<article class="dc rv"><img src="../assets/img/d_{k}_1.webp" alt="{E(n)}" loading="lazy"><img src="../assets/img/d_{k}_2.webp" alt="" loading="lazy">'
        f'<div class="t"><div><h3>{n}</h3><div class="sp">{s} · выдача: {c}</div></div>'
        f'<div class="pr">{p.replace(" ", "&nbsp;")}&nbsp;₽<small>итог под ключ</small></div></div></article>' for k, n, s, c, p in DELIV)


def team():
    max_href = "https://max.ru/u/f9LHodD0cOLQzwPoUyWBoejqc5iq940FAYmSIsMAm8Hr1FcNu85zWG126zY"
    out = []
    for p in TEAM:
        bt = f'<a href="https://t.me/{p["tg"]}">Telegram</a><a href="https://wa.me/{p["wa"]}">WhatsApp</a>'
        if p["mx"] and p["mx"] != "phone":
            bt += f'<a href="{max_href}">MAX</a>'
        tel = "+" + "".join(ch for ch in p["tel"] if ch.isdigit())
        mx = '<span class="mx">Этот же номер — в MAX</span>' if p["mx"] == "phone" else ""
        out.append(f'<div class="who rv"><img src="../assets/img/{p["img"]}.webp" alt="{p["name"]}" loading="lazy" width="96" height="96">'
                   f'<h3>{p["name"]}</h3><div class="r">{p["note"]}</div><a class="ph" href="tel:{tel}">{p["tel"].replace(" ", "&nbsp;", 1)}</a>{mx}'
                   f'<div class="bt">{bt}</div></div>')
    return "".join(out)


def main():
    IMG.mkdir(parents=True, exist_ok=True)
    font()
    nw, nh = name_white()
    slides, dots = [], []
    for i, k in enumerate((2, 1, 3)):
        webp(CARS / f"hero_sec{k}.jpg", f"hero{k}", 2200, 74)
        webp(CARS / f"hero_sec{k}.jpg", f"hero{k}_m", 1400, 74)
        slides.append(f'<picture><source media="(max-width:760px)" srcset="img/hero{k}_m.webp"><img src="img/hero{k}.webp" alt="" '
                      f'{"fetchpriority=\"high\"" if i == 0 else "loading=\"lazy\""} width="2200" height="1228"></picture>')
        dots.append("<i></i>")
    road = AC / "mtk" / "kp" / "fon_a4_polnyy.jpg"
    webp(road, "road", 1600, 74, crop=(0, 700, 1400, 1700))
    webp(road, "road_m", 900, 74)
    tabs, cards, n = catalog()
    spin, thumbs, names = kicks()
    s = (ROOT / "new" / "index.tpl.html").read_text()
    for k, v in {"SLIDES": "".join(slides), "DOTS": "".join(dots), "STEPS": steps(), "TABS": tabs, "CARDS": cards, "NMODELS": str(n),
                 "SPIN": spin, "THUMBS": thumbs, "SPIN_NAMES": names, "DELIV": deliv(), "TEAM": team(), "NW": str(nw), "NH": str(nh)}.items():
        s = s.replace("{{%s}}" % k, v)
    assert "{{" not in s, s[s.index("{{"):s.index("{{") + 40]
    (OUT / "index.html").write_text(s)
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print("docs/new/index.html", len(s), "всего", round(size / 1e6, 1), "МБ", "моделей", n)


if __name__ == "__main__":
    main()
