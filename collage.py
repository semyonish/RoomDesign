"""Side-by-side comparison sheet of renders with a caption under each.

    .venv/bin/python collage.py out.png a.png "Подпись A" b.png "Подпись B" ...
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HEIGHT = 900      # each picture is scaled to this height
GAP = 24          # white space between and around the pictures
CAPTION = 90      # caption band under the pictures
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"  # has Cyrillic


def collage(out, items):
    pics = []
    for path, _ in items:
        im = Image.open(path).convert("RGB")
        pics.append(im.resize((round(im.width * HEIGHT / im.height), HEIGHT), Image.LANCZOS))
    width = sum(p.width for p in pics) + GAP * (len(pics) + 1)
    sheet = Image.new("RGB", (width, HEIGHT + CAPTION + GAP), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(FONT, 44)
    x = GAP
    for pic, (_, caption) in zip(pics, items):
        sheet.paste(pic, (x, GAP))
        w = draw.textlength(caption, font=font)
        draw.text((x + (pic.width - w) / 2, GAP + HEIGHT + 22), caption, fill=(40, 40, 40), font=font)
        x += pic.width + GAP
    sheet.save(out)
    print(f"collage -> {out}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 3 or len(args) % 2 == 0:
        sys.exit(__doc__)
    collage(Path(args[0]), list(zip(args[1::2], args[2::2])))
