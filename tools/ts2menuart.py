"""Build a 2x menu and loading-art mod from the player's TS2 Xbox archives.

    python tools/ts2menuart.py game/data build/menu-and-loading-art
    RECOMP_MODS="$PWD/build/menu-and-loading-art" <usual game or launcher command>

Requires Pillow and FFmpeg with its xBR filter. The output is a new mod folder.
"""
import argparse
from pathlib import Path
import struct
import subprocess
import tempfile

from PIL import Image

from ts2pak import build_pak, read_pak
from ts2xbt import Xbt, decode_level, encode_level, full_levels


MENU_ART = {"ts2newlogo", *(f"ts2banner{i}" for i in range(1, 5)),
           *(f"ts2smallbanner{i}" for i in range(1, 5))}
ART = {
    "l_101.pak": MENU_ART | {"menubg"},
    "l_103.pak": {"ts2newlogo", "ts2loading"},
    "l_105.pak": MENU_ART,
}
# The front end draws its text from these glyph sheets.  Every archive that
# carries one gets the 2x replacement; the same bytes recur across the paks.
FONTS = {"impact.xbt", "book.xbt", "booklight.xbt"}


def xbr(rgb):
    """Feed FFmpeg opaque pixels, so its colour-distance metric sees only colour."""
    w, h = rgb.size
    command = ["ffmpeg", "-nostdin", "-v", "error", "-f", "rawvideo",
               "-pixel_format", "rgb24", "-video_size", f"{w}x{h}",
               "-i", "pipe:0", "-vf", "xbr=2", "-frames:v", "1",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
    pixels = subprocess.run(command, input=rgb.tobytes(), stdout=subprocess.PIPE,
                            check=True).stdout
    return Image.frombytes("RGB", (w * 2, h * 2), pixels)


def upscale(blob):
    texture = Xbt(blob)
    hd = texture.header
    source = Image.frombytes("RGBA", (hd.width, hd.height), decode_level(texture, 0))
    # Interpolate visible colour and coverage independently. Hidden colour in
    # transparent pixels must not bleed into the outline of the title lettering.
    red, green, blue, alpha = source.convert("RGBa").split()
    rgb = xbr(Image.merge("RGB", (red, green, blue)))
    if alpha.getextrema() == (255, 255):
        result = rgb.convert("RGBA")
    else:
        coverage = xbr(alpha.convert("RGB")).getchannel("R")
        result = Image.merge("RGBa", (*rgb.split(), coverage)).convert("RGBA")

    # Add a new top level. Keep the original levels byte-exact below it and
    # keep the original display size, including the loading picture's 4:3 size.
    levels = [encode_level(result.tobytes(), *result.size, hd.format), *texture.levels]
    if hd.levels < full_levels(hd.width, hd.height):
        levels = levels[:hd.levels]
    header = bytearray(hd.raw)
    struct.pack_into("<2I", header, 0, *result.size)
    struct.pack_into("<I", header, 16, len(levels) - 1)
    return bytes(header) + b"".join(levels) + texture.trailing


def build(data, output):
    if output.exists():
        raise ValueError(f"Choose a new mod folder. {output} already exists.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        mod = Path(temp) / "mod"
        mod.mkdir()
        # Each level loads its own copy of a glyph sheet.  US loads whole
        # archives.  Decode repeated copies once, keyed by source bytes.
        required = {data / "arcade" / archive for archive in ART}
        font_cache = {}
        for path in sorted(set(data.rglob("*.pak")) | required):
            archive = path.name
            selected = ART[archive] if path in required else ()
            raw = path.read_bytes()
            _, entries, layout = read_pak(raw)
            wanted = {f"textures/misc/{name}.xbt" for name in selected}
            wanted.update(f"textures/misc/{font}" for font in FONTS
                          if any(e["name"] == f"textures/misc/{font}" for e in entries))
            # Mission cards, the loading-screen backdrops, and the larger
            # pictures behind the story briefing live in several archives.
            wanted.update(e["name"] for e in entries
                          if e["name"].startswith("textures/misc/lvim_")
                          and e["name"].endswith(".xbt"))
            if not wanted:
                continue
            names, blobs = [], []
            for entry in entries:
                name, offset = entry["name"], entry["position"]
                blob = raw[offset:offset + entry["length"]]
                if name in wanted:
                    if name in {f"textures/misc/{font}" for font in FONTS}:
                        if blob not in font_cache:
                            font_cache[blob] = upscale(blob)
                        blob = font_cache[blob]
                    else:
                        blob = upscale(blob)
                    wanted.remove(name)
                names.append(name)
                blobs.append(blob)
            if wanted:
                raise ValueError(f"{archive} is missing {', '.join(sorted(wanted))}")
            target = mod / "data" / path.relative_to(data)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(build_pak(layout, names, blobs))
        (mod / "mod.json").write_text('{\n  "name": "TimeSplitters 2 menu and loading art"\n}\n', encoding="utf-8")
        mod.rename(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path, help="game data directory containing arcade/")
    parser.add_argument("output", type=Path, help="new mod directory to create")
    args = parser.parse_args()
    build(args.data, args.output)
