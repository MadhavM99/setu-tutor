"""Crop and shrink photos for the word pictures.

    python -m scripts.prepare_word_photos  path/to/photo.jpg  book

Writes setu/web/static/img/words/book.webp: a centred 480x480 square, small enough to load fast on a phone.
"""
import sys
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parents[1] / "setu/web/static/img/words"


def main(src: str, name: str) -> Path:
    im = Image.open(src).convert("RGB")
    side = min(im.size)
    left, top = (im.width - side) // 2, (im.height - side) // 2
    im = im.crop((left, top, left + side, top + side)).resize((480, 480))
    out = OUT / f"{name}.webp"
    im.save(out, "WEBP", quality=80)
    return out


if __name__ == "__main__":
    print(main(sys.argv[1], sys.argv[2]))
