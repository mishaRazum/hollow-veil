"""Мир: комнаты-тайлмапы, коллизии, переходы между комнатами.

Легенда символов карт:
  #  твёрдый блок          ^  шипы            -  сквозная платформа
  P  точка старта игрока   b  скамья          s  табличка с текстом
  e  ползущий враг         f  летающий враг   X  босс
  W  пикап «Крылья» (двойной прыжок)          D  пикап «Плащ» (рывок)
"""
import random

import pygame

from .settings import TILE, PALETTE


def _shade(color, amount):
    return tuple(max(0, min(255, c + amount)) for c in color[:3])


class Room:
    def __init__(self, name, spec):
        self.name = name
        self.display_name = spec.get('name', name)
        self.tint = spec.get('tint', (12, 16, 28))
        self.exits = spec.get('exits', {})
        self.sign_texts = spec.get('signs', [])
        self.locked = set()  # направления, закрытые в бою с боссом

        rows = [r for r in spec['map'].strip('\n').split('\n') if r.strip()]
        self.w = max(len(r) for r in rows)
        self.rows = [r.ljust(self.w, '.') for r in rows]
        self.h = len(self.rows)
        self.pw, self.ph = self.w * TILE, self.h * TILE

        self.solids = set()
        self.spikes = set()
        self.plats = set()
        self.spawn = None          # (px, py) точка новой игры
        self.benches = []          # [(tx, ty)]
        self.signs = []            # [(tx, ty, text)]
        self.pickups = []          # [(kind, tx, ty)]
        self.enemy_specs = []      # [(kind, tx, ty)]

        for y, row in enumerate(self.rows):
            for x, ch in enumerate(row):
                if ch == '#':
                    self.solids.add((x, y))
                elif ch == '^':
                    self.spikes.add((x, y))
                elif ch == '-':
                    self.plats.add((x, y))
                elif ch == 'P':
                    self.spawn = (x * TILE + 2, (y + 1) * TILE)
                elif ch == 'b':
                    self.benches.append((x, y))
                elif ch == 's':
                    text = self.sign_texts[len(self.signs)] if len(self.signs) < len(self.sign_texts) else '...'
                    self.signs.append((x, y, text))
                elif ch in 'efX':
                    self.enemy_specs.append((ch, x, y))
                elif ch in 'WD':
                    self.pickups.append((ch, x, y))

        self._build_tile_surf()
        self._build_parallax()

    # ---------- геометрия ----------
    def is_blocked(self, tx, ty):
        if 0 <= tx < self.w and 0 <= ty < self.h:
            return (tx, ty) in self.solids
        # за пределами комнаты стена, кроме стороны с открытым выходом
        if tx < 0 and 'left' in self.exits and 'left' not in self.locked:
            return False
        if tx >= self.w and 'right' in self.exits and 'right' not in self.locked:
            return False
        if ty < 0 and 'top' in self.exits and 'top' not in self.locked:
            return False
        if ty >= self.h and 'bottom' in self.exits and 'bottom' not in self.locked:
            return False
        return True

    def spike_tiles_in(self, rect):
        x0, x1 = rect.left // TILE, (rect.right - 1) // TILE
        y0, y1 = rect.top // TILE, (rect.bottom - 1) // TILE
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                if (tx, ty) in self.spikes:
                    return True
        return False

    # ---------- рендер ----------
    def _build_tile_surf(self):
        surf = pygame.Surface((self.pw, self.ph), pygame.SRCALPHA)
        surf.fill(self.tint)
        # фоновая кладка: тонкие швы кирпичей
        mortar = _shade(self.tint, -14)
        for ry, y in enumerate(range(0, self.ph, 12)):
            surf.fill(mortar, (0, y + 11, self.pw, 1))
            off = 12 if ry % 2 else 0
            for x in range(off, self.pw, 24):
                surf.fill(mortar, (x, y, 1, 11))

        rnd = random.Random(self.name)
        moss_c, moss_hi = PALETTE['moss'], PALETTE['moss_light']
        for (x, y) in sorted(self.solids):
            px, py = x * TILE, y * TILE
            base = PALETTE['tile'] if rnd.random() > 0.25 else PALETTE['tile_dark']
            surf.fill(base, (px, py, TILE, TILE))
            for _ in range(2):
                if rnd.random() < 0.5:
                    surf.fill(PALETTE['tile_dark'],
                              (px + rnd.randint(2, 12), py + rnd.randint(4, 12), 2, 2))
            top = (x, y - 1) not in self.solids
            left = (x - 1, y) not in self.solids
            right = (x + 1, y) not in self.solids
            bot = (x, y + 1) not in self.solids
            if top:
                surf.fill(PALETTE['rim'], (px, py, TILE, 2))
                surf.fill(PALETTE['rim_dim'], (px, py + 2, TILE, 1))
                for _ in range(3):  # кустики мха на кромке
                    if rnd.random() < 0.55:
                        mx = px + rnd.randint(1, 13)
                        h = rnd.randint(2, 4)
                        surf.fill(moss_c, (mx, py - h, 1, h))
                        if rnd.random() < 0.5:
                            surf.fill(moss_hi, (mx + 1, py - h + 1, 1, max(1, h - 1)))
            if left:
                surf.fill(PALETTE['rim_dim'], (px, py, 1, TILE))
            if right:
                surf.fill(PALETTE['tile_dark'], (px + TILE - 1, py, 1, TILE))
            if bot:
                surf.fill(PALETTE['tile_dark'], (px, py + TILE - 2, TILE, 2))
            if top and left:
                surf.fill(self.tint, (px, py, 2, 2))
            if top and right:
                surf.fill(self.tint, (px + TILE - 2, py, 2, 2))
        for (x, y) in sorted(self.plats):
            surf.fill(PALETTE['platform'], (x * TILE, y * TILE, TILE, 4))
            surf.fill(PALETTE['rim'], (x * TILE, y * TILE, TILE, 1))
            surf.fill(PALETTE['tile_dark'], (x * TILE, y * TILE + 4, TILE, 1))
        for (x, y) in sorted(self.spikes):
            cx = x * TILE
            base = y * TILE + TILE
            surf.fill(PALETTE['tile_dark'], (cx, base - 2, TILE, 2))
            for i in range(4):
                px = cx + i * 4
                pygame.draw.polygon(surf, PALETTE['spike'],
                                    [(px, base), (px + 2, base - 10), (px + 4, base)])
        self.tile_surf = surf

    def _build_parallax(self):
        """Слои фона: градиент с луной и колоннами, ближе — сталагмиты и лианы."""
        self.parallax = []
        w0 = int(640 + 0.25 * self.pw) + 80
        s0 = pygame.Surface((w0, self.ph), pygame.SRCALPHA)
        top_c, bot_c = _shade(self.tint, -8), _shade(self.tint, 16)
        for y in range(self.ph):
            k = y / max(1, self.ph - 1)
            c = tuple(int(top_c[i] + (bot_c[i] - top_c[i]) * k) for i in range(3))
            s0.fill((*c, 255), (0, y, w0, 1))
        mx, my, mr = int(w0 * 0.72), int(self.ph * 0.22), 24
        for i, a in ((30, 26), (22, 60)):
            pygame.draw.circle(s0, (*_shade(self.tint, 46), a), (mx, my), mr + i)
        pygame.draw.circle(s0, (*_shade(self.tint, 52), 200), (mx, my), mr)
        pygame.draw.circle(s0, (*_shade(self.tint, 28), 110), (mx - 6, my - 4), 4)
        rnd = random.Random(self.name + 'cols')
        col_c = (*_shade(self.tint, 20), 44)
        for x in range(20, w0, rnd.randint(80, 140)):
            h = rnd.randint(70, 170)
            pygame.draw.rect(s0, col_c, (x, self.ph - h, 12, h))
            pygame.draw.rect(s0, col_c, (x - 4, self.ph - h - 6, 20, 6))
            pygame.draw.rect(s0, col_c, (x - 4, self.ph - 8, 20, 6))
        self.parallax.append((0.25, s0))

        w1 = int(640 + 0.55 * self.pw) + 80
        s1 = pygame.Surface((w1, self.ph), pygame.SRCALPHA)
        rnd = random.Random(self.name + 'near')
        sil_c = (*_shade(self.tint, 24), 40)
        for x in range(0, w1, rnd.randint(16, 30)):
            h = rnd.randint(30, 130)
            pygame.draw.polygon(s1, sil_c, [(x, self.ph), (x + 12, self.ph - h), (x + 26, self.ph)])
            h2 = rnd.randint(18, 60)
            pygame.draw.polygon(s1, sil_c, [(x, 0), (x + 13, h2), (x + 28, 0)])
        vine_c = (*_shade(self.tint, 30), 70)
        for x in range(10, w1, rnd.randint(60, 120)):
            ln = rnd.randint(24, 64)
            pts = [(x + i * 3, 4 + int(i / max(1, ln // 3) * ln + 3 * ((i // 4) % 2)))
                   for i in range(1, ln // 3)]
            if len(pts) > 1:
                pygame.draw.lines(s1, vine_c, False, pts, 1)
        for _ in range(w1 // 90):
            x, y = rnd.randint(0, w1 - 3), rnd.randint(40, self.ph - 60)
            s1.fill((*PALETTE['rim'], 70), (x, y, 2, 2))
        self.parallax.append((0.55, s1))


# Общий алгоритм движения с коллизиями (используют игрок, враги, монеты)
def move_and_collide(room, ent, use_plats=True):
    """Двигает сущность по осям X и Y с разрешением коллизий.

    ent: объект с rect (pygame.Rect), vx, vy (float), fx, fy (дробные накопители).
    Возвращает (grounded, hit_wall, hit_ceiling).
    """
    grounded = hit_wall = hit_ceiling = False
    r = ent.rect

    ent.fx = getattr(ent, 'fx', 0.0) + ent.vx
    dx = int(ent.fx)
    ent.fx -= dx
    r.x += dx
    if dx:
        if dx > 0:
            col = (r.right - 1) // TILE
            for ty in range(r.top // TILE, (r.bottom - 1) // TILE + 1):
                if room.is_blocked(col, ty):
                    r.right = col * TILE
                    ent.vx = 0
                    hit_wall = True
                    break
        else:
            col = r.left // TILE
            for ty in range(r.top // TILE, (r.bottom - 1) // TILE + 1):
                if room.is_blocked(col, ty):
                    r.left = (col + 1) * TILE
                    ent.vx = 0
                    hit_wall = True
                    break

    prev_bottom = r.bottom
    ent.fy = getattr(ent, 'fy', 0.0) + ent.vy
    dy = int(ent.fy)
    ent.fy -= dy
    r.y += dy
    if dy > 0:
        row = (r.bottom - 1) // TILE
        for tx in range(r.left // TILE, (r.right - 1) // TILE + 1):
            solid = room.is_blocked(tx, row)
            plat = (use_plats and not getattr(ent, 'drop_t', 0)
                    and (tx, row) in room.plats and prev_bottom <= row * TILE + 4)
            if solid or plat:
                r.bottom = row * TILE
                ent.vy = 0
                grounded = True
                break
    elif dy < 0:
        row = r.top // TILE
        for tx in range(r.left // TILE, (r.right - 1) // TILE + 1):
            if room.is_blocked(tx, row):
                r.top = (row + 1) * TILE
                ent.vy = 0
                hit_ceiling = True
                break
    return grounded, hit_wall, hit_ceiling


def validate_levels(rooms):
    """Проверка карт: каждый выход ведёт в существующую комнату, точка выхода проходима."""
    problems = []
    for name, room in rooms.items():
        for d, ex in room.exits.items():
            target = rooms.get(ex['to'])
            if target is None:
                problems.append(f'{name}: {d} -> неизвестная комната {ex["to"]}')
                continue
            sx, sy = ex['sx'], ex['sy']
            if not (0 <= sx < target.pw and 0 <= sy < target.ph):
                problems.append(f'{name}: {d} -> точка выхода ({sx},{sy}) вне комнаты {ex["to"]}')
                continue
            if sy <= 8:
                continue  # точки «падения сверху» на опору не проверяем
            tx, ty = sx // TILE, sy // TILE
            # ty — уровень ног: под ним опора (твёрдый тайл или платформа),
            # над ним — свободное место для тела
            if not target.is_blocked(tx, ty) and (tx, ty) not in target.plats:
                problems.append(f'{name}: {d} -> под выходом в {ex["to"]} нет опоры ({tx},{ty})')
            if target.is_blocked(tx, ty - 1):
                problems.append(f'{name}: {d} -> выход в стену {ex["to"]} тайл ({tx},{ty - 1})')
    return problems


# ---------------------------------------------------------------------------
# УРОВНИ
# ---------------------------------------------------------------------------
LEVELS = {
    'awakening': {
        'name': 'Пробуждение',
        'tint': (16, 20, 34),
        'signs': ['AD/стрелки — движение · SPACE/Z — прыжок · J/X — удар · E — взаимодействие'],
        'exits': {'right': {'to': 'corridor', 'sx': 6, 'sy': 192}},
        'map': """
####################################
#..................................#
#..................................#
#..................................#
#..................................#
#..................................#
#..................................#
#..................................#
#..................................#
#.....................-----........#
#..................................#
#.....P...b....s....................
####################################
####################################
""",
    },
    'corridor': {
        'name': 'Разбитая галерея',
        'tint': (13, 17, 30),
        'signs': ['Впереди развилка. Слышен звон металла — но это не кузница...'],
        'exits': {'left': {'to': 'awakening', 'sx': 558, 'sy': 192},
                  'right': {'to': 'atrium', 'sx': 6, 'sy': 192}},
        'map': """
############################################################
#..........................................................#
#..........................................................#
#..........................................................#
#..........................................................#
#..........................................................#
#..........................................................#
#..........................................................#
#..................................f.......................#
#..........................................................#
............................................................
............s.................e.................e...........
######################..################...#################
######################^^################^^^#################
""",
    },
    'atrium': {
        'name': 'Затонувший атриум',
        'tint': (11, 15, 28),
        'signs': ['Колодец уводит в поющие пещеры. Наверху мерцает шахта огоньков.'],
        'exits': {'left': {'to': 'corridor', 'sx': 942, 'sy': 192},
                  'right': {'to': 'hall', 'sx': 6, 'sy': 192},
                  'top': {'to': 'shaft', 'sx': 176, 'sy': 384},
                  'bottom': {'to': 'caverns', 'sx': 432, 'sy': 4}},
        'map': """
############......############
#............................#
#............................#
#...........-----............#
#............................#
#............................#
#.......------...............#
#............................#
#............................#
#.............------.........#
..............................
.........................f....
#########............#########
#............................#
#............................#
#..................------....#
#............................#
#............................#
#...........-------..........#
#............................#
#............................#
#....------..................#
#............................#
#.......e.........s...e......#
##############...#############
##############...#############
""",
    },
    'shaft': {
        'name': 'Шахта огоньков',
        'tint': (9, 13, 26),
        'exits': {'top': {'to': 'atrium', 'sx': 224, 'sy': 48}},
        'map': """
#########....##########
#.....................#
#....W................#
#.-------.............#
#.....................#
#.....................#
#...........-------..#
#.....................#
#.....................#
#..-------...........#
#.....................#
#.....................#
#...........-------..#
#.....f...............#
#.....................#
#..-------...........#
#.....................#
#.....................#
#...........-------..#
#.....................#
#..............f.....#
#..-------...........#
#.....................#
#.....................#
######################
######################
""",
    },
    'hall': {
        'name': 'Зал Эхо',
        'tint': (16, 13, 28),
        'signs': ['Эхо повторяет шаги. Что-то сверкает высоко под потолком.'],
        'exits': {'left': {'to': 'atrium', 'sx': 462, 'sy': 192},
                  'right': {'to': 'sanctum', 'sx': 6, 'sy': 192}},
        'map': """
################################################################
#..............................................................#
#..............................................................#
#..............................................................#
#..............................................................#
#...................D..........................................#
#................########......................................#
#..............................................................#
#.............................f.............f..................#
#..............................................................#
................................................................
.....s............................e......................e......
###############################################.........########
###############################################^^^^^^^^^########
""",
    },
    'caverns': {
        'name': 'Поющие пещеры',
        'tint': (8, 11, 20),
        'signs': ['Здесь тихо. Скамья помнит всех, кто отдыхал.'],
        'exits': {'top': {'to': 'atrium', 'sx': 272, 'sy': 384}},
        'map': """
##########################....############################
#..........................................................#
#..........................................................#
#.......................--------...........................#
#..........................................................#
#.......................--------...........................#
#..........................................................#
#..........................................................#
#..............................--------....................#
#..........................................................#
#..........................................................#
#.......................--------...........................#
#...................f......................f...............#
#.....e..........................e..............s..b.....#
########...#############################....################
########^^^#############################^^^^################
""",
    },
    'sanctum': {
        'name': 'Святилище Дозорного',
        'tint': (22, 13, 16),
        'exits': {'left': {'to': 'hall', 'sx': 1006, 'sy': 192}},
        'map': """
########################################
#......................................#
#......................................#
#......................................#
#......................................#
#......................................#
#......................................#
#......................................#
#......................................#
#......................................#
.......................................#
.......................................#
######.................................#
#......-------.....-------.............#
#......................................#
#..............................X.......#
########################################
########################################
""",
    },
}


def build_rooms():
    return {name: Room(name, spec) for name, spec in LEVELS.items()}
