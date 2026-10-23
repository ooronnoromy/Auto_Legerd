"""Render AutoLedger's vector mark as glass app icons. Run from the project root."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


OUTPUT = Path(__file__).resolve().parent.parent / 'static' / 'icons'
SCALE = 2
SIZE = 512 * SCALE
# Keep the recognizable chevron fully inside the PWA maskable safe circle.
MARK = [(256, 108), (400, 384), (319, 384), (252, 232), (185, 384), (112, 384)]


def box(values):
    return tuple(round(value * SCALE) for value in values)


def gradient(top, bottom):
    result = Image.new('RGBA', (SIZE, SIZE))
    draw = ImageDraw.Draw(result)
    for y in range(SIZE):
        t = y / (SIZE - 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom))
        draw.line((0, y, SIZE, y), fill=color)
    return result


def glow(image, bounds, color, blur):
    layer = Image.new('RGBA', image.size)
    ImageDraw.Draw(layer).ellipse(box(bounds), fill=color)
    image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur * SCALE)))


def masked(image, fill, mask):
    layer = Image.new('RGBA', image.size)
    layer.paste(fill, (0, 0), mask)
    image.alpha_composite(layer)


def render():
    image = gradient((178, 197, 229, 255), (207, 217, 240, 255))
    glow(image, (-160, -140, 340, 300), (248, 252, 255, 190), 62)
    glow(image, (290, -60, 650, 320), (159, 151, 214, 130), 60)
    glow(image, (135, 340, 580, 680), (219, 239, 252, 210), 60)

    # Convex glass tile with a bright rim, dark underside and visible backdrop.
    shadow = Image.new('RGBA', image.size)
    ImageDraw.Draw(shadow).rounded_rectangle(box((37, 43, 475, 490)), radius=110*SCALE, fill=(49, 71, 113, 62))
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(15*SCALE)))
    tile = Image.new('L', image.size)
    ImageDraw.Draw(tile).rounded_rectangle(box((30, 29, 482, 477)), radius=112*SCALE, fill=255)
    masked(image, gradient((252, 254, 255, 60), (230, 239, 255, 12)), tile)
    edges = Image.new('RGBA', image.size)
    draw = ImageDraw.Draw(edges)
    draw.rounded_rectangle(box((30, 29, 482, 477)), radius=112*SCALE, outline=(250, 253, 255, 224), width=2*SCALE)
    draw.rounded_rectangle(box((34, 33, 478, 473)), radius=109*SCALE, outline=(250, 253, 255, 72), width=2*SCALE)
    draw.arc(box((258, 29, 482, 253)), 270, 355, fill=(226, 239, 255, 200), width=2*SCALE)
    image.alpha_composite(edges)

    mark = Image.new('L', image.size)
    points = [box(point) for point in MARK]
    ImageDraw.Draw(mark).polygon(points, fill=255)
    mark_shadow = Image.new('RGBA', image.size)
    mark_shadow.paste((47, 67, 108, 110), (0, 0, SIZE, SIZE), mark.filter(ImageFilter.GaussianBlur(8*SCALE)))
    image.alpha_composite(mark_shadow)
    masked(image, gradient((244, 250, 255, 255), (68, 96, 151, 255)), mark)

    # Narrow reflective edges preserve the letter's silhouette at favicon size.
    rim = Image.new('RGBA', image.size)
    draw = ImageDraw.Draw(rim)
    draw.line(points + [points[0]], fill=(51, 77, 125, 175), width=2*SCALE, joint='curve')
    draw.line([box(p) for p in [(114, 381), (256, 110), (395, 379)]], fill=(250, 253, 255, 240), width=3*SCALE, joint='curve')
    draw.line([box(p) for p in [(185, 383), (252, 232), (319, 383)]], fill=(216, 237, 255, 180), width=2*SCALE, joint='curve')
    draw.line([box(p) for p in [(121, 381), (251, 129)]], fill=(230, 246, 255, 145), width=2*SCALE)
    draw.line([box(p) for p in [(266, 135), (388, 371)]], fill=(234, 223, 255, 130), width=2*SCALE)
    image.alpha_composite(rim)

    # A broad reflected light sweeps across the glass mark.
    shine = Image.new('L', image.size)
    ImageDraw.Draw(shine).polygon([box(p) for p in [(80, 230), (450, 160), (450, 193), (80, 272)]], fill=65)
    from PIL import ImageChops
    shine = ImageChops.multiply(shine.filter(ImageFilter.GaussianBlur(8*SCALE)), mark)
    masked(image, Image.new('RGBA', image.size, (250, 253, 255, 255)), shine)
    return image


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    icon = render()
    for size in (192, 512):
        rendered = icon.resize((size, size), Image.Resampling.LANCZOS).convert('RGB')
        rendered.save(OUTPUT / f'icon-glass-{size}.png', optimize=True)
        # Replace legacy URLs too, for existing installations requesting them.
        rendered.save(OUTPUT / f'icon-{size}.png', optimize=True)
    icon.resize((180, 180), Image.Resampling.LANCZOS).convert('RGB').save(OUTPUT / 'apple-touch-icon.png', optimize=True)
    icon.resize((32, 32), Image.Resampling.LANCZOS).convert('RGB').save(OUTPUT / 'favicon-32.png', optimize=True)
    icon.save(OUTPUT / 'favicon.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])

    points = ' '.join(f'{x},{y}' for x, y in MARK)
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
<defs>
 <linearGradient id="bg" x2=".5" y2="1"><stop stop-color="#e0eaff"/><stop offset=".5" stop-color="#b5c9e9"/><stop offset="1" stop-color="#d2dcf3"/></linearGradient>
 <radialGradient id="light"><stop stop-color="#f8fcff" stop-opacity=".65"/><stop offset="1" stop-color="#f8fcff" stop-opacity="0"/></radialGradient>
 <linearGradient id="glass" x2=".3" y2="1"><stop stop-color="#fcfeff" stop-opacity=".24"/><stop offset="1" stop-color="#e6efff" stop-opacity=".05"/></linearGradient>
 <linearGradient id="mark" x2=".15" y2="1"><stop stop-color="#f4faff"/><stop offset=".4" stop-color="#bbceec"/><stop offset="1" stop-color="#446097"/></linearGradient>
 <filter id="shadow" x="-30%" y="-30%" width="160%" height="170%"><feDropShadow dx="0" dy="7" stdDeviation="8" flood-color="#2f436c" flood-opacity=".28"/></filter>
</defs>
<path fill="url(#bg)" d="M0 0h512v512H0z"/>
<ellipse cx="95" cy="70" rx="260" ry="230" fill="url(#light)"/>
<rect x="30" y="29" width="452" height="448" rx="112" fill="url(#glass)" stroke="#fafdff" stroke-opacity=".88" stroke-width="2"/>
<rect x="34" y="33" width="444" height="440" rx="109" fill="none" stroke="#fcfeff" stroke-opacity=".28" stroke-width="2"/>
<polygon points="POINTS" fill="url(#mark)" stroke="#334d7d" stroke-opacity=".65" stroke-width="2" stroke-linejoin="round" filter="url(#shadow)"/>
<path d="M114 381 256 110 395 379" fill="none" stroke="#fafdff" stroke-opacity=".95" stroke-width="3" stroke-linejoin="round"/>
<path d="M185 383 252 232 319 383" fill="none" stroke="#d8edff" stroke-opacity=".7" stroke-width="2"/>
</svg>'''.replace('POINTS', points)
    (OUTPUT / 'icon-glass.svg').write_text(svg, encoding='utf-8')
    print('Generated glass PWA icons, Apple touch icon, PNG/ICO favicons and SVG source.')


if __name__ == '__main__':
    main()
