from pathlib import Path
from collections import deque

from PIL import Image, ImageEnhance


ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"
DOWNLOADS = Path.home() / "Downloads"


SOURCE_FILES = {
    "boss": DOWNLOADS / "boss.jpg",
    "zombie": DOWNLOADS / "zumbi.jpg",
    "player": DOWNLOADS / "280535103-bb7fd081-bda0-4e35-9261-f9927cf91b84.gif",
    "fundoreal": DOWNLOADS / "fundoreal.jpg",
    "local": DOWNLOADS / "local.png",
    "ambiente": DOWNLOADS / "ambiente.png",
}


PLAYER_TINTS = [
    (82, 170, 255),
    (255, 126, 95),
    (94, 231, 172),
    (232, 111, 255),
    (255, 218, 99),
]


def ensure_assets():
    ASSETS.mkdir(exist_ok=True)


def transparent_by_color(img, target, tolerance):
    rgba = img.convert("RGBA")
    pixels = rgba.load()
    w, h = rgba.size
    tr, tg, tb = target
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if abs(r - tr) <= tolerance and abs(g - tg) <= tolerance and abs(b - tb) <= tolerance:
                pixels[x, y] = (r, g, b, 0)
    return rgba


def transparent_edge_flood(img, tolerance=26):
    rgba = img.convert("RGBA")
    pixels = rgba.load()
    w, h = rgba.size
    bg = pixels[0, 0][:3]
    seen = set()
    queue = deque()

    for x in range(w):
        queue.append((x, 0))
        queue.append((x, h - 1))
    for y in range(h):
        queue.append((0, y))
        queue.append((w - 1, y))

    while queue:
        x, y = queue.popleft()
        if (x, y) in seen or not (0 <= x < w and 0 <= y < h):
            continue
        seen.add((x, y))
        r, g, b, a = pixels[x, y]
        if abs(r - bg[0]) > tolerance or abs(g - bg[1]) > tolerance or abs(b - bg[2]) > tolerance:
            continue
        pixels[x, y] = (r, g, b, 0)
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return rgba


def alpha_bbox(img):
    alpha = img.getchannel("A")
    return alpha.getbbox() or (0, 0, img.width, img.height)


def save_zombies():
    src = Image.open(SOURCE_FILES["zombie"]).convert("RGB")
    cols, rows = 3, 2
    cell_w, cell_h = src.width // cols, src.height // rows
    for row in range(rows):
        for col in range(cols):
            cell = src.crop((col * cell_w, row * cell_h, (col + 1) * cell_w, (row + 1) * cell_h))
            cutout = transparent_by_color(cell, (0, 0, 0), 28)
            bbox = alpha_bbox(cutout)
            cutout = cutout.crop(bbox)
            cutout.thumbnail((96, 96), Image.Resampling.LANCZOS)
            cutout.save(ASSETS / f"zombie_{row * cols + col}.png")


def tint_player(base, color):
    base = base.convert("RGBA")
    overlay = Image.new("RGBA", base.size, color + (0,))
    alpha = base.getchannel("A")
    overlay.putalpha(alpha.point(lambda a: int(a * 0.28)))
    mixed = Image.alpha_composite(base, overlay)
    return ImageEnhance.Contrast(mixed).enhance(1.08)


def save_players():
    gif = Image.open(SOURCE_FILES["player"])
    frame = gif.convert("RGBA")
    frame = transparent_by_color(frame, (255, 255, 255), 36)
    frame = frame.crop(alpha_bbox(frame))
    frame.thumbnail((90, 90), Image.Resampling.LANCZOS)
    for idx, color in enumerate(PLAYER_TINTS):
        tint_player(frame, color).save(ASSETS / f"player_{idx}.png")


def save_boss():
    boss = Image.open(SOURCE_FILES["boss"])
    cutout = transparent_edge_flood(boss, 18)
    bbox = alpha_bbox(cutout)
    cutout = cutout.crop(bbox)
    cutout.thumbnail((260, 180), Image.Resampling.LANCZOS)
    cutout.save(ASSETS / "boss.png")


def save_backgrounds():
    for name in ("fundoreal", "local", "ambiente"):
        img = Image.open(SOURCE_FILES[name]).convert("RGB")
        if name != "fundoreal":
            img = ImageEnhance.Color(img).enhance(0.78)
            img = ImageEnhance.Brightness(img).enhance(0.72)
        img.save(ASSETS / ("fundoreal.jpg" if name == "fundoreal" else f"{name}.png"))


def main():
    ensure_assets()
    missing = [path for path in SOURCE_FILES.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing source images: " + ", ".join(str(path) for path in missing))
    save_zombies()
    save_players()
    save_boss()
    save_backgrounds()
    print(f"Assets generated in {ASSETS}")


if __name__ == "__main__":
    main()
