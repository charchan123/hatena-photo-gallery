"""Assemble actual Chromium captures; never modifies source photographs."""
from pathlib import Path
from io import BytesIO
import json
import shutil
import sys
from PIL import Image, ImageDraw, ImageFont

source = Path(sys.argv[1])
out = Path(__file__).resolve().parent
font = ImageFont.truetype('DejaVuSans.ttf', 22)
data = json.loads((source / 'measurements.json').read_text())
shutil.copyfile(source / 'measurements.json', out / 'measurements.json')
def sheet(name, panels):
    width = sum(im.width for _, im in panels) + 16 * (len(panels) - 1)
    result = Image.new('RGB', (width, max(im.height for _, im in panels) + 48), '#f7fcf4')
    draw = ImageDraw.Draw(result)
    x = 0
    for label, im in panels:
        draw.text((x + 12, 10), label, font=font, fill='#25412d')
        result.paste(im.convert('RGB'), (x, 48))
        x += im.width + 16
    buffer = BytesIO()
    result.save(buffer, format='WEBP', quality=88, method=6)
    payload = buffer.getvalue()
    assert len(payload) > 100
    (out / name).write_bytes(payload)
    assert (out / name).read_bytes() == payload
for width in (1280, 1024, 900, 899, 768, 680, 390, 320):
    sheet(f'top-comparison-{width}.webp', [(label, Image.open(source / f'top-{width}-{v}.png'))
          for v, label in [('before', 'Before / main'), ('after', 'After / Draft #131')]])
for width in (1280, 390):
    panels = []
    for variant in ('before', 'after'):
        im = Image.open(source / f'mixed-{width}-{variant}.png')
        m = next(m for m in data['measurements'] if m['page'] == 'best-shots-2025' and m['width'] == width and m['variant'] == variant)
        cards = m['cards'][3:5]  # October's first two photographs; November has three.
        height = round(max(c['card']['bottom'] for c in cards) - min(c['card']['y'] for c in cards) + 38)
        panels.append((variant.title(), im.crop((0, 0, im.width, min(im.height, height)))))
    sheet(f'best-mixed-comparison-{width}.webp', panels)
    panels = []
    for letter, label in [('A', 'A / 4:3 contain (selected)'), ('B', 'B / square + 20px mat'), ('C', 'C / compact 3:2 contain')]:
        im = Image.open(source / f'option-{letter}-{width}.png')
        im = im.crop((0, 0, im.width, min(im.height, 1080 if width == 1280 else 1350)))
        if width == 1280:
            im = im.resize((600, round(im.height * 600 / im.width)))
        panels.append((label, im))
    sheet(f'best-options-{width}.webp', panels)
    sheet(f'annual-comparison-{width}.webp', [(v.title(), Image.open(source / f'best-shots-2025-{width}-{v}.png').crop((0, 0, width, 1300))) for v in ('before', 'after')])
    Image.open(source / f'extreme-{width}.png').convert('RGB').save(out / f'extreme-{width}.webp', quality=88)
if len(sys.argv) > 2:
    reference = Path(sys.argv[2])
    shutil.copyfile(reference, out / 'reference-ss110.png')
    panels = [('User reference / original crop', Image.open(reference))]
    for v in ('before', 'after'):
        im = Image.open(source / f'top-1280-{v}.png')
        panels.append((v.title() + ' / 1280px crop', im.crop((0, 216, 1280, 684))))
    sheet('reference-and-1280-comparison.webp', panels)
print('PASS: actual before/after captures assembled with viewport labels')
