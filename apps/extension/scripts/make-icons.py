"""Render the extension's PNG icons from the Anything Download logo mark.

Chrome does not accept SVG for manifest icons, so the brand mark used by the website
(apps/web/public/brand/mark-512.png) is downscaled to each size. One logo everywhere:
website favicon, app icon and extension icon.
Run from apps/extension:  python scripts/make-icons.py   (requires Pillow)
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT.parent / "web" / "public" / "brand" / "mark-512.png"
OUT = ROOT / "src" / "icons"


def render(mark: Image.Image, size: int) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    # A small inset keeps the mark from touching the toolbar's edge at 16px.
    inset = max(1, round(size * 0.04))
    target = size - inset * 2
    scaled = mark.resize((target, target), Image.LANCZOS)
    canvas.paste(scaled, (inset, inset), scaled)
    return canvas


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    mark = Image.open(SOURCE).convert("RGBA")
    for size in (16, 32, 48, 128):
        render(mark, size).save(OUT / f"icon-{size}.png", optimize=True)
        print("wrote", OUT / f"icon-{size}.png")
