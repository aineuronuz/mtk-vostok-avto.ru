"""Сайт МТК Восток-Авто — та же страница, что yurazol.ru, со своим брендом, цветом (синий КП; у yurazol.ru бирюзовый) и порядком блоков.

Берёт исходник ../yurazol.ru/src/index.html, меняет бренд, собирает тем же render() и пишет docs/index.html.
Картинки — из ../yurazol.ru/docs/assets (сначала prep_assets.py там, если их меняли). Запуск: python3 build.py
"""
import re
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
YZ = ROOT.parent / "yurazol.ru" / "docs"
sys.path.insert(0, str(ROOT.parent / "yurazol.ru"))
from build import catalog, render  # noqa: E402
OUT = ROOT / "docs"
IMG = OUT / "assets" / "img"

PALETTE = """
html.mtk{--bg:#f5f7fb;--bg2:#eaf0f8;--card:#fff;--card2:#fbfcfe;--line:rgba(29,61,107,.14);--ink:#0e1b2e;--muted:rgba(14,27,46,.66);
--acc:#2b5797;--acc2:#1d3d6b;--soft:#e6edf7;--glow:rgba(43,87,151,.16);--sh:0 1px 2px rgba(14,27,46,.05),0 12px 34px -14px rgba(29,61,107,.22)}
html.mtk.navy{--bg:#f4f6fa;--bg2:#e7ecf4;--line:rgba(20,39,70,.15);--ink:#0c1626;--acc:#1f3a68;--acc2:#142746;--soft:#e4e9f2;--glow:rgba(31,58,104,.16)}
html.mtk.indigo{--bg:#f5f5fb;--bg2:#e9e9f6;--line:rgba(39,50,109,.15);--ink:#11132a;--acc:#3b4a9c;--acc2:#27326d;--soft:#e7e8f5;--glow:rgba(59,74,156,.16)}
.wm{font-family:'Unbounded',sans-serif;font-weight:700;letter-spacing:.01em}
@media (max-width:420px){html.mtk .brand b{display:block;font-size:12.5px;line-height:1.15}}
"""


def sub(s, old, new, count=1):
    assert old in s, f"нет в шаблоне: {old[:70]}"
    return s.replace(old, new, count)


def section(s, sid):
    m = re.search(rf'<section class="sec" id="{sid}">.*?</section>\n', s, flags=re.S)
    assert m, sid
    return m.group(0)


def build():
    s = (YZ.parent / "src" / "index.html").read_text()

    s = sub(s, '<html lang="ru">', '<html lang="ru" class="mtk">')
    s = sub(s, "<title>YuraZol Auto — автомобили из Китая под ключ</title>", "<title>МТК Восток-Авто — автомобили из Китая под ключ</title>")
    s = s.replace("https://yurazol.ru/", "https://mtk-vostok-avto.ru/")
    s = s.replace('content="YuraZol Auto"', 'content="МТК Восток-Авто"')
    s = s.replace('content="YuraZol Auto — автомобили из Китая под ключ"', 'content="МТК Восток-Авто — автомобили из Китая под ключ"')
    s = sub(s, '<meta name="theme-color" content="#f4f8f9">', '<meta name="theme-color" content="#f5f7fb">')
    s = re.sub(r'<link rel="icon"[^>]*>\n<link rel="apple-touch-icon"[^>]*>\n', "", s)   # логотипа пока нет
    s = sub(s, "</style>", PALETTE + "</style>")

    # шапка и подвал без логотипа — только название
    s = re.sub(r'<a class="brand" href="#"><img src="assets/img/logo96.png"[^>]*><span><b>YuraZol Auto</b>',
               '<a class="brand" href="#"><span><b class="wm">МТК <span class="nw">Восток-Авто</span></b>', s, count=1)
    s = re.sub(r'<a class="brand" href="#"><img src="assets/img/logo96.png"[^>]*><span><b>YuraZol Auto</b></span></a>',
               '<a class="brand" href="#"><span><b class="wm">МТК Восток-Авто</b></span></a>', s, count=1)
    s = sub(s, "© 2026 YuraZol Auto", "© 2026 МТК Восток-Авто")
    s = sub(s, '<div class="ghost" aria-hidden="true">YURAZOL</div>', '<div class="ghost" aria-hidden="true">VOSTOK</div>')

    # главное фото — студийное, без номеров
    s = re.sub(r'<picture><source media="\(max-width:700px\)" srcset="assets/img/hall_m.webp".*?</picture>',
               '<picture><source media="(max-width:700px)" srcset="assets/img/hero_m.webp" type="image/webp">'
               '<source srcset="assets/img/hero.webp" type="image/webp"><img src="assets/img/hero.jpg" '
               'alt="Автомобиль из Китая" width="1400" height="781" fetchpriority="high"></picture>', s, count=1, flags=re.S)

    s = sub(s, "<span>YuraZol Auto — подбор автомобиля и сопровождение сделки</span>",
            "<span>МТК Восток-Авто — подбор автомобиля и сопровождение сделки</span>")
    # канал в контактах
    s = sub(s, '<nav class="links">\n',
            '<nav class="links">\n          <a href="https://t.me/mtk_vostok_avto"><span><b>Telegram-канал</b>'
            '<small>автомобили и новости</small></span><span class="ar">→</span></a>\n')

    # «Получить каталог»: окно с каналом МТК (в MAX канала пока нет)
    s = sub(s, "на канал YuraZol Auto", "на канал МТК Восток-Авто")
    s = catalog(s, tg="https://t.me/mtk_vostok_avto")

    # порядок: сначала этапы сделки, потом цена
    price, steps = section(s, "price"), section(s, "steps")
    s = s.replace(price, "@@PRICE@@").replace(steps, price).replace("@@PRICE@@", steps)
    s = sub(s, '<a href="#price">Цена</a><a href="#steps">Этапы</a>', '<a href="#steps">Этапы</a><a href="#price">Цена</a>')

    left = [w for w in ("YuraZol Авто", "YuraZol Auto", "yurazol.ru", "logo96") if w in s]
    assert not left, f"остался бренд YuraZol: {left}"
    s = render(s)
    (OUT / "index.html").write_text(s)
    print("docs/index.html", len(s))


def assets():
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    shutil.copytree(YZ / "assets" / "fonts", OUT / "assets" / "fonts", dirs_exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    for f in (YZ / "assets" / "img").iterdir():
        if f.name.startswith(("d_", "sec", "yura")):
            shutil.copy2(f, IMG / f.name)
    hero = Image.open(Path.home() / "auto-china/catalog/cars/hero_sec2.jpg").convert("RGB")
    for name, w in (("hero", 2200), ("hero_m", 1100)):
        im = hero.resize((w, round(hero.height * w / hero.width)), Image.LANCZOS) if hero.width > w else hero
        im.save(IMG / f"{name}.jpg", quality=80, optimize=True, progressive=True)
        im.save(IMG / f"{name}.webp", quality=78, method=6)
    ImageOps.fit(hero, (1200, 630), Image.LANCZOS).save(IMG / "og.jpg", quality=84, optimize=True)


if __name__ == "__main__":
    assets()
    build()
    (OUT / "robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: https://mtk-vostok-avto.ru/sitemap.xml\n")
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                     '<url><loc>https://mtk-vostok-avto.ru/</loc></url></urlset>\n')
