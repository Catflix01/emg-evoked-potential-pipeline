"""Turn the site's favicon into application icons for the downloads.

    python web/make_icons.py

Writes assets/icon.icns (Mac) and assets/icon.ico (Windows) from assets/favicon.svg, so
the downloaded app wears the same mark as the website instead of a blank page.

Both outputs are committed. They are build inputs: PyInstaller needs them at build time,
and the Windows runner has no way to make an .icns. Run this again only when the favicon
itself changes.

Rasterising needs macOS's own tools (qlmanage, sips, iconutil), which is where the .icns
has to be made anyway. The .ico is written by Pillow and could be made anywhere.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"
SVG = ASSETS / "favicon.svg"

# The sizes macOS wants in an .iconset, and what each must be called.
ICNS_SIZES = [(16, "16x16"), (32, "16x16@2x"), (32, "32x32"), (64, "32x32@2x"),
              (128, "128x128"), (256, "128x128@2x"), (256, "256x256"),
              (512, "256x256@2x"), (512, "512x512"), (1024, "512x512@2x")]

# Windows packs several sizes into one .ico and picks whichever fits.
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def run(*command):
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode:
        sys.exit(f"{command[0]} failed: {done.stderr.strip() or done.stdout.strip()}")


def svg_to_png(svg, png, size=1024):
    """Render the SVG once, large, and scale everything else from it."""
    if not shutil.which("qlmanage"):
        sys.exit("Rendering the SVG needs macOS (qlmanage). The committed icons are "
                 "already built; this only needs running when the favicon changes.")
    with tempfile.TemporaryDirectory() as scratch:
        run("qlmanage", "-t", "-s", str(size), "-o", scratch, str(svg))
        rendered = next(Path(scratch).glob("*.png"), None)
        if rendered is None:
            sys.exit("qlmanage produced no image from the SVG")
        shutil.copy(rendered, png)


def build_icns(png, target):
    with tempfile.TemporaryDirectory() as scratch:
        iconset = Path(scratch) / "icon.iconset"
        iconset.mkdir()
        for pixels, name in ICNS_SIZES:
            run("sips", "-z", str(pixels), str(pixels), str(png),
                "--out", str(iconset / f"icon_{name}.png"))
        run("iconutil", "-c", "icns", str(iconset), "-o", str(target))


def build_ico(png, target):
    from PIL import Image
    image = Image.open(png).convert("RGBA")
    image.save(target, sizes=[(s, s) for s in ICO_SIZES])


def main():
    if not SVG.exists():
        sys.exit(f"no {SVG}")

    with tempfile.TemporaryDirectory() as scratch:
        png = Path(scratch) / "icon.png"
        svg_to_png(SVG, png)
        build_icns(png, ASSETS / "icon.icns")
        build_ico(png, ASSETS / "icon.ico")

    for made in ["icon.icns", "icon.ico"]:
        size = (ASSETS / made).stat().st_size
        print(f"  wrote assets/{made}  ({size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
