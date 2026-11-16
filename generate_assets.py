from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"
SOURCE = ASSETS / "source_art"


def transparent_edge_flood(image, tolerance=24):
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    background = pixels[0, 0][:3]
    seen = bytearray(width * height)
    queue = deque()

    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))

    while queue:
        x, y = queue.popleft()
        index = y * width + x
        if seen[index]:
            continue
        seen[index] = 1
        r, g, b, _ = pixels[x, y]
        if (
            abs(r - background[0]) > tolerance
            or abs(g - background[1]) > tolerance
            or abs(b - background[2]) > tolerance
        ):
            continue

        pixels[x, y] = (r, g, b, 0)
        if x > 0:
            queue.append((x - 1, y))
        if x + 1 < width:
            queue.append((x + 1, y))
        if y > 0:
            queue.append((x, y - 1))
        if y + 1 < height:
            queue.append((x, y + 1))

    return rgba


def crop_asset(filename, box, transparent=True, tolerance=24):
    image = Image.open(SOURCE / filename).convert("RGBA").crop(box)
    if transparent:
        image = transparent_edge_flood(image, tolerance)
        bounds = image.getchannel("A").getbbox()
        if bounds:
            image = image.crop(bounds)
    return image


def save_crates():
    boxes = [
        (16, 16, 89, 125),
        (118, 32, 193, 125),
        (216, 0, 291, 125),
        (310, 10, 387, 125),
    ]
    for index, box in enumerate(boxes):
        crop_asset("crates.png", box).save(ASSETS / f"crate_{index}.png")


def save_zombies():
    for index, filename in enumerate(
        ("zombie_runner.png", "zombie_brute.png", "zombie_spitter.png")
    ):
        with Image.open(SOURCE / filename) as source:
            bounds = (0, 0, source.width, source.height)
        image = crop_asset(filename, bounds, tolerance=20)
        if index == 1:
            boss = image.copy()
            boss.thumbnail((260, 260), Image.Resampling.LANCZOS)
            boss.save(ASSETS / "boss.png")
        image.thumbnail((112, 112), Image.Resampling.LANCZOS)
        image.save(ASSETS / f"zombie_{index}.png")


def save_players():
    scale = 3
    size = 112
    outline = (25, 32, 38, 255)
    styles = (
        ("ranger", (48, 91, 119, 255), (94, 130, 143, 255), (40, 57, 61, 255), (86, 100, 79, 255)),
        ("tank", (126, 67, 52, 255), (175, 105, 75, 255), (54, 57, 56, 255), (112, 79, 58, 255)),
        ("scout", (68, 101, 57, 255), (128, 151, 83, 255), (43, 61, 46, 255), (71, 88, 59, 255)),
        ("medic", (178, 181, 157, 255), (224, 224, 197, 255), (59, 76, 67, 255), (191, 194, 173, 255)),
        ("sniper", (126, 101, 57, 255), (175, 145, 88, 255), (57, 61, 48, 255), (105, 101, 72, 255)),
    )

    for index, (style, armor, highlight, pants, gear) in enumerate(styles):
        image = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        def coords(values):
            return tuple(round(value * scale) for value in values)

        def rounded(box, fill, radius=5, border=outline, width=2):
            draw.rounded_rectangle(
                coords(box),
                radius=radius * scale,
                fill=fill,
                outline=border,
                width=width * scale,
            )

        def ellipse(box, fill, border=outline, width=2):
            draw.ellipse(coords(box), fill=fill, outline=border, width=width * scale)

        def polygon(points, fill, border=outline, width=2):
            draw.polygon([coords(point) for point in points], fill=fill)
            if border:
                draw.line(
                    [coords(point) for point in list(points) + [points[0]]],
                    fill=border,
                    width=width * scale,
                    joint="curve",
                )

        def line(points, fill, width):
            draw.line([coords(point) for point in points], fill=fill, width=width * scale, joint="curve")

        draw.ellipse(coords((23, 98, 96, 114)), fill=(9, 12, 14, 105))

        if style == "sniper":
            polygon(((36, 44), (72, 42), (88, 70), (82, 98), (26, 91), (30, 65)), gear)

        backpack = (17, 43, 39, 77) if style != "tank" else (15, 41, 42, 80)
        rounded(backpack, gear, radius=7)
        rounded((20, 50, 36, 68), pants, radius=4, width=1)
        line(((24, 54), (32, 54)), (146, 145, 111, 255), 2)

        polygon(((39, 70), (54, 73), (51, 96), (39, 100), (33, 89)), pants)
        polygon(((56, 72), (72, 70), (80, 87), (75, 99), (61, 94)), pants)
        rounded((29, 94, 47, 107), (36, 40, 40, 255), radius=5)
        rounded((67, 93, 88, 106), (36, 40, 40, 255), radius=5)
        line(((33, 101), (43, 101)), highlight, 2)
        line(((72, 100), (84, 100)), highlight, 2)

        if style == "tank":
            torso = ((28, 40), (77, 39), (88, 58), (81, 85), (34, 87), (25, 62))
        elif style == "scout":
            torso = ((38, 42), (72, 42), (79, 59), (73, 82), (38, 82), (33, 61))
        else:
            torso = ((34, 41), (75, 41), (83, 57), (77, 84), (34, 84), (29, 59))
        polygon(torso, armor)
        polygon(((40, 47), (70, 47), (75, 63), (68, 79), (41, 79), (36, 61)), gear, width=1)
        line(((49, 49), (49, 76)), highlight, 2)
        line(((48, 61), (69, 61)), outline, 2)
        rounded((42, 65, 50, 75), highlight, radius=2, width=1)
        rounded((57, 65, 65, 75), highlight, radius=2, width=1)

        arm_color = highlight if style == "medic" else armor
        line(((36, 49), (28, 62), (34, 72)), outline, 15)
        line(((36, 49), (28, 62), (34, 72)), arm_color, 10)
        line(((73, 49), (84, 49), (91, 55)), outline, 15)
        line(((73, 49), (84, 49), (91, 55)), arm_color, 10)
        ellipse((28, 67, 39, 77), gear, width=1)
        ellipse((86, 50, 97, 60), gear, width=1)

        if style == "scout":
            polygon(((39, 26), (45, 15), (65, 15), (73, 26), (68, 44), (48, 47), (38, 38)), gear)
            rounded((43, 27, 68, 36), (39, 49, 43, 255), radius=3, width=1)
            ellipse((46, 28, 55, 34), (215, 205, 125, 255), width=1)
            ellipse((58, 28, 66, 34), (215, 205, 125, 255), width=1)
            line(((28, 75), (20, 88)), outline, 5)
            line(((27, 75), (20, 87)), (166, 177, 143, 255), 2)
        elif style == "medic":
            ellipse((40, 20, 70, 48), highlight)
            rounded((45, 17, 65, 24), (205, 207, 185, 255), radius=3, width=1)
            draw.rectangle(coords((53, 17, 59, 24)), fill=(186, 57, 54, 255))
            draw.rectangle(coords((48, 20, 64, 23)), fill=(186, 57, 54, 255))
            draw.rectangle(coords((17, 52, 39, 70)), fill=(218, 218, 193, 255))
            draw.rectangle(coords((25, 54, 31, 68)), fill=(186, 57, 54, 255))
            draw.rectangle(coords((21, 58, 35, 64)), fill=(186, 57, 54, 255))
            draw.rectangle(coords((29, 55, 35, 67)), fill=(186, 57, 54, 255))
        elif style == "sniper":
            polygon(((41, 24), (47, 14), (66, 16), (74, 29), (69, 41), (44, 42)), gear)
            rounded((44, 30, 67, 39), pants, radius=4, width=1)
            line(((47, 34), (65, 34)), highlight, 2)
        elif style == "tank":
            ellipse((31, 20, 73, 50), (76, 63, 54, 255), width=3)
            ellipse((38, 25, 67, 44), gear, width=1)
            rounded((37, 14, 68, 23), highlight, radius=4, width=1)
        else:
            ellipse((40, 20, 70, 48), (41, 69, 90, 255))
            ellipse((43, 16, 68, 38), (62, 103, 133, 255), width=2)
            line(((48, 20), (63, 20)), (137, 172, 186, 255), 2)

        rifle_length = 43 if style == "sniper" else 27 if style == "scout" else 34
        rifle_end = 73 + rifle_length
        line(((72, 51), (rifle_end, 49)), outline, 9)
        line(((73, 50), (rifle_end, 48)), (91, 103, 103, 255), 4)
        rounded((77, 43, 86, 48), (49, 58, 59, 255), radius=2, width=1)
        line(((80, 54), (84, 61)), outline, 4)
        if style == "sniper":
            rounded((92, 40, 104, 45), (46, 54, 52, 255), radius=2, width=1)
            line(((108, 48), (116, 48)), (210, 169, 88, 255), 2)
        elif style == "tank":
            polygon(((17, 66), (29, 62), (34, 71), (32, 91), (20, 94), (15, 84)), armor)
            line(((21, 70), (28, 70)), highlight, 2)
        elif style == "ranger":
            rounded((34, 56, 40, 64), (47, 60, 68, 255), radius=2, width=1)

        reduced = image.resize((size, size), Image.Resampling.LANCZOS)
        reduced.save(ASSETS / f"player_{index}.png")


def save_environment():
    images = {
        "cobblestone.png": ("environment_sheet.png", (14, 2, 313, 184), False),
        "ruined_asphalt.png": ("environment_sheet.png", (337, 2, 628, 184), False),
        "barrier_0.png": ("environment_sheet.png", (657, 9, 850, 86), True),
        "barrier_1.png": ("environment_sheet.png", (850, 9, 1042, 86), True),
        "debris.png": ("environment_sheet.png", (659, 112, 781, 190), True),
        "spent_casings.png": ("environment_sheet.png", (794, 123, 874, 188), True),
        "blood_splatter.png": ("environment_sheet.png", (954, 126, 1077, 190), True),
        "sandbags.png": ("obstacle_sheet.png", (0, 0, 211, 109), True),
        "abandoned_car.png": ("obstacle_sheet.png", (231, 0, 460, 110), True),
        "oil_drums.png": ("obstacle_sheet.png", (482, 0, 620, 112), True),
    }

    for output, (filename, box, transparent) in images.items():
        image = crop_asset(filename, box, transparent, tolerance=22)
        image.save(ASSETS / output)


def main():
    ASSETS.mkdir(exist_ok=True)
    required = (
        "crates.png",
        "zombie_runner.png",
        "zombie_brute.png",
        "zombie_spitter.png",
        "obstacle_sheet.png",
        "environment_sheet.png",
    )
    missing = [SOURCE / filename for filename in required if not (SOURCE / filename).exists()]
    if missing:
        raise FileNotFoundError("Missing source images: " + ", ".join(map(str, missing)))

    save_crates()
    save_zombies()
    save_players()
    save_environment()
    print(f"Assets generated in {ASSETS}")


if __name__ == "__main__":
    main()
