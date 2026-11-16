import json
import math
import random
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pygame


WIDTH, HEIGHT = 1280, 720
FPS = 60
ARENA = pygame.Rect(-1500, -1050, 3000, 2100)
BG = (23, 26, 31)
PANEL = (34, 39, 48)
TEXT = (232, 238, 242)
MUTED = (147, 159, 171)
ACCENT = (255, 202, 87)
RED = (229, 76, 76)
GREEN = (89, 185, 122)
ASSET_DIR = Path(__file__).parent / "assets"
RANKING_FILE = Path(__file__).parent / "ranking.json"


def load_ranking():
    if not RANKING_FILE.exists():
        return []

    try:
        entries = json.loads(RANKING_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Arquivo de ranking invalido: {exc}") from exc
    if not isinstance(entries, list):
        raise ValueError("O arquivo de ranking deve conter uma lista.")

    required = {"date", "character", "kills", "score", "level"}
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or not required.issubset(entry):
            raise ValueError(f"Registro {index} do ranking esta incompleto.")
        if (
            not isinstance(entry["character"], str)
            or type(entry["kills"]) is not int
            or type(entry["score"]) is not int
            or type(entry["level"]) is not int
        ):
            raise ValueError(f"Registro {index} do ranking tem dados invalidos.")
        try:
            datetime.fromisoformat(entry["date"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Data invalida no registro {index} do ranking.") from exc
    return entries


def save_ranking(entries):
    RANKING_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def format_ranking_date(value):
    return datetime.fromisoformat(value).astimezone().strftime("%d/%m/%Y %H:%M")


@dataclass(frozen=True)
class Character:
    name: str
    color: tuple[int, int, int]
    speed: float
    max_health: int
    fire_bonus: float
    trait: str


CHARACTERS = [
    Character("Ranger", (82, 170, 255), 285, 100, 1.00, "Equilibrado"),
    Character("Tanque", (255, 126, 95), 235, 145, 0.92, "Mais vida"),
    Character("Scout", (94, 231, 172), 340, 85, 1.06, "Mais rapido"),
    Character("Medica", (232, 111, 255), 275, 115, 0.98, "Regenera entre niveis"),
    Character("Atirador", (255, 218, 99), 255, 90, 1.18, "Maior cadencia"),
]


WEAPONS = [
    ("Pistola", 18, 330, 1, 0, 720),
    ("Pistola Forte", 24, 280, 1, 0, 760),
    ("SMG", 18, 135, 1, 3, 800),
    ("SMG Tatico", 21, 110, 1, 3, 850),
    ("Escopeta", 17, 520, 5, 12, 690),
    ("Escopeta Auto", 20, 420, 6, 13, 710),
    ("Rifle", 42, 245, 1, 0, 980),
    ("Rifle Pesado", 54, 220, 1, 0, 1040),
    ("Canhao Duplo", 45, 300, 2, 5, 940),
    ("Exterminadora", 40, 155, 2, 4, 1080),
]


def clamp(value, low, high):
    return max(low, min(high, value))


def safe_normalize(vec):
    if vec.length_squared() == 0:
        return pygame.Vector2()
    return vec.normalize()


def draw_text(surface, font, text, color, pos, align="topleft"):
    image = font.render(text, True, color)
    rect = image.get_rect()
    setattr(rect, align, pos)
    surface.blit(image, rect)
    return rect


def blit_center(surface, image, center):
    rect = image.get_rect(center=(int(center[0]), int(center[1])))
    surface.blit(image, rect)
    return rect


def circle_hits_rect(pos, radius, rect):
    closest_x = clamp(pos.x, rect.left, rect.right)
    closest_y = clamp(pos.y, rect.top, rect.bottom)
    return pos.distance_squared_to((closest_x, closest_y)) < (radius - 0.25) * (radius - 0.25)


def circle_rect_push(pos, radius, rect):
    closest = pygame.Vector2(clamp(pos.x, rect.left, rect.right), clamp(pos.y, rect.top, rect.bottom))
    offset = pygame.Vector2(pos) - closest
    dist_sq = offset.length_squared()
    if dist_sq > 0:
        distance = math.sqrt(dist_sq)
        if distance < radius:
            return offset / distance * (radius - distance + 0.5)
        return pygame.Vector2()

    distances = [
        (abs(pos.x - rect.left), pygame.Vector2(rect.left - radius - pos.x, 0)),
        (abs(pos.x - rect.right), pygame.Vector2(rect.right + radius - pos.x, 0)),
        (abs(pos.y - rect.top), pygame.Vector2(0, rect.top - radius - pos.y)),
        (abs(pos.y - rect.bottom), pygame.Vector2(0, rect.bottom + radius - pos.y)),
    ]
    return min(distances, key=lambda item: item[0])[1]


def resolve_obstacle_overlaps(pos, radius, obstacles, passes=3):
    for _ in range(passes):
        moved = False
        for rect in obstacles:
            push = circle_rect_push(pos, radius, rect)
            if push.length_squared() > 0:
                pos += push
                moved = True
        if not moved:
            break
    pos.x = clamp(pos.x, ARENA.left + radius, ARENA.right - radius)
    pos.y = clamp(pos.y, ARENA.top + radius, ARENA.bottom - radius)
    return pos


def move_actor(pos, radius, delta, obstacles):
    pos.x += delta.x
    pos.x = clamp(pos.x, ARENA.left + radius, ARENA.right - radius)
    resolve_obstacle_overlaps(pos, radius, obstacles, 2)
    pos.y += delta.y
    pos.y = clamp(pos.y, ARENA.top + radius, ARENA.bottom - radius)
    resolve_obstacle_overlaps(pos, radius, obstacles, 4)
    return pos


class Assets:
    def __init__(self):
        self.players = self.load_many("player_", 5)
        self.zombies = self.load_many("zombie_", 3)
        self.crates = self.load_many("crate_", 4)
        self.barriers = self.load_many("barrier_", 2)
        self.boss = self.load("boss.png")
        ground = self.load("ruined_asphalt.png", alpha=False)
        if ground:
            width, height = ground.get_size()
            ground = ground.subsurface((4, 4, width - 8, height - 8)).copy()
            ground = pygame.transform.smoothscale(ground, (283, 174))
        self.backgrounds = [ground] if ground else []
        self.background_tiles = (
            [
                ground,
                pygame.transform.flip(ground, True, False),
                pygame.transform.flip(ground, False, True),
                pygame.transform.flip(ground, True, True),
            ]
            if ground
            else []
        )
        self.cobblestone = self.load("cobblestone.png", alpha=False)
        self.debris = self.load("debris.png")
        self.spent_casings = self.load("spent_casings.png")
        self.blood_splatter = self.load("blood_splatter.png")
        self.sandbags = self.load("sandbags.png")
        self.abandoned_car = self.load("abandoned_car.png")
        self.oil_drums = self.load("oil_drums.png")
        self.vertical_barriers = [pygame.transform.rotate(image, 90) for image in self.barriers]
        self.backgrounds = [image for image in self.backgrounds if image]
        self.scale_cache = {}

    def load(self, filename, alpha=True):
        path = ASSET_DIR / filename
        if not path.exists():
            return None
        image = pygame.image.load(str(path))
        return image.convert_alpha() if alpha else image.convert()

    def load_many(self, prefix, count):
        return [img for img in (self.load(f"{prefix}{i}.png") for i in range(count)) if img]

    def scaled(self, image, size):
        if not image:
            return None
        key = (id(image), int(size[0]), int(size[1]))
        if key not in self.scale_cache:
            self.scale_cache[key] = pygame.transform.smoothscale(image, (max(1, int(size[0])), max(1, int(size[1]))))
        return self.scale_cache[key]


class Bullet:
    def __init__(self, pos, velocity, damage, pierce):
        self.pos = pygame.Vector2(pos)
        self.velocity = pygame.Vector2(velocity)
        self.damage = damage
        self.pierce = pierce
        self.radius = 5
        self.life = 1.25
        self.age = 0
        self.hit_ids = set()

    def update(self, dt):
        self.pos += self.velocity * dt
        self.life -= dt
        self.age += dt

    def draw(self, surface, camera):
        direction = safe_normalize(self.velocity)
        side = pygame.Vector2(-direction.y, direction.x)
        head = self.pos - camera + direction * 5
        flicker = math.sin(self.age * 58 + self.pos.x * 0.13)
        tail_length = 15 + (flicker + 1) * 3
        flame_width = 2.5 + (flicker + 1) * 0.7
        tail = head - direction * tail_length

        def point(position):
            return (round(position.x), round(position.y))

        outer_flame = (
            head + direction * 3,
            head - direction * 4 + side * flame_width,
            tail,
            head - direction * 4 - side * flame_width,
        )
        inner_flame = (
            head + direction * 2,
            head - direction * 3 + side * flame_width * 0.55,
            head - direction * (tail_length * 0.72),
            head - direction * 3 - side * flame_width * 0.55,
        )
        pygame.draw.polygon(surface, (224, 55, 18), [point(p) for p in outer_flame])
        pygame.draw.polygon(surface, (255, 132, 28), [point(p) for p in inner_flame])
        pygame.draw.line(
            surface,
            (255, 224, 91),
            point(head - direction * 2),
            point(head + direction * 4),
            3,
        )
        spark = head - direction * (7 + (flicker + 1) * 2) + side * flicker * 2
        pygame.draw.line(surface, (255, 239, 157), point(spark), point(spark - direction * 4), 1)

    @property
    def dead(self):
        return self.life <= 0 or not ARENA.inflate(180, 180).collidepoint(self.pos)


class Particle:
    def __init__(self, pos, color, speed=130):
        angle = random.random() * math.tau
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(math.cos(angle), math.sin(angle)) * random.uniform(35, speed)
        self.color = color
        self.life = random.uniform(0.22, 0.55)
        self.max_life = self.life
        self.radius = random.uniform(2, 5)

    def update(self, dt):
        self.pos += self.vel * dt
        self.vel *= 0.90
        self.life -= dt

    def draw(self, surface, camera):
        alpha = clamp(self.life / self.max_life, 0, 1)
        radius = max(1, int(self.radius * alpha))
        pygame.draw.circle(surface, self.color, self.pos - camera, radius)


class MedKit:
    def __init__(self, pos):
        self.pos = pygame.Vector2(pos)
        self.radius = 20
        self.heal = 28
        self.pulse = random.random() * math.tau

    def draw(self, surface, camera):
        p = self.pos - camera
        glow_radius = 28 + int(math.sin(pygame.time.get_ticks() / 180 + self.pulse) * 3)
        pygame.draw.circle(surface, (37, 86, 64), p, glow_radius)
        box = pygame.Rect(0, 0, 34, 28)
        box.center = (p.x, p.y)
        pygame.draw.rect(surface, (238, 242, 228), box, border_radius=5)
        pygame.draw.rect(surface, (150, 42, 48), box, 3, border_radius=5)
        pygame.draw.rect(surface, (214, 50, 62), (box.centerx - 4, box.y + 6, 8, 16), border_radius=2)
        pygame.draw.rect(surface, (214, 50, 62), (box.x + 9, box.centery - 4, 16, 8), border_radius=2)


class Campfire:
    def __init__(self, pos, phase=0):
        self.pos = pygame.Vector2(pos)
        self.phase = phase
        self.glow = pygame.Surface((112, 112), pygame.SRCALPHA)
        pygame.draw.circle(self.glow, (255, 75, 12, 12), (56, 56), 55)
        pygame.draw.circle(self.glow, (255, 104, 20, 18), (56, 56), 34)
        pygame.draw.circle(self.glow, (255, 160, 45, 22), (56, 56), 18)

    def draw(self, surface, camera):
        center = self.pos - camera
        if not surface.get_rect().inflate(112, 112).collidepoint(center):
            return

        x, y = round(center.x), round(center.y)
        surface.blit(self.glow, (x - 56, y - 56))
        for offset_x, offset_y in ((-13, 7), (-7, 12), (1, 13), (10, 9), (15, 3), (6, -1), (-6, 0)):
            pygame.draw.circle(surface, (72, 72, 68), (x + offset_x, y + offset_y), 4)
        pygame.draw.line(surface, (67, 43, 29), (x - 12, y + 9), (x + 12, y + 3), 7)
        pygame.draw.line(surface, (104, 62, 35), (x - 10, y + 3), (x + 10, y + 10), 6)

        time = pygame.time.get_ticks() * 0.001 + self.phase
        flicker = math.sin(time * 11) + math.sin(time * 17 + self.phase) * 0.35
        for index, offset_x in enumerate((-7, 0, 7)):
            height = 16 + (flicker + math.sin(time * 8 + index) * 0.5) * 3
            width = 5 + math.sin(time * 13 + index * 2) * 1.2
            base_y = y + 3
            tip_y = base_y - height - (index == 1) * 3
            points = tuple(
                (round(point_x), round(point_y))
                for point_x, point_y in (
                    (x + offset_x, tip_y),
                    (x + offset_x - width, base_y - 2),
                    (x + offset_x, base_y + 2),
                    (x + offset_x + width, base_y - 2),
                )
            )
            pygame.draw.polygon(surface, (213, 59, 17), points)
            inner = tuple(
                (round(point_x), round(point_y))
                for point_x, point_y in (
                    (x + offset_x, tip_y + height * 0.38),
                    (x + offset_x - width * 0.55, base_y - 1),
                    (x + offset_x + width * 0.55, base_y - 1),
                )
            )
            pygame.draw.polygon(surface, (255, 143, 28), inner)
        pygame.draw.ellipse(surface, (255, 218, 91), (x - 2, y - 2, 4, 8))


class Tree:
    def __init__(self, pos, radius, shade, seed):
        self.pos = pygame.Vector2(pos)
        self.radius = radius
        self.shade = shade
        rng = random.Random(seed)
        patterns = (
            (-0.48, -0.12, 0.40),
            (-0.38, -0.42, 0.38),
            (0.02, -0.52, 0.40),
            (0.43, -0.38, 0.40),
            (0.54, 0.02, 0.40),
            (0.34, 0.43, 0.41),
            (-0.08, 0.51, 0.40),
            (-0.48, 0.36, 0.40),
        )
        self.puffs = []
        for offset_x, offset_y, size in patterns:
            x = (offset_x + rng.uniform(-0.06, 0.06)) * radius
            y = (offset_y + rng.uniform(-0.06, 0.06)) * radius
            puff_radius = radius * size * rng.uniform(0.86, 1.08)
            puff_color = tuple(
                max(0, min(255, component + rng.randint(-8, 8)))
                for component in shade
            )
            marks = [
                (
                    rng.uniform(-0.48, 0.48) * puff_radius,
                    rng.uniform(-0.42, 0.42) * puff_radius,
                    rng.uniform(0.10, 0.17) * puff_radius,
                )
                for _ in range(3)
            ]
            self.puffs.append((x, y, puff_radius, puff_color, marks))

        self.margin = max(8, round(radius * 0.28))
        size = (radius + self.margin) * 2
        self.image = pygame.Surface((size, size), pygame.SRCALPHA)
        self.render_canopy()
        self.puffs.clear()

    def render_canopy(self):
        radius = self.radius
        x = y = radius + self.margin
        pygame.draw.ellipse(
            self.image,
            (12, 22, 18),
            (x - radius, round(y - radius * 0.45), radius * 2, round(radius * 1.65)),
        )
        pygame.draw.circle(self.image, (24, 54, 29), (x, y), radius)

        branch_color = (87, 55, 29)
        branch_width = max(3, round(radius * 0.13))
        for end_x, end_y in (
            (x - radius * 0.58, y - radius * 0.28),
            (x + radius * 0.60, y - radius * 0.20),
            (x - radius * 0.43, y + radius * 0.48),
            (x + radius * 0.42, y + radius * 0.50),
            (x + radius * 0.06, y - radius * 0.72),
        ):
            pygame.draw.line(
                self.image,
                branch_color,
                (x, y),
                (round(end_x), round(end_y)),
                branch_width,
            )
        pygame.draw.circle(self.image, (104, 67, 34), (x, y), max(4, round(radius * 0.2)))

        for offset_x, offset_y, puff_radius, color, marks in self.puffs:
            puff_x = round(x + offset_x)
            puff_y = round(y + offset_y)
            outline = (27, 67, 34)
            light = (
                min(255, color[0] + 28),
                min(255, color[1] + 42),
                min(255, color[2] + 12),
            )
            pygame.draw.circle(self.image, outline, (puff_x, puff_y), round(puff_radius + 2))
            pygame.draw.circle(self.image, color, (puff_x, puff_y), round(puff_radius))
            pygame.draw.circle(
                self.image,
                light,
                (round(puff_x - puff_radius * 0.2), round(puff_y - puff_radius * 0.22)),
                round(puff_radius * 0.68),
            )
            for mark_x, mark_y, mark_radius in marks:
                mark_rect = pygame.Rect(
                    round(puff_x + mark_x - mark_radius * 0.55),
                    round(puff_y + mark_y - mark_radius),
                    max(2, round(mark_radius * 1.1)),
                    max(3, round(mark_radius * 2)),
                )
                pygame.draw.ellipse(self.image, (190, 226, 111), mark_rect)

    def draw(self, surface, camera):
        center = self.pos - camera
        rect = self.image.get_rect(center=(round(center.x), round(center.y)))
        if surface.get_rect().colliderect(rect):
            surface.blit(self.image, rect)


class Zombie:
    next_id = 1

    def __init__(self, level, player_pos, assets=None, is_boss=False, obstacles=None):
        self.id = Zombie.next_id
        Zombie.next_id += 1
        self.level = level
        self.is_boss = is_boss
        self.radius = random.randint(18, 25) if not is_boss else 82
        self.max_health = (35 + level * 18) if not is_boss else 1250
        self.health = self.max_health
        self.speed = (85 + level * 10 + random.uniform(-8, 16)) if not is_boss else 96
        self.damage = (10 + level * 2) if not is_boss else 34
        self.attack_cooldown = 0
        self.color = (74, 148 + min(70, level * 8), 85)
        self.image = None
        if assets:
            if is_boss and assets.boss:
                self.image = assets.boss
            elif assets.zombies:
                self.image = random.choice(assets.zombies)
        self.pos = self.spawn_away_from(player_pos, obstacles)

    def spawn_away_from(self, player_pos, obstacles=None):
        obstacles = obstacles or []
        for _ in range(80):
            x = random.choice([random.uniform(ARENA.left, ARENA.left + 80), random.uniform(ARENA.right - 80, ARENA.right)])
            y = random.uniform(ARENA.top, ARENA.bottom)
            if random.random() < 0.5:
                x = random.uniform(ARENA.left, ARENA.right)
                y = random.choice([random.uniform(ARENA.top, ARENA.top + 80), random.uniform(ARENA.bottom - 80, ARENA.bottom)])
            pos = pygame.Vector2(x, y)
            if pos.distance_to(player_pos) > 520 and not any(circle_hits_rect(pos, self.radius, rect) for rect in obstacles):
                return pos
        return pygame.Vector2(random.choice([ARENA.left, ARENA.right]), random.uniform(ARENA.top, ARENA.bottom))

    def move_with_collisions(self, delta, obstacles):
        move_actor(self.pos, self.radius, delta, obstacles)

    def find_movement(self, desired, obstacles):
        if desired.length_squared() == 0:
            return desired
        test = pygame.Vector2(self.pos) + desired
        if not any(circle_hits_rect(test, self.radius + 4, rect) for rect in obstacles):
            return desired

        base = safe_normalize(desired)
        candidates = [
            pygame.Vector2(-base.y, base.x),
            pygame.Vector2(base.y, -base.x),
            safe_normalize(base + pygame.Vector2(-base.y, base.x) * 0.75),
            safe_normalize(base + pygame.Vector2(base.y, -base.x) * 0.75),
        ]
        best = pygame.Vector2()
        best_score = -999
        for candidate in candidates:
            movement = candidate * desired.length()
            probe = pygame.Vector2(self.pos) + movement
            blocked = any(circle_hits_rect(probe, self.radius + 4, rect) for rect in obstacles)
            score = candidate.dot(base) - (3 if blocked else 0)
            if score > best_score:
                best_score = score
                best = movement
        return best

    def update(self, dt, player, obstacles):
        direction = safe_normalize(player.pos - self.pos)
        desired = direction * self.speed * dt
        self.move_with_collisions(self.find_movement(desired, obstacles), obstacles)
        self.attack_cooldown = max(0, self.attack_cooldown - dt)

        if self.pos.distance_to(player.pos) < self.radius + player.radius and self.attack_cooldown <= 0:
            player.take_damage(self.damage)
            self.attack_cooldown = 0.72

    def draw(self, surface, camera):
        p = self.pos - camera
        shadow = pygame.Rect(0, 0, self.radius * 2, self.radius)
        shadow.center = (p.x, p.y + self.radius * 0.8)
        pygame.draw.ellipse(surface, (7, 9, 12), shadow)
        if self.image:
            scale = 2.15 if self.is_boss else 1.0 + self.level * 0.025
            width = self.radius * scale * (2.45 if self.is_boss else 2.15)
            height = self.radius * scale * (1.65 if self.is_boss else 2.05)
            image = pygame.transform.smoothscale(self.image, (int(width), int(height)))
            blit_center(surface, image, (p.x, p.y - self.radius * (0.12 if self.is_boss else 0.30)))
        else:
            pygame.draw.circle(surface, self.color, p, self.radius)
            pygame.draw.circle(surface, (38, 83, 49), p, self.radius, 3)

            eye_offset = pygame.Vector2(self.radius * 0.34, -self.radius * 0.20)
            pygame.draw.circle(surface, (244, 248, 224), p + eye_offset, 3)
            pygame.draw.circle(surface, (244, 248, 224), p + pygame.Vector2(-eye_offset.x, eye_offset.y), 3)

        bar_w = self.radius * 2
        ratio = self.health / self.max_health
        pygame.draw.rect(surface, (30, 20, 20), (p.x - self.radius, p.y - self.radius - 12, bar_w, 5), border_radius=2)
        pygame.draw.rect(surface, RED, (p.x - self.radius, p.y - self.radius - 12, bar_w * ratio, 5), border_radius=2)


class Player:
    def __init__(self, character, image=None):
        self.character = character
        self.image = image
        self.pos = pygame.Vector2(0, 0)
        self.radius = 22
        self.health = character.max_health
        self.invuln = 0
        self.last_shot = 0

    def move_with_collisions(self, delta, obstacles):
        move_actor(self.pos, self.radius, delta, obstacles)

    def update(self, dt, keys, obstacles):
        movement = pygame.Vector2(
            (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT]),
            (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP]),
        )
        self.move_with_collisions(safe_normalize(movement) * self.character.speed * dt, obstacles)
        self.invuln = max(0, self.invuln - dt)

    def take_damage(self, amount):
        if self.invuln > 0:
            return
        self.health = max(0, self.health - amount)
        self.invuln = 0.33

    def heal_between_levels(self):
        heal = 24 if self.character.name == "Medica" else 15
        self.health = min(self.character.max_health, self.health + heal)

    def draw(self, surface, camera, mouse_world):
        p = self.pos - camera
        aim = safe_normalize(mouse_world - self.pos)
        if aim.length_squared() == 0:
            aim = pygame.Vector2(1, 0)

        shadow = pygame.Rect(0, 0, 52, 20)
        shadow.center = (p.x, p.y + 18)
        pygame.draw.ellipse(surface, (7, 9, 12), shadow)

        if self.invuln > 0 and int(pygame.time.get_ticks() / 70) % 2 == 0:
            body = (255, 255, 255)
        else:
            body = self.character.color
        if self.image:
            image = pygame.transform.smoothscale(self.image, (78, 78))
            if aim.length_squared() > 0:
                angle = -math.degrees(math.atan2(aim.y, aim.x))
                image = pygame.transform.rotate(image, angle)
            blit_center(surface, image, p)
        else:
            pygame.draw.circle(surface, body, p, self.radius)
            pygame.draw.circle(surface, (18, 22, 27), p, self.radius, 3)
            shoulder = pygame.Vector2(-aim.y, aim.x)
            gun_start = p + aim * 22
            gun_end = p + aim * 48
            pygame.draw.line(surface, (49, 55, 65), gun_start + shoulder * 4, gun_end + shoulder * 4, 8)


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Noite dos 10 Niveis")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.assets = Assets()
        self.font = pygame.font.SysFont("segoeui", 22)
        self.small = pygame.font.SysFont("segoeui", 17)
        self.big = pygame.font.SysFont("segoeui", 56, bold=True)
        self.title = pygame.font.SysFont("segoeui", 72, bold=True)
        self.state = "menu"
        self.selected = 0
        self.player = None
        self.level = 1
        self.kills = 0
        self.total_kills = 0
        self.spawned = 0
        self.spawn_timer = 0
        self.zombies = []
        self.bullets = []
        self.particles = []
        self.medkits = []
        self.message_timer = 0
        self.camera = pygame.Vector2()
        self.mouse_world = pygame.Vector2()
        self.current_death = None
        self.ranking_error = None
        self.ranking_available = True
        try:
            self.death_history = load_ranking()
        except (OSError, ValueError) as exc:
            self.death_history = []
            self.ranking_error = f"Nao foi possivel carregar o ranking: {exc}"
            self.ranking_available = False
            print(self.ranking_error, file=sys.stderr)
        self.obstacle_props = [
            (pygame.Rect(-1435, -465, 210, 95), self.assets.sandbags),
            (pygame.Rect(960, -820, 220, 105), self.assets.abandoned_car),
            (pygame.Rect(1350, 740, 100, 82), self.assets.oil_drums),
        ]
        self.obstacles = self.create_obstacles() + [rect for rect, _ in self.obstacle_props]
        self.medkit_spawns = self.create_medkit_spawns()
        self.decals = self.create_decals()
        self.campfires = [
            Campfire((-370, -300), 0.4),
            Campfire((1060, 0), 1.8),
            Campfire((370, 630), 3.1),
        ]
        self.trees = self.create_trees()

    def create_obstacles(self):
        return [
            pygame.Rect(-1380, -900, 520, 62),
            pygame.Rect(-1380, -900, 62, 410),
            pygame.Rect(-1080, -610, 62, 420),
            pygame.Rect(-1080, -250, 430, 62),
            pygame.Rect(-1310, 215, 610, 62),
            pygame.Rect(-760, 215, 62, 510),
            pygame.Rect(-1260, 680, 360, 62),
            pygame.Rect(-560, -920, 62, 455),
            pygame.Rect(-560, -520, 515, 62),
            pygame.Rect(-110, -790, 62, 355),
            pygame.Rect(170, -920, 670, 62),
            pygame.Rect(780, -920, 62, 420),
            pygame.Rect(385, -550, 560, 62),
            pygame.Rect(385, -550, 62, 260),
            pygame.Rect(650, -210, 620, 62),
            pygame.Rect(1208, -210, 62, 440),
            pygame.Rect(920, 225, 360, 62),
            pygame.Rect(1020, 520, 390, 62),
            pygame.Rect(1348, 285, 62, 295),
            pygame.Rect(-210, -145, 420, 62),
            pygame.Rect(-210, -145, 62, 295),
            pygame.Rect(150, 90, 62, 390),
            pygame.Rect(-470, 455, 745, 62),
            pygame.Rect(-470, 455, 62, 380),
            pygame.Rect(490, 390, 62, 455),
            pygame.Rect(490, 790, 530, 62),
            pygame.Rect(-1450, -80, 120, 120),
            pygame.Rect(-920, -785, 112, 112),
            pygame.Rect(-875, 440, 104, 104),
            pygame.Rect(-265, 220, 112, 112),
            pygame.Rect(40, -845, 116, 116),
            pygame.Rect(515, -365, 108, 108),
            pygame.Rect(720, 125, 120, 120),
            pygame.Rect(1115, 705, 112, 112),
            pygame.Rect(-40, 705, 116, 116),
        ]

    def create_trees(self):
        rng = random.Random(2026)
        shades = ((43, 82, 48), (53, 91, 48), (42, 75, 53), (62, 96, 52))
        trees = []
        spacing = 78
        rows = (66, 128, 190, 252)

        def add_tree(pos):
            trees.append(
                Tree(
                    pos,
                    rng.randint(35, 49),
                    rng.choice(shades),
                    rng.randrange(1 << 30),
                )
            )

        for row, depth in enumerate(rows):
            for x in range(ARENA.left - 100, ARENA.right + 101, spacing):
                stagger = (row % 2) * (spacing // 2)
                add_tree(
                    (
                        x + stagger + rng.randint(-15, 15),
                        ARENA.top - depth + rng.randint(-18, 18),
                    )
                )
                add_tree(
                    (
                        x + stagger + rng.randint(-15, 15),
                        ARENA.bottom + depth + rng.randint(-18, 18),
                    )
                )

            for y in range(ARENA.top - 100, ARENA.bottom + 101, spacing):
                stagger = (row % 2) * (spacing // 2)
                add_tree(
                    (
                        ARENA.left - depth + rng.randint(-18, 18),
                        y + stagger + rng.randint(-15, 15),
                    )
                )
                add_tree(
                    (
                        ARENA.right + depth + rng.randint(-18, 18),
                        y + stagger + rng.randint(-15, 15),
                    )
                )
        return trees

    def create_medkit_spawns(self):
        return [
            (-1260, -390),
            (-1140, 520),
            (-690, -720),
            (-330, 350),
            (20, -330),
            (320, 650),
            (735, -710),
            (920, 50),
            (1280, 770),
            (1180, -470),
        ]

    def create_decals(self):
        rng = random.Random(137)
        decals = []
        images = (
            (self.assets.cobblestone, (190, 118), 8),
            (self.assets.debris, (72, 48), 12),
            (self.assets.blood_splatter, (48, 34), 10),
            (self.assets.spent_casings, (42, 30), 10),
        )
        for image, size, count in images:
            if not image:
                continue
            scaled = self.assets.scaled(image, size)
            for _ in range(count):
                for _ in range(40):
                    pos = pygame.Vector2(
                        rng.uniform(ARENA.left + 100, ARENA.right - 100),
                        rng.uniform(ARENA.top + 100, ARENA.bottom - 100),
                    )
                    if not any(circle_hits_rect(pos, max(size) / 2, rect) for rect in self.obstacles):
                        faded = scaled.copy()
                        faded.set_alpha(130 if image is self.assets.cobblestone else 190)
                        decals.append((faded, pos))
                        break
        return decals

    def reset_medkits(self):
        self.medkits = []
        for pos in self.medkit_spawns:
            point = pygame.Vector2(pos)
            if not any(circle_hits_rect(point, 26, rect) for rect in self.obstacles):
                self.medkits.append(MedKit(point))

    def start(self):
        image = self.assets.players[self.selected] if len(self.assets.players) > self.selected else None
        self.player = Player(CHARACTERS[self.selected], image)
        self.level = 1
        self.kills = 0
        self.total_kills = 0
        self.spawned = 0
        self.spawn_timer = 0
        self.zombies.clear()
        self.bullets.clear()
        self.particles.clear()
        self.reset_medkits()
        self.message_timer = 2.0
        self.current_death = None
        self.state = "playing"

    def record_death(self):
        entry = {
            "date": datetime.now().astimezone().isoformat(timespec="microseconds"),
            "character": self.player.character.name,
            "kills": self.total_kills,
            "score": self.total_kills,
            "level": self.level,
        }
        self.current_death = entry
        if not self.ranking_available:
            return

        self.death_history.append(entry)
        try:
            save_ranking(self.death_history)
        except OSError as exc:
            self.ranking_error = f"Nao foi possivel salvar o ranking: {exc}"
            self.ranking_available = False
            print(self.ranking_error, file=sys.stderr)

    def level_target(self):
        return 7 + self.level * 4

    def active_zombie_cap(self):
        return 5 + self.level * 2

    def weapon(self):
        return WEAPONS[self.level - 1]

    def shoot(self):
        name, damage, cooldown_ms, pellet_count, spread_deg, bullet_speed = self.weapon()
        now = pygame.time.get_ticks()
        cooldown_ms /= self.player.character.fire_bonus
        if now - self.player.last_shot < cooldown_ms:
            return
        self.player.last_shot = now

        direction = safe_normalize(self.mouse_world - self.player.pos)
        if direction.length_squared() == 0:
            direction = pygame.Vector2(1, 0)
        base_angle = math.atan2(direction.y, direction.x)
        count = pellet_count
        for i in range(count):
            offset = 0 if count == 1 else (i - (count - 1) / 2) * math.radians(spread_deg)
            offset += math.radians(random.uniform(-spread_deg * 0.22, spread_deg * 0.22))
            angle = base_angle + offset
            velocity = pygame.Vector2(math.cos(angle), math.sin(angle)) * bullet_speed
            self.bullets.append(Bullet(self.player.pos + direction * 50, velocity, damage, 1 if self.level >= 7 else 0))
        for _ in range(5):
            self.particles.append(Particle(self.player.pos + direction * 50, ACCENT, 220))

    def spawn_zombies(self, dt):
        target = self.level_target()
        if self.spawned >= target:
            return
        self.spawn_timer -= dt
        interval = max(0.20, 0.95 - self.level * 0.06)
        if self.spawn_timer <= 0 and len(self.zombies) < self.active_zombie_cap():
            is_boss = self.level == 10 and self.spawned == 0
            self.zombies.append(Zombie(self.level, self.player.pos, self.assets, is_boss, self.obstacles))
            self.spawned += 1
            self.spawn_timer = interval

    def update_playing(self, dt):
        keys = pygame.key.get_pressed()
        self.player.update(dt, keys, self.obstacles)
        self.camera.update(self.player.pos.x - WIDTH / 2, self.player.pos.y - HEIGHT / 2)
        self.mouse_world = pygame.Vector2(pygame.mouse.get_pos()) + self.camera

        if pygame.mouse.get_pressed(num_buttons=3)[0] or keys[pygame.K_SPACE]:
            self.shoot()

        self.spawn_zombies(dt)
        for zombie in self.zombies:
            zombie.update(dt, self.player, self.obstacles)
        for bullet in self.bullets:
            bullet.update(dt)
            if any(circle_hits_rect(bullet.pos, bullet.radius, rect) for rect in self.obstacles):
                bullet.life = 0
        for particle in self.particles:
            particle.update(dt)

        self.handle_bullet_hits()
        self.handle_medkits()
        self.bullets = [b for b in self.bullets if not b.dead]
        self.particles = [p for p in self.particles if p.life > 0]

        if self.player.health <= 0:
            self.record_death()
            self.state = "gameover"

        if self.state == "playing" and self.kills >= self.level_target() and not self.zombies:
            if self.level >= 10:
                self.state = "victory"
            else:
                self.level += 1
                self.kills = 0
                self.spawned = 0
                self.spawn_timer = 1.0
                self.player.heal_between_levels()
                self.message_timer = 2.1

        self.message_timer = max(0, self.message_timer - dt)

    def handle_bullet_hits(self):
        dead_zombies = []
        for bullet in self.bullets:
            for zombie in self.zombies:
                if zombie.id in bullet.hit_ids:
                    continue
                if bullet.pos.distance_to(zombie.pos) <= bullet.radius + zombie.radius:
                    zombie.health -= bullet.damage
                    bullet.hit_ids.add(zombie.id)
                    for _ in range(8):
                        self.particles.append(Particle(zombie.pos, (94, 168, 91), 160))
                    if zombie.health <= 0 and zombie not in dead_zombies:
                        dead_zombies.append(zombie)
                    if len(bullet.hit_ids) > bullet.pierce:
                        bullet.life = 0
                        break
        for zombie in dead_zombies:
            if zombie in self.zombies:
                self.zombies.remove(zombie)
                self.kills += 1
                self.total_kills += 1
                for _ in range(16):
                    self.particles.append(Particle(zombie.pos, (101, 196, 102), 260))

    def handle_medkits(self):
        remaining = []
        for kit in self.medkits:
            if self.player.pos.distance_to(kit.pos) <= self.player.radius + kit.radius:
                old_health = self.player.health
                self.player.health = min(self.player.character.max_health, self.player.health + kit.heal)
                if self.player.health > old_health:
                    for _ in range(18):
                        self.particles.append(Particle(kit.pos, (107, 235, 158), 190))
                else:
                    remaining.append(kit)
            else:
                remaining.append(kit)
        self.medkits = remaining

    def draw_grid(self):
        self.screen.fill(BG)
        bg = self.assets.backgrounds[0] if self.assets.backgrounds else None
        if bg:
            tile_w, tile_h = bg.get_size()
            start_x = math.floor(self.camera.x / tile_w) * tile_w
            start_y = math.floor(self.camera.y / tile_h) * tile_h
            for x in range(start_x, int(self.camera.x + WIDTH) + tile_w, tile_w):
                for y in range(start_y, int(self.camera.y + HEIGHT) + tile_h, tile_h):
                    tile_x = x // tile_w
                    tile_y = y // tile_h
                    variant = (tile_x * 3 + tile_y * 5) % len(self.assets.background_tiles)
                    self.screen.blit(
                        self.assets.background_tiles[variant],
                        (x - self.camera.x, y - self.camera.y),
                    )
            shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            shade.fill((10, 12, 16, 30))
            self.screen.blit(shade, (0, 0))
        self.draw_forest()
        self.draw_boundary()

    def draw_forest(self):
        forest_ground = ARENA.inflate(680, 680).move(-self.camera.x, -self.camera.y)
        pygame.draw.rect(self.screen, (20, 33, 27), forest_ground, 340)
        for tree in self.trees:
            tree.draw(self.screen, self.camera)

    def draw_boundary(self):
        arena = ARENA.move(-self.camera.x, -self.camera.y)
        wall = ARENA.inflate(52, 52).move(-self.camera.x, -self.camera.y)
        thickness = 26
        pygame.draw.rect(self.screen, (61, 70, 67), wall, thickness)
        pygame.draw.rect(self.screen, (116, 122, 103), wall, 2)
        pygame.draw.rect(self.screen, (34, 43, 40), arena, 2)

        block_colors = ((74, 84, 76), (82, 90, 78), (69, 80, 73))
        segment = 64
        for index, world_x in enumerate(range(ARENA.left, ARENA.right, segment)):
            x = round(world_x - self.camera.x)
            block_width = min(segment - 2, ARENA.right - world_x)
            for y in (wall.top, arena.bottom):
                block = pygame.Rect(x, y, block_width, thickness)
                if block.colliderect(self.screen.get_rect()):
                    pygame.draw.rect(self.screen, block_colors[index % len(block_colors)], block)
                    pygame.draw.line(self.screen, (105, 113, 95), block.topleft, (block.right - 1, block.top), 1)

        for index, world_y in enumerate(range(ARENA.top, ARENA.bottom, segment)):
            y = round(world_y - self.camera.y)
            block_height = min(segment - 2, ARENA.bottom - world_y)
            for x in (wall.left, arena.right):
                block = pygame.Rect(x, y, thickness, block_height)
                if block.colliderect(self.screen.get_rect()):
                    pygame.draw.rect(self.screen, block_colors[(index + 1) % len(block_colors)], block)
                    pygame.draw.line(self.screen, (105, 113, 95), block.topleft, (block.left, block.bottom - 1), 1)

    def draw_decals(self):
        for image, pos in self.decals:
            blit_center(self.screen, image, pos - self.camera)

    def draw_campfires(self):
        for campfire in self.campfires:
            campfire.draw(self.screen, self.camera)

    def draw_obstacles(self):
        props = {tuple(rect): image for rect, image in self.obstacle_props}
        for index, rect in enumerate(self.obstacles):
            screen_rect = rect.move(-self.camera.x, -self.camera.y)
            prop = props.get(tuple(rect))
            if prop:
                image = self.assets.scaled(prop, rect.size)
                self.screen.blit(image, screen_rect)
                continue

            is_crate = rect.width <= 125 and rect.height <= 125
            if is_crate:
                if self.assets.crates:
                    image = self.assets.scaled(self.assets.crates[index % len(self.assets.crates)], rect.size)
                    self.screen.blit(image, screen_rect)
                continue

            if self.assets.barriers:
                horizontal = rect.width >= rect.height
                source = self.assets.barriers[0] if horizontal else self.assets.vertical_barriers[0]
                tile_length = min(220, rect.width if horizontal else rect.height)
                tile_size = (tile_length, rect.height) if horizontal else (rect.width, tile_length)
                tile = self.assets.scaled(source, tile_size)
                old_clip = self.screen.get_clip()
                self.screen.set_clip(screen_rect)
                if horizontal:
                    for x in range(screen_rect.left, screen_rect.right, tile.get_width()):
                        self.screen.blit(tile, (x, screen_rect.top))
                else:
                    for y in range(screen_rect.top, screen_rect.bottom, tile.get_height()):
                        self.screen.blit(tile, (screen_rect.left, y))
                self.screen.set_clip(old_clip)
            else:
                pygame.draw.rect(self.screen, (88, 111, 48), screen_rect, border_radius=2)

    def draw_hud(self):
        pygame.draw.rect(self.screen, (20, 23, 28), (0, 0, WIDTH, 78))
        pygame.draw.line(self.screen, (58, 64, 74), (0, 78), (WIDTH, 78), 2)

        hp_ratio = self.player.health / self.player.character.max_health
        pygame.draw.rect(self.screen, (66, 25, 28), (28, 24, 245, 22), border_radius=6)
        pygame.draw.rect(self.screen, RED, (28, 24, 245 * hp_ratio, 22), border_radius=6)
        draw_text(self.screen, self.small, f"Vida {self.player.health}/{self.player.character.max_health}", TEXT, (36, 25))

        name, damage, cooldown, pellets, spread, speed = self.weapon()
        draw_text(self.screen, self.font, f"Nivel {self.level}/10", TEXT, (315, 19))
        draw_text(self.screen, self.small, f"Abates {self.kills}/{self.level_target()}", MUTED, (315, 46))
        draw_text(self.screen, self.font, name, ACCENT, (500, 19))
        draw_text(self.screen, self.small, f"Dano {damage}  Tiros {pellets}  Recarga {int(cooldown / self.player.character.fire_bonus)}ms", MUTED, (500, 46))
        draw_text(self.screen, self.font, self.player.character.name, self.player.character.color, (885, 19))
        draw_text(self.screen, self.small, "WASD move | Mouse mira | Clique/Espaco atira | Esc menu", MUTED, (885, 46))

        if self.message_timer > 0:
            text = f"Nivel {self.level}: zumbis mais fortes, arma melhorada"
            draw_text(self.screen, self.big, text, TEXT, (WIDTH / 2, 118), "midtop")

    def draw_playing(self):
        self.draw_grid()
        self.draw_decals()
        self.draw_obstacles()
        self.draw_campfires()
        for kit in self.medkits:
            kit.draw(self.screen, self.camera)
        for particle in self.particles:
            particle.draw(self.screen, self.camera)
        for bullet in self.bullets:
            bullet.draw(self.screen, self.camera)
        for zombie in sorted(self.zombies, key=lambda z: z.pos.y):
            zombie.draw(self.screen, self.camera)
        self.player.draw(self.screen, self.camera, self.mouse_world)
        self.draw_hud()

    def draw_menu(self):
        self.screen.fill((18, 21, 27))
        for i in range(0, WIDTH, 46):
            pygame.draw.line(self.screen, (24, 29, 37), (i, 0), (i - 260, HEIGHT), 1)
        draw_text(self.screen, self.title, "NOITE DOS 10 NIVEIS", TEXT, (WIDTH / 2, 58), "midtop")
        draw_text(self.screen, self.font, "Escolha um personagem e sobreviva a horda completa.", MUTED, (WIDTH / 2, 139), "midtop")

        preview = self.assets.backgrounds[0] if self.assets.backgrounds else None
        if preview:
            preview_area = pygame.Rect(0, int(HEIGHT * 0.42), WIDTH, int(HEIGHT * 0.58))
            old_clip = self.screen.get_clip()
            self.screen.set_clip(preview_area)
            for x in range(0, WIDTH, preview.get_width()):
                for y in range(preview_area.top, HEIGHT, preview.get_height()):
                    self.screen.blit(preview, (x, y))
            overlay = pygame.Surface(preview_area.size, pygame.SRCALPHA)
            overlay.fill((18, 21, 27, 175))
            self.screen.blit(overlay, preview_area.topleft)
            self.screen.set_clip(old_clip)

        card_w, card_h = 205, 260
        gap = 22
        total = card_w * len(CHARACTERS) + gap * (len(CHARACTERS) - 1)
        start_x = (WIDTH - total) / 2
        y = 225
        mouse = pygame.Vector2(pygame.mouse.get_pos())
        for i, char in enumerate(CHARACTERS):
            rect = pygame.Rect(start_x + i * (card_w + gap), y, card_w, card_h)
            hovered = rect.collidepoint(mouse)
            active = i == self.selected
            fill = (42, 49, 60) if active else PANEL
            if hovered:
                fill = (48, 56, 69)
            pygame.draw.rect(self.screen, fill, rect, border_radius=8)
            pygame.draw.rect(self.screen, char.color if active else (70, 78, 91), rect, 3, border_radius=8)
            image = self.assets.players[i] if len(self.assets.players) > i else None
            if image:
                image = pygame.transform.smoothscale(image, (88, 88))
                blit_center(self.screen, image, (rect.centerx, rect.y + 72))
            else:
                pygame.draw.circle(self.screen, char.color, (rect.centerx, rect.y + 70), 34)
                pygame.draw.circle(self.screen, (18, 22, 27), (rect.centerx, rect.y + 70), 34, 3)
            draw_text(self.screen, self.font, char.name, TEXT, (rect.centerx, rect.y + 122), "midtop")
            draw_text(self.screen, self.small, char.trait, MUTED, (rect.centerx, rect.y + 154), "midtop")
            draw_text(self.screen, self.small, f"Vida {char.max_health}", TEXT, (rect.x + 22, rect.y + 194))
            draw_text(self.screen, self.small, f"Vel {int(char.speed)}", TEXT, (rect.x + 22, rect.y + 219))

        draw_text(self.screen, self.font, "Enter para iniciar | 1-5 seleciona | Clique no card", ACCENT, (WIDTH / 2, 548), "midtop")
        draw_text(self.screen, self.small, "Progressao: cada nivel aumenta vida e velocidade dos zumbis; sua arma sobe junto.", MUTED, (WIDTH / 2, 588), "midtop")

    def draw_end(self, title, subtitle, color):
        self.screen.fill((17, 19, 24))
        draw_text(self.screen, self.title, title, color, (WIDTH / 2, 210), "midtop")
        draw_text(self.screen, self.font, subtitle, TEXT, (WIDTH / 2, 310), "midtop")
        draw_text(self.screen, self.font, "Enter reinicia | Esc volta ao menu", ACCENT, (WIDTH / 2, 370), "midtop")

    def draw_gameover(self):
        self.screen.fill((17, 19, 24))
        draw_text(self.screen, self.title, "FIM DE JOGO", RED, (WIDTH / 2, 25), "midtop")

        current = self.current_death
        if current:
            current_date = format_ranking_date(current["date"])
            draw_text(
                self.screen,
                self.font,
                f"Esta morte: {current['character']} | {current['kills']} zumbis | {current_date}",
                TEXT,
                (WIDTH / 2, 112),
                "midtop",
            )
            draw_text(
                self.screen,
                self.font,
                f"Pontos: {current['score']} | Nivel alcancado: {current['level']}",
                ACCENT,
                (WIDTH / 2, 145),
                "midtop",
            )

        current_index = next(
            (index for index, entry in enumerate(self.death_history) if entry is current),
            None,
        )
        if current_index is not None and current_index > 0:
            previous = self.death_history[current_index - 1]
        elif current_index is None and self.death_history:
            previous = self.death_history[-1]
        else:
            previous = None

        if previous:
            previous_text = (
                f"Morte anterior: {previous['character']} | {previous['kills']} zumbis | "
                f"{format_ranking_date(previous['date'])}"
            )
        else:
            previous_text = "Esta foi sua primeira morte registrada."
        draw_text(self.screen, self.small, previous_text, MUTED, (WIDTH / 2, 180), "midtop")

        ranked = sorted(
            self.death_history,
            key=lambda entry: (entry["score"], entry["date"]),
            reverse=True,
        )
        current_rank = next(
            (rank for rank, entry in enumerate(ranked, start=1) if entry is current),
            None,
        )
        visible = list(enumerate(ranked[:8], start=1))
        if current and not any(entry is current for _, entry in visible):
            visible = list(enumerate(ranked[:7], start=1)) + [(current_rank, current)]

        draw_text(
            self.screen,
            self.font,
            f"RANKING DE PONTOS (1 zumbi eliminado = 1 ponto) - {len(self.death_history)} partidas",
            ACCENT,
            (WIDTH / 2, 215),
            "midtop",
        )
        panel = pygame.Rect(80, 250, WIDTH - 160, 330)
        pygame.draw.rect(self.screen, PANEL, panel, border_radius=10)
        pygame.draw.rect(self.screen, (70, 78, 91), panel, 2, border_radius=10)

        columns = ((112, "Pos."), (205, "Personagem"), (490, "Pontos"), (630, "Abates"), (770, "Nivel"), (920, "Data"))
        for x, label in columns:
            draw_text(self.screen, self.small, label, MUTED, (x, 265))

        if not visible:
            draw_text(self.screen, self.font, "Nenhuma morte registrada ainda.", TEXT, (WIDTH / 2, 325), "midtop")
        else:
            for row, (rank, entry) in enumerate(visible):
                y = 298 + row * 32
                color = ACCENT if entry is current else TEXT
                rank_label = f"#{rank}" if rank else "Atual"
                draw_text(self.screen, self.small, rank_label, color, (112, y))
                draw_text(self.screen, self.small, entry["character"], color, (205, y))
                draw_text(self.screen, self.small, str(entry["score"]), color, (490, y))
                draw_text(self.screen, self.small, str(entry["kills"]), color, (630, y))
                draw_text(self.screen, self.small, str(entry["level"]), color, (770, y))
                draw_text(self.screen, self.small, format_ranking_date(entry["date"]), color, (920, y))

        if self.ranking_error:
            draw_text(self.screen, self.small, self.ranking_error, RED, (WIDTH / 2, 600), "midtop")
        draw_text(self.screen, self.font, "Enter: novo jogo | Esc: menu", ACCENT, (WIDTH / 2, 640), "midtop")

    def handle_menu_click(self, pos):
        card_w, card_h = 205, 260
        gap = 22
        total = card_w * len(CHARACTERS) + gap * (len(CHARACTERS) - 1)
        start_x = (WIDTH - total) / 2
        y = 225
        for i in range(len(CHARACTERS)):
            rect = pygame.Rect(start_x + i * (card_w + gap), y, card_w, card_h)
            if rect.collidepoint(pos):
                self.selected = i

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.state = "menu"
                    if self.state == "menu":
                        if pygame.K_1 <= event.key <= pygame.K_5:
                            self.selected = event.key - pygame.K_1
                        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            self.start()
                    elif self.state in ("gameover", "victory"):
                        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            self.start()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.state == "menu":
                        self.handle_menu_click(event.pos)

            if self.state == "playing":
                self.update_playing(dt)
                self.draw_playing()
            elif self.state == "menu":
                self.draw_menu()
            elif self.state == "gameover":
                self.draw_gameover()
            elif self.state == "victory":
                self.draw_end("VITORIA", "Voce limpou os 10 niveis da infestacao.", GREEN)

            pygame.display.flip()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()
