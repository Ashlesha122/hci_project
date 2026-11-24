"""Tiny trust-blue / sage icons for the Chrome extension."""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent / "icons"
HERE.mkdir(parents=True, exist_ok=True)

BLUE = (49, 130, 206, 255)
SAGE = (107, 144, 128, 255)


for size in (16, 48, 128):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    pad = max(1, size // 16)
    draw.rounded_rectangle([pad, pad, size - pad - 1, size - pad - 1], radius=size // 4, fill=BLUE)
    m = size // 4
    draw.ellipse([m, m, size - m - 1, size - m - 1], fill=SAGE)
    im.save(HERE / f"icon{size}.png")
    print("wrote", HERE / f"icon{size}.png")
