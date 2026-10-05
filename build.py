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
.cint{position:relative;color:var(--muted);margin:0 0 28px;max-width:560px}
.team{position:relative;display:grid;grid-template-columns:repeat(3,1fr);gap:24px;align-items:stretch}
.team .who{display:flex;flex-direction:column}
.team .who>span{flex:1}
.team .im{display:flex;gap:10px;margin-top:10px}.team .im .btn{flex:1;padding:0 12px}
.team .tl{min-height:64px}.team .mx{display:block;color:var(--muted);font-size:13px;margin-top:4px}
.fin2 .links.ch{position:relative;margin-top:34px}
/* шапка: круглый логотип и название, как на обложке КП МТК (Юрий 05.10.2026, временно) */
.top .brand{flex:0 1 auto;min-width:0;gap:12px}
.top .brand .lg{flex-shrink:0;line-height:0}.top .brand .lg img{width:56px;height:56px}
.top .bv{width:280px;flex:0 1 auto;min-width:0;line-height:0}.top .bv img{display:block;width:100%;height:auto}
.top .nav,.top .tools,.top .btn{flex-shrink:0}
@media (max-width:1100px){.top .bv .tg{display:none}.top .brand .lg img{width:48px;height:48px}}
@media (max-width:920px) and (min-width:861px){.top .bv{display:none}}
@media (max-width:860px) and (min-width:721px){.top .bv .tg{display:block}}
@media (max-width:560px){.top .brand{gap:8px}.top .brand .lg img{width:40px;height:40px}}
@media (max-width:374px){.top .bv{display:none}}
@media (max-width:980px){.team{grid-template-columns:1fr;max-width:480px}.team .tl{min-height:0}}
"""

# контакты: Юрий, Глеб (СЗФО), Иван (УрФО и ПФО) — «Авто» по просьбе Юрия 04.10 и 05.10.2026
TEAM = [
    dict(img="yura", name="Юрий Золотарёв", note="Подбор автомобиля и сопровождение сделки",
         tg="YuraZol", wa="79119261617", mx="MAX_HREF", tel="+7 911 926-16-17"),
    dict(img="gleb", name="Глеб Цепелев", note="Заказы для Северо-Западного федерального округа",
         tg="GlebTsepelev", wa="79817613421", mx="phone", tel="+7 981 761-34-21"),
    dict(img="ivan", name="Иван Сергеев", note="Заказы для Уральского и Приволжского федеральных округов",
         tg="ivan_sergand", wa="79667948699", mx=None, tel="+7 966 794-86-99"),
]


# логотип и название — те же, что в КП и каталогах МТК (~/auto-china/mtk); для сайта ужаты
MTK = Path.home() / "auto-china" / "mtk"
LOGO_SRC = MTK / "logo" / "colors" / "MTK-logo-cvet-03-krupnee.png"
NAME_SRC = MTK / "kp" / "nazvanie" / "vostok-avto-gradient.png"
BOOKMAN = "/usr/share/fonts/opentype/urw-base35/URWBookman-Demi.otf"
NAME_W = 560   # px картинки названия (на сайте до 280 px — вдвое плотнее экрана)
BRAND = ('<a class="brand" href="#"><picture class="lg"><source srcset="assets/img/mtk_logo56.webp 1x, assets/img/mtk_logo112.webp 2x, '
         'assets/img/mtk_logo168.webp 3x" type="image/webp"><img src="assets/img/mtk_logo112.png" alt="" width="56" height="56"></picture>'
         '<span class="bv"><img src="assets/img/mtk_name.png" alt="МТК Восток-Авто" width="{nw}" height="{nh}">'
         '<img class="tg" src="assets/img/mtk_tag.png" alt="Международная транспортная компания" width="{tw}" height="{th}"></span></a>')


def brand_assets():
    """Круглый логотип, «ВОСТОК-АВТО» с переливом и подпись «МЕЖДУНАРОДНАЯ ТРАНСПОРТНАЯ КОМПАНИЯ» (Bookman, #2b5797)
    в ширину названия — пропорции как на обложке КП (gen_kp_mtk.py: название 79 мм, подпись 7.6 pt, отступ 2.6 мм)."""
    global BRAND
    from PIL import ImageDraw, ImageFont
    lg = Image.open(LOGO_SRC).convert("RGBA")
    lg = lg.crop(lg.getchannel("A").point(lambda v: 255 if v > 200 else 0).getbbox())   # без мягкой тени по краям
    for px in (56, 112, 168):
        im = lg.resize((px, px), Image.LANCZOS)
        im.save(IMG / f"mtk_logo{px}.webp", quality=88, method=6)
        if px == 112:
            im.save(IMG / "mtk_logo112.png", optimize=True)
    lg.resize((64, 64), Image.LANCZOS).quantize(256, method=Image.Quantize.FASTOCTREE).save(OUT / "assets" / "favicon.png", optimize=True)
    ti = Image.new("RGBA", (180, 180), (245, 247, 251, 255))
    ti.alpha_composite(lg.resize((164, 164), Image.LANCZOS), (8, 8))
    ti.convert("RGB").quantize(256).save(OUT / "assets" / "apple-touch-icon.png", optimize=True)

    nm = Image.open(NAME_SRC).convert("RGBA")
    nm = nm.resize((NAME_W, round(nm.height * NAME_W / nm.width)), Image.LANCZOS)
    nm.save(IMG / "mtk_name.png", optimize=True)
    text, mm = "МЕЖДУНАРОДНАЯ ТРАНСПОРТНАЯ КОМПАНИЯ", NAME_W / 79   # px картинки на миллиметр обложки
    f = ImageFont.truetype(BOOKMAN, round(7.6 * 25.4 / 72 * mm))
    ls = (NAME_W - f.getlength(text)) / (len(text) - 1)
    top, bot = f.getbbox("М")[1], f.getbbox("М")[3]
    gap = round(2.6 * mm * .55)   # на обложке 2.6 мм от строки; от названия до верха букв — чуть больше половины
    tg = Image.new("RGBA", (NAME_W, gap + bot - top + 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(tg)
    for i, c in enumerate(text):
        d.text((f.getlength(text[:i]) + i * ls, gap - top), c, font=f, fill=(0x2b, 0x57, 0x97, 255))
    tg.save(IMG / "mtk_tag.png", optimize=True)
    BRAND = BRAND.format(nw=nm.width // 2, nh=nm.height // 2, tw=tg.width // 2, th=tg.height // 2)


def team():
    cards = []
    for p in TEAM:
        im = f'<a class="btn o sm" href="https://wa.me/{p["wa"]}">WhatsApp</a>'
        if p["mx"] and p["mx"] != "phone":
            im += f'<a class="btn o sm" href="{p["mx"]}">MAX</a>'
        tel = "+" + re.sub(r"\D", "", p["tel"])
        cards.append(
            f'      <div class="who rv">\n'
            f'        <picture><source srcset="assets/img/{p["img"]}.webp" type="image/webp"><img src="assets/img/{p["img"]}.jpg" '
            f'alt="{p["name"]}" width="132" height="132" loading="lazy"></picture>\n'
            f'        <b>{p["name"]}</b>\n        <span>{p["note"]}</span>\n'
            f'        <a class="btn g" href="https://t.me/{p["tg"]}">Написать в Telegram <span class="ar">→</span></a>\n'
            f'        <div class="im">{im}</div>\n'
            f'        <div class="tl"><a class="ph" href="tel:{tel}">{p["tel"]}</a>'
            + ('<small class="mx">Этот же номер — в MAX</small>' if p["mx"] == "phone" else "")
            + '</div>\n      </div>\n')
    return ('\n    <p class="cint rv">Напишите, какую машину и в какой город хотите, — подберём варианты и посчитаем стоимость под ключ.</p>\n'
            '    <div class="team">\n' + "".join(cards) + '    </div>\n'
            '    <nav class="links ch">\n      <a href="https://t.me/mtk_vostok_avto"><span><b>Telegram-канал</b>'
            '<small>автомобили и новости</small></span><span class="ar">→</span></a>\n    </nav>\n')


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
    s = sub(s, "</style>", PALETTE + "</style>")

    # шапка: круглый логотип и название картинками, как на обложке КП; подвал — только название
    s, n = re.subn(r'<a class="brand" href="#"><img src="assets/img/logo96.png"[^>]*><span><b>YuraZol Auto</b><small>.*?</small></span></a>',
                   BRAND, s, count=1)
    assert n, "нет логотипа в шапке"
    s = re.sub(r'<a class="brand" href="#"><img src="assets/img/logo96.png"[^>]*><span><b>YuraZol Auto</b></span></a>',
               '<a class="brand" href="#"><span><b class="wm">МТК Восток-Авто</b></span></a>', s, count=1)
    s = sub(s, "© 2026 YuraZol Auto", "© 2026 МТК Восток-Авто")
    s = sub(s, '<div class="ghost" aria-hidden="true">YURAZOL</div>', '<div class="ghost" aria-hidden="true">VOSTOK</div>')

    # главное фото — студийное, без номеров
    s = re.sub(r'<picture><source media="\(max-width:700px\)" srcset="assets/img/hall_m.webp".*?</picture>',
               '<picture><source media="(max-width:700px)" srcset="assets/img/hero_m.webp" type="image/webp">'
               '<source srcset="assets/img/hero.webp" type="image/webp"><img src="assets/img/hero.jpg" '
               'alt="Автомобиль из Китая" width="1400" height="781" fetchpriority="high"></picture>', s, count=1, flags=re.S)

    # контакты: три карточки вместо Юрия одного, под ними канал
    s, n = re.subn(r'\n    <div class="cgrid">\n.*?\n    </div>\n', lambda m: team(), s, count=1, flags=re.S)
    assert n, "нет блока контактов"

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
    for name, c in (("gleb", 0.36), ("ivan", 0.42)):   # круглые фото для контактов, как yura в prep_assets.py
        im = ImageOps.fit(Image.open(Path.home() / f"auto-china/assets/{name}.jpg").convert("RGB"), (320, 320), Image.LANCZOS, centering=(0.5, c))
        im.save(IMG / f"{name}.jpg", quality=84, optimize=True, progressive=True)
        im.save(IMG / f"{name}.webp", quality=82, method=6)
    hero = Image.open(Path.home() / "auto-china/catalog/cars/hero_sec2.jpg").convert("RGB")
    for name, w in (("hero", 2200), ("hero_m", 1100)):
        im = hero.resize((w, round(hero.height * w / hero.width)), Image.LANCZOS) if hero.width > w else hero
        im.save(IMG / f"{name}.jpg", quality=80, optimize=True, progressive=True)
        im.save(IMG / f"{name}.webp", quality=78, method=6)
    ImageOps.fit(hero, (1200, 630), Image.LANCZOS).save(IMG / "og.jpg", quality=84, optimize=True)


if __name__ == "__main__":
    assets()
    brand_assets()
    build()
    (OUT / "robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: https://mtk-vostok-avto.ru/sitemap.xml\n")
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                     '<url><loc>https://mtk-vostok-avto.ru/</loc></url></urlset>\n')
