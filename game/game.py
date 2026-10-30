"""Игровой цикл, состояния, камера, взаимодействия."""
import random

import pygame

from .settings import (INTERNAL_W, INTERNAL_H, WINDOW_W, WINDOW_H, STEP, TILE, MAX_HP, C)
from . import savegame
from .sfx import Sfx
from .player import Player
from .enemies import Crawler, Flyer, Sentinel
from .world import build_rooms, validate_levels
from .particles import ParticleSystem, Particle
from . import ui

KEY_ACTIONS = {}
for _action, _keys in {
    'left': (pygame.K_LEFT, pygame.K_a),
    'right': (pygame.K_RIGHT, pygame.K_d),
    'up': (pygame.K_UP, pygame.K_w),
    'down': (pygame.K_DOWN, pygame.K_s),
    'jump': (pygame.K_SPACE, pygame.K_z),
    'attack': (pygame.K_j, pygame.K_x),
    'dash': (pygame.K_k, pygame.K_c, pygame.K_LSHIFT),
    'heal': (pygame.K_f,),
    'interact': (pygame.K_e,),
    'map': (pygame.K_TAB,),
    'pause': (pygame.K_ESCAPE,),
    'confirm': (pygame.K_RETURN,),
    'newgame': (pygame.K_n,),
}.items():
    for _k in _keys:
        KEY_ACTIONS.setdefault(_k, []).append(_action)


class Input:
    def __init__(self):
        self.held = set()
        self.just = set()

    def feed_down(self, key):
        for a in KEY_ACTIONS.get(key, ()):
            self.held.add(a)
            self.just.add(a)

    def feed_up(self, key):
        for a in KEY_ACTIONS.get(key, ()):
            self.held.discard(a)

    def down(self, action):
        return action in self.held

    def pressed(self, action):
        return action in self.just


def make_vignette():
    small = pygame.Surface((160, 90), pygame.SRCALPHA)
    for y in range(90):
        for x in range(160):
            dx, dy = (x - 80) / 80.0, (y - 45) / 45.0
            dd = (dx * dx + dy * dy) ** 0.5
            a = int(max(0, min(140, (dd - 0.62) * 260)))
            small.set_at((x, y), (4, 5, 10, a))
    return pygame.transform.smoothscale(small, (INTERNAL_W, INTERNAL_H))


def make_fog():
    surf = pygame.Surface((INTERNAL_W, INTERNAL_H), pygame.SRCALPHA)
    for y in range(210, INTERNAL_H):
        a = int((y - 210) / (INTERNAL_H - 210) * 60)
        surf.fill((10, 14, 26, a), (0, y, INTERNAL_W, 1))
    return surf


class Game:
    def __init__(self):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption('Hollow Veil')
        self.window = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        self.screen = pygame.Surface((INTERNAL_W, INTERNAL_H)).convert()
        self.vignette = make_vignette()
        self.fog = make_fog()
        self.fonts = ui.make_fonts()
        self.sfx = Sfx()
        self.clock = pygame.time.Clock()

        self.rooms = build_rooms()
        problems = validate_levels(self.rooms)
        if problems:
            raise RuntimeError('Ошибки в картах: ' + '; '.join(problems))

        self.map_pos = {'awakening': (0, 0), 'corridor': (1, 0), 'atrium': (2, 0),
                        'shaft': (2, -1), 'hall': (3, 0), 'caverns': (2, 1), 'sanctum': (4, 0)}

        self.input = Input()
        self.particles = ParticleSystem()
        self.running = True
        self.tick = 0
        self.state = 'title'
        self.show_map = False
        self.messages = []
        self.death_t = 0
        self.deaths = 0
        self.playtime = 0.0
        self.visited = set()
        self.collected = set()
        self.boss_dead = False
        self.boss = None
        self.seal_pos = None
        self.interact_target = None
        self.trans_cd = 0
        self.trans_fade = 0.0
        self.shake = 0
        self.cam_x = self.cam_y = 0.0

        self.player = None
        self.room = None
        self.room_name = None
        self.geo_drops = []
        self.projectiles = []

    # ---------- запуск игр ----------
    def has_save(self):
        return savegame.load() is not None

    def new_game(self):
        room = self.rooms['awakening']
        self.player = Player(*room.spawn)
        self.player.spawn = ('awakening', room.spawn[0], room.spawn[1] - 20)
        self.visited = set()
        self.collected = set()
        self.boss_dead = False
        self.playtime = 0.0
        self.load_room('awakening')
        self.state = 'play'

    def load_save(self):
        data = savegame.load()
        if not data:
            self.new_game()
            return
        self.new_game()  # базовая инициализация
        savegame.apply(self, data)
        self.load_room(data.get('room', 'awakening'),
                       (int(data.get('x', 0)), int(data.get('y', 0))))
        self.state = 'play'

    def load_room(self, name, pos=None):
        room = self.rooms[name]
        self.room_name = name
        self.room = room
        room.locked.clear()
        self.visited.add(name)
        self._enemies = []  # враги не переносятся между комнатами
        self.geo_drops.clear()
        self.projectiles.clear()
        self.particles.clear()
        self.messages.clear()
        self.seal_pos = None
        self.boss = None

        for kind, tx, ty in room.enemy_specs:
            x, y = tx * TILE, (ty + 1) * TILE
            if kind == 'e':
                self.room_enemies().append(Crawler(x, y))
            elif kind == 'f':
                self.room_enemies().append(Flyer(x, y))
            elif kind == 'X' and not self.boss_dead:
                self.boss = Sentinel(x, y)
                self.room_enemies().append(self.boss)

        if self.boss is None and name == 'sanctum' and self.boss_dead:
            self.seal_pos = (room.pw // 2, 16 * TILE - 20)

        if pos is not None:
            self.player.rect.topleft = pos
            self.player.last_safe = pos
        self.player.vx = self.player.vy = 0
        self.player.dash_t = 0
        self.trans_cd = 30
        self.trans_fade = 0.7
        self.message(room.display_name, 150)
        self.update_camera(instant=True)

    def room_enemies(self):
        if not hasattr(self, '_enemies'):
            self._enemies = []
        return self._enemies

    # ---------- сообщения ----------
    def message(self, text, dur=150, big=False, boss=False):
        self.messages.append({'text': text, 'dur': dur, 't': 0, 'big': big, 'boss': boss})

    # ---------- босс ----------
    def on_boss_start(self):
        self.room.locked.add('left')
        savegame.save(savegame.collect(self))

    def on_boss_defeated(self, pos):
        self.boss_dead = True
        self.boss = None
        self.room.locked.discard('left')
        self.seal_pos = (self.room.pw // 2, 16 * TILE - 20)
        self.shake = 12
        self.sfx.play('bossdie')
        self.message('ДОЗОРНЫЙ ПОВЕРЖЕН', 200, big=True, boss=True)
        self.particles.burst(pos, 30, C('boss_eye'), speed=4, life=60)
        savegame.save(savegame.collect(self))

    # ---------- взаимодействия ----------
    def find_interact(self):
        p = self.player
        best = None
        best_d = 34 * 34
        for (tx, ty) in self.room.benches:
            cx, cy = tx * TILE + 8, ty * TILE + 10
            d = (p.rect.centerx - cx) ** 2 + (p.rect.centery - cy) ** 2
            if d < best_d:
                best, best_d = ('bench', cx, cy, 'Отдых'), d
        for (tx, ty, text) in self.room.signs:
            cx, cy = tx * TILE + 8, ty * TILE + 8
            d = (p.rect.centerx - cx) ** 2 + (p.rect.centery - cy) ** 2
            if d < best_d:
                best, best_d = ('sign', cx, cy, 'Читать'), d
        for (kind, tx, ty) in self.room.pickups:
            pid = f'{self.room_name}:{kind}:{tx},{ty}'
            if pid in self.collected:
                continue
            cx, cy = tx * TILE + 8, ty * TILE + 8
            d = (p.rect.centerx - cx) ** 2 + (p.rect.centery - cy) ** 2
            if d < best_d:
                label = 'Взять крылья' if kind == 'W' else 'Взять плащ'
                best, best_d = (kind, cx, cy, label), d
        return best

    def do_interact(self, target):
        kind, cx, cy, label = target
        p = self.player
        if kind == 'bench':
            p.hp = MAX_HP
            p.spawn = (self.room_name, float(p.rect.x), float(p.rect.y))
            self.sfx.play('bench')
            self.message('Отдых у скамьи. Прогресс сохранён.')
            self.particles.burst((cx, cy), 10, C('soul'), speed=1.6, life=36)
            savegame.save(savegame.collect(self))
        elif kind == 'sign':
            for (tx, ty, text) in self.room.signs:
                if tx * TILE + 8 == cx and ty * TILE + 8 == cy:
                    self.message(text, 260)
                    break
        elif kind in 'WD':
            pid = f'{self.room_name}:{kind}:{int((cx - 8) / TILE)},{int((cy - 8) / TILE)}'
            self.collected.add(pid)
            if kind == 'W':
                p.abilities['wings'] = True
                self.message('КРЫЛЬЯ ТКАЧА: прыжок в воздухе — двойной прыжок', 240, big=True)
            else:
                p.abilities['dash'] = True
                self.message('ПЛАЩ ТЕНИ: K/C/Shift — рывок', 240, big=True)
            self.sfx.play('pickup')
            self.particles.burst((cx, cy), 18, C('accent'), speed=2.4, life=44)
            savegame.save(savegame.collect(self))

    # ---------- переходы комнат ----------
    def check_transitions(self):
        if self.trans_cd > 0:
            return
        p = self.player
        room = self.room
        ex = room.exits
        target = None
        if p.rect.right <= 0 and 'left' in ex:
            target = ex['left']
        elif p.rect.left >= room.pw and 'right' in ex:
            target = ex['right']
        elif p.rect.top < 0 and 'top' in ex:
            target = ex['top']
        elif p.rect.top > room.ph and 'bottom' in ex:
            target = ex['bottom']
        if target:
            self.load_room(target['to'], (int(target['sx']), int(target['sy']) - p.rect.h))

    # ---------- камера ----------
    def update_camera(self, instant=False):
        room = self.room
        p = self.player

        def axis(pos, size, view):
            half = (size - view) / 2
            if half < 0:
                return half  # комната меньше экрана — центрируем
            return max(0, min(half, pos - view / 2))

        tx = axis(p.rect.centerx, room.pw, INTERNAL_W)
        ty = axis(p.rect.centery, room.ph, INTERNAL_H)
        if instant:
            self.cam_x, self.cam_y = tx, ty
        else:
            self.cam_x += (tx - self.cam_x) * 0.16
            self.cam_y += (ty - self.cam_y) * 0.16

    # ---------- шаг симуляции ----------
    def step(self):
        self.tick += 1
        for m in self.messages:
            m['t'] += 1
        self.messages = [m for m in self.messages if m['t'] < m['dur']]

        if self.state == 'title':
            if self.input.pressed('confirm'):
                self.load_save()
            elif self.input.pressed('newgame'):
                savegame.clear()
                self.new_game()
            elif self.input.pressed('pause'):
                self.running = False

        elif self.state == 'play':
            self.update_play()

        elif self.state == 'pause':
            if self.input.pressed('pause'):
                self.state = 'play'

        elif self.state == 'dead':
            self.death_t += 1
            if self.death_t == 50:
                self.respawn()
            elif self.death_t > 105:
                self.state = 'play'

        elif self.state == 'victory':
            if self.input.pressed('confirm'):
                self.state = 'title'

        self.input.just.clear()

    def update_play(self):
        self.playtime += STEP
        self.trans_cd = max(0, self.trans_cd - 1)
        self.trans_fade = max(0.0, self.trans_fade - 0.12)
        self.shake *= 0.85
        if self.shake < 0.3:
            self.shake = 0

        # фоновые пылинки в воздухе
        if self.tick % 5 == 0 and len(self.particles.parts) < 300:
            self.particles.parts.append(Particle(
                self.cam_x + random.uniform(0, INTERNAL_W),
                self.cam_y + random.uniform(0, INTERNAL_H),
                random.uniform(-0.08, 0.08), random.uniform(-0.16, -0.05),
                150, (*C('rim'), 55), 1, 0.0))

        if self.input.pressed('pause'):
            self.state = 'pause'
            return
        if self.input.pressed('map'):
            self.show_map = not self.show_map
        if self.show_map:
            return  # мир на паузе под картой

        p = self.player
        p.update(self)

        # удары игрока по врагам
        box = p.attack_box
        if box:
            for e in self.room_enemies():
                if e.alive and e.rect.colliderect(box):
                    e.hurt(self, 1, 2.2 * (1 if e.rect.centerx >= p.rect.centerx else -1),
                           p.swing_id)

        for e in self.room_enemies():
            if e.alive:
                e.update(self)
        self._enemies = [e for e in self.room_enemies() if e.alive]

        for proj in self.projectiles:
            proj.update(self)
        self.projectiles = [pr for pr in self.projectiles if pr.alive]

        for g in self.geo_drops:
            g.update(self)
        self.geo_drops = [g for g in self.geo_drops if g.alive]

        # взаимодействия
        self.interact_target = self.find_interact()
        if self.interact_target and self.input.pressed('interact'):
            self.do_interact(self.interact_target)

        # печать после босса
        if self.seal_pos and self.player.hp > 0:
            dx = p.rect.centerx - self.seal_pos[0]
            dy = p.rect.centery - self.seal_pos[1]
            if dx * dx + dy * dy < 18 * 18:
                self.state = 'victory'
                savegame.save(savegame.collect(self))
                return

        # смерть
        if p.hp <= 0:
            self.state = 'dead'
            self.death_t = 0
            self.deaths += 1
            self.sfx.play('die')
            self.particles.burst(p.rect.center, 24, C('mask'), speed=3.4, life=50)
            return

        self.check_transitions()
        self.update_camera()
        self.particles.update(p.rect.center)

    def respawn(self):
        name, x, y = self.player.spawn
        self.player.hp = MAX_HP
        self.player.iframe = 60
        self.load_room(name, (int(x), int(y)))
        savegame.save(savegame.collect(self))

    # ---------- отрисовка ----------
    def draw(self):
        s = self.screen
        if self.state == 'title':
            ui.draw_title(s, self)
        elif self.state == 'victory':
            ui.draw_victory(s, self)
        else:
            self.draw_world(s)
            ui.draw_hud(s, self)
            ui.draw_boss_bar(s, self)
            ui.draw_messages(s, self)
            ui.draw_world_overlays(s, self)
            if self.show_map and self.state == 'play':
                ui.draw_map(s, self)
            if self.state == 'pause':
                ui.draw_pause(s, self)
            if self.state == 'dead':
                ui.draw_death(s, self)

        pygame.transform.scale(s, (WINDOW_W, WINDOW_H), self.window)
        pygame.display.flip()

    def draw_world(self, s):
        room = self.room
        shake = int(self.shake)
        ox = int(self.cam_x) - shake // 2 + (self.tick % 3 if shake else 0)
        oy = int(self.cam_y) - shake // 2 + ((self.tick * 7) % 3 if shake else 0)

        s.fill(room.tint)
        for factor, layer in room.parallax:
            s.blit(layer, (-int(self.cam_x * factor), -int(self.cam_y * factor * 0.5)))
        s.blit(room.tile_surf, (-ox, -oy))

        self.draw_props(s, ox, oy)

        for g in self.geo_drops:
            g.draw(s, ox, oy, self.tick)
        for e in self.room_enemies():
            e.draw(s, ox, oy, self.tick)
        for pr in self.projectiles:
            pr.draw(s, ox, oy, self.tick)
        self.player.draw(s, ox, oy, self.tick)
        self.particles.draw(s, ox, oy)

        if self.seal_pos:
            sx, sy = self.seal_pos[0] - ox, self.seal_pos[1] - oy
            r = 8 + (self.tick % 30) // 6
            pygame.draw.circle(s, C('accent'), (int(sx), int(sy)), r, 1)
            pygame.draw.circle(s, C('mask'), (int(sx), int(sy)), 4)

        s.blit(self.fog, (0, 0))
        s.blit(self.vignette, (0, 0))
        if self.trans_fade > 0:
            fade = pygame.Surface((INTERNAL_W, INTERNAL_H))
            fade.fill((4, 5, 10))
            fade.set_alpha(int(255 * min(1.0, self.trans_fade * 1.4)))
            s.blit(fade, (0, 0))

    def draw_props(self, s, ox, oy):
        for (tx, ty) in self.room.benches:
            x, y = tx * TILE - ox, ty * TILE - oy
            pulse = (self.tick % 60) < 30
            # фонарь
            pygame.draw.rect(s, C('rim_dim'), (x + 12, y - 6, 1, 12))
            lamp = C('accent') if pulse else (*C('accent'), 120)
            pygame.draw.circle(s, lamp, (x + 12, y - 8), 2)
            if pulse:
                pygame.draw.circle(s, (*C('accent'), 60), (x + 12, y - 8), 5, 1)
            # скамья
            pygame.draw.rect(s, C('rim'), (x + 1, y + 8, 14, 3))
            pygame.draw.rect(s, C('rim_dim'), (x + 3, y + 11, 2, 5))
            pygame.draw.rect(s, C('rim_dim'), (x + 11, y + 11, 2, 5))
            pygame.draw.rect(s, C('rim'), (x + 1, y + 4, 3, 6))
            if pulse:
                pygame.draw.circle(s, (*C('soul'), 28), (x + 7, y + 6), 9, 1)
        for (tx, ty, _) in self.room.signs:
            x, y = tx * TILE - ox, ty * TILE - oy
            pygame.draw.rect(s, C('rim_dim'), (x + 7, y + 6, 2, 10))
            pygame.draw.rect(s, C('rim'), (x + 3, y + 2, 10, 6))
            pygame.draw.rect(s, C('rim_dim'), (x + 5, y + 4, 6, 1))
            pygame.draw.rect(s, C('rim_dim'), (x + 5, y + 6, 4, 1))
        for (kind, tx, ty) in self.room.pickups:
            pid = f'{self.room_name}:{kind}:{tx},{ty}'
            if pid in self.collected:
                continue
            bob = (self.tick // 16) % 2
            x, y = tx * TILE + 8 - ox, ty * TILE + 8 - oy - bob
            a0 = (self.tick * 0.05) % 6.28
            for i in range(4):  # вращающиеся сегменты кольца
                pygame.draw.arc(s, C('accent'),
                                (x - 10, y - 10, 20, 20), a0 + i * 1.57, a0 + i * 1.57 + 0.9, 1)
            pygame.draw.circle(s, (*C('mask'), 40), (x, y), 6)
            if kind == 'W':
                pygame.draw.polygon(s, C('mask'), [(x - 5, y + 3), (x, y - 5), (x - 1, y + 4)])
                pygame.draw.polygon(s, C('mask'), [(x + 5, y + 3), (x, y - 5), (x + 1, y + 4)])
            else:
                pygame.draw.lines(s, C('mask'), False,
                                  [(x - 4, y - 4), (x + 1, y), (x - 3, y + 4)], 2)

    # ---------- главный цикл ----------
    def run(self):
        acc = 0.0
        while self.running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                elif ev.type == pygame.KEYDOWN:
                    self.input.feed_down(ev.key)
                elif ev.type == pygame.KEYUP:
                    self.input.feed_up(ev.key)
            acc += min(self.clock.tick(60) / 1000.0, 0.1)
            while acc >= STEP:
                self.step()
                acc -= STEP
            self.draw()
        pygame.quit()
