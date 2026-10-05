import math
import random
import sys
from dataclasses import dataclass
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
        self.zombies = self.load_many("zombie_", 6)
        self.boss = self.load("boss.png")
        self.backgrounds = [
            self.load("fundoreal.jpg", alpha=False),
            self.load("ambiente.png", alpha=False),
            self.load("local.png", alpha=False),
        ]
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
        self.hit_ids = set()

    def update(self, dt):
        self.pos += self.velocity * dt
        self.life -= dt

    def draw(self, surface, camera):
        p = self.pos - camera
        pygame.draw.circle(surface, (255, 236, 155), p, self.radius)
        pygame.draw.circle(surface, (255, 156, 78), p, 2)

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
            image = pygame.transform.smoothscale(self.image, (82, 62))
            if aim.length_squared() > 0:
                angle = -math.degrees(math.atan2(aim.y, aim.x)) + 180
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
        self.spawned = 0
        self.spawn_timer = 0
        self.zombies = []
        self.bullets = []
        self.particles = []
        self.medkits = []
        self.message_timer = 0
        self.camera = pygame.Vector2()
        self.mouse_world = pygame.Vector2()
        self.obstacles = self.create_obstacles()
        self.medkit_spawns = self.create_medkit_spawns()

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
        self.spawned = 0
        self.spawn_timer = 0
        self.zombies.clear()
        self.bullets.clear()
        self.particles.clear()
        self.reset_medkits()
        self.message_timer = 2.0
        self.state = "playing"

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
            self.state = "gameover"

        if self.kills >= self.level_target() and not self.zombies:
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
                    self.screen.blit(bg, (x - self.camera.x, y - self.camera.y))
            shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            shade.fill((10, 12, 16, 58))
            self.screen.blit(shade, (0, 0))
        tile = 80
        start_x = int((self.camera.x + ARENA.left) // tile) * tile
        end_x = int((self.camera.x + WIDTH + tile) // tile) * tile
        start_y = int((self.camera.y + ARENA.top) // tile) * tile
        end_y = int((self.camera.y + HEIGHT + tile) // tile) * tile
        for x in range(start_x, end_x + tile, tile):
            screen_x = x - self.camera.x
            color = (31, 36, 43) if x % (tile * 2) else (38, 43, 51)
            pygame.draw.line(self.screen, color, (screen_x, 0), (screen_x, HEIGHT))
        for y in range(start_y, end_y + tile, tile):
            screen_y = y - self.camera.y
            color = (31, 36, 43) if y % (tile * 2) else (38, 43, 51)
            pygame.draw.line(self.screen, color, (0, screen_y), (WIDTH, screen_y))
        arena_screen = ARENA.move(-self.camera.x, -self.camera.y)
        pygame.draw.rect(self.screen, (129, 126, 97), arena_screen, 6)
        pygame.draw.rect(self.screen, (27, 31, 38), arena_screen.inflate(-18, -18), 2)

    def draw_obstacles(self):
        for rect in self.obstacles:
            screen_rect = rect.move(-self.camera.x, -self.camera.y)
            is_crate = rect.width <= 125 and rect.height <= 125
            if is_crate:
                pygame.draw.rect(self.screen, (128, 86, 47), screen_rect, border_radius=3)
                pygame.draw.rect(self.screen, (72, 46, 29), screen_rect, 3, border_radius=3)
                pygame.draw.line(self.screen, (178, 126, 70), screen_rect.topleft, screen_rect.bottomright, 5)
                pygame.draw.line(self.screen, (178, 126, 70), screen_rect.topright, screen_rect.bottomleft, 5)
                pygame.draw.rect(self.screen, (80, 53, 34), screen_rect.inflate(-18, -18), 2, border_radius=2)
            else:
                pygame.draw.rect(self.screen, (88, 111, 48), screen_rect, border_radius=2)
                pygame.draw.rect(self.screen, (40, 57, 34), screen_rect, 3, border_radius=2)
                step = 34
                if rect.width >= rect.height:
                    for x in range(screen_rect.left, screen_rect.right, step):
                        pygame.draw.line(self.screen, (121, 143, 70), (x, screen_rect.top + 6), (x + 18, screen_rect.bottom - 6), 2)
                else:
                    for y in range(screen_rect.top, screen_rect.bottom, step):
                        pygame.draw.line(self.screen, (121, 143, 70), (screen_rect.left + 6, y), (screen_rect.right - 6, y + 18), 2)

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
        self.draw_obstacles()
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
            preview = pygame.transform.smoothscale(preview, (WIDTH, int(HEIGHT * 0.58)))
            preview.set_alpha(80)
            self.screen.blit(preview, (0, int(HEIGHT * 0.42)))

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
                image = pygame.transform.smoothscale(image, (108, 82))
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
                self.draw_end("FIM DE JOGO", "A horda venceu. Ajuste sua rota e tente de novo.", RED)
            elif self.state == "victory":
                self.draw_end("VITORIA", "Voce limpou os 10 niveis da infestacao.", GREEN)

            pygame.display.flip()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()
