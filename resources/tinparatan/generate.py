#!/usr/bin/env python3

# Copyright 2026 The Tinparatan Authors
# You can use, redistribute, and/or modify this source code under
# the terms of the GPL-3.0 license that can be found in the LICENSE file.
"""
Regenerate Tinparatan icons from resources/tinparatan/source/logo-1024.png.

Helium's utils/generate_resources.py only scales a square PNG. This script
does that for the sizes in generate_resources.txt, and also builds the extra
files the branding copy list needs: about-page logos, the Linux SVG, the NTP
favicon, the Windows .ico files, and the document icon.

Run from anywhere:

    python3 resources/tinparatan/generate.py
"""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent
MASTER = ROOT / "source" / "logo-1024.png"
LIST = ROOT / "generate_resources.txt"

# Windows icon sizes. Vista and later store these as PNG frames inside the .ico.
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def load_master():
    """Return the square RGBA master logo."""
    image = Image.open(MASTER).convert("RGBA")
    if image.size[0] != image.size[1]:
        raise ValueError(f"master logo must be square, got {image.size}")
    return image


def resize(image, size):
    """Scale a square image to an exact size."""
    return image.resize((size, size), Image.Resampling.LANCZOS)


def save_png(image, path):
    """Write an optimized PNG, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)
    print(f"Created {path.relative_to(ROOT)} ({image.size[0]}x{image.size[1]})")


def scale_listed_pngs(master):
    """
    Honor generate_resources.txt, which uses Helium's
    "input size output" line format.
    """
    with LIST.open(encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 3:
                raise ValueError(f"{LIST.name}:{line_number} is invalid: {raw!r}")
            size = int(parts[1])
            output = ROOT / parts[2]
            save_png(resize(master, size), output)


def save_ico(master, path):
    """Write a multi-resolution Windows icon."""
    path.parent.mkdir(parents=True, exist_ok=True)
    master.save(
        path,
        format="ICO",
        sizes=[(size, size) for size in ICO_SIZES],
    )
    print(f"Created {path.relative_to(ROOT)} (ico {', '.join(map(str, ICO_SIZES))})")


def save_svg(master, path):
    """
    Embed a 256px PNG in an SVG. Chromium's .icon format is a flat vector
    path and cannot represent this artwork; the SVG can, so Linux desktop
    entries that consume product_logo.svg still show the logo.
    """
    import base64
    import io

    buffer = io.BytesIO()
    resize(master, 256).save(buffer, format="PNG", optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    # The data URL has to stay on one line. A newline inside the attribute
    # would be part of the base64 payload and the image would not decode.
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" '
        'viewBox="0 0 256 256">\n'
        f'  <image width="256" height="256" href="data:image/png;base64,{encoded}"/>\n'
        "</svg>\n",
        encoding="utf-8",
    )
    print(f"Created {path.relative_to(ROOT)} (svg)")


def document_icon(master, size=512):
    """A page glyph with the logo centered, replacing Helium's file.png."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    margin = int(size * 0.09)
    top = int(size * 0.05)
    left = margin
    right = size - margin
    bottom = size - int(size * 0.06)
    radius = int(size * 0.055)
    fold = int(size * 0.2)

    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        [left + 8, top + 10, right + 6, bottom + 8],
        radius=radius,
        fill=(0, 0, 0, 80),
    )
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(radius=size * 0.018)))

    page = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(page)
    draw.rounded_rectangle(
        [left, top, right, bottom],
        radius=radius,
        fill=(252, 252, 253, 255),
    )
    # Folded corner. Drawn after the page so it covers the rounded corner.
    draw.polygon(
        [(right - fold, top), (right, top + fold), (right - fold, top + fold)],
        fill=(214, 218, 224, 255),
    )
    draw.line(
        [(right - fold, top + 1), (right - 1, top + fold)],
        fill=(168, 174, 184, 255),
        width=max(2, size // 160),
    )
    canvas.alpha_composite(page)

    inner = int((right - left) * 0.58)
    logo = resize(master, inner)
    origin_x = left + ((right - left) - inner) // 2
    origin_y = top + ((bottom - top) - inner) // 2 + int(size * 0.03)
    canvas.alpha_composite(logo, (origin_x, origin_y))
    return canvas


def main():
    """CLI entrypoint."""
    if not MASTER.exists():
        raise SystemExit(f"missing master logo: {MASTER}")

    master = load_master()
    scale_listed_pngs(master)

    # About page and theme logos. 1x is what chrome://theme shows at the
    # image's CSS size; @2x is twice that. about-product-logo-size.patch
    # constrains the about page to 48px so the 128px 1x asset stays sharp.
    save_png(resize(master, 128), ROOT / "branding" / "product_logo.png")
    save_png(resize(master, 256), ROOT / "branding" / "product_logo_200.png")
    # The artwork is already full color and readable on light and dark, so the
    # "white" slots get the same image instead of a flattened white silhouette.
    save_png(resize(master, 128), ROOT / "branding" / "product_logo_white.png")
    save_png(resize(master, 256), ROOT / "branding" / "product_logo_white_200.png")
    # Destination filename is historical (Helium's monochrome star). The pixels
    # are the color logo, which is what stays recognizable at 22px.
    save_png(resize(master, 22), ROOT / "branding" / "product_logo_22_mono.png")

    save_svg(master, ROOT / "branding" / "product_logo.svg")
    save_png(resize(master, 16), ROOT / "favicons" / "favicon_ntp_16.png")
    save_png(resize(master, 32), ROOT / "favicons" / "favicon_ntp_32.png")
    save_png(resize(master, 32), ROOT / "branding" / "icon_sprite_32.png")

    save_ico(master, ROOT / "win" / "app.ico")
    document = document_icon(master)
    save_png(document, ROOT / "win" / "file.png")
    save_ico(document, ROOT / "win" / "document.ico")


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
