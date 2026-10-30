"""Враги: ползуны, летуны, босс «Дозорный Глубин», монеты и ударные волны."""
import math
import random

import pygame

from .settings import (TILE, GRAVITY, MAX_FALL, CRAWLER_HP, CRAWLER_GEO,
                       FLYER_HP, FLYER_GEO, BOSS_HP, BOSS_GEO, C)
from .world import move_and_collide


class Enemy:
    def __init__(self, x, y, w, h, hp, dmg, geo):
        self.rect = pygame.Rect(int(x), int(y), w, h)
        self.vx = self.vy = 0.0
        self.fx = self.fy = 0.0
        self.hp = hp
        self.max_hp = hp
        self.dmg = dmg
        self.geo = geo
        self.alive = True
        self.flash = 0
        self.last_swing = -1
        self.drop_t = 0

    def hurt(self, game, dmg, kx, swing_id):
        if not self.alive or self.last_swing == swing_id:
            return
        self.last_swing = swing_id
        self.hp -= dmg
        self.flash = 8
        self.vx += kx
        game.player.soul = min(99, game.player.soul + 11)
        game.particles.burst(self.rect.center, 6, C('mask'), speed=2.4, life=18)
        game.sfx.play('hit')
        if self.hp <= 0:
            self.die(game)

    def die(self, game):
        self.alive = False
        game.sfx.play('die')
        game.particles.burst(self.rect.center, 14, C('enemy_light'), speed=2.8, life=30)
        drop_coins(game, self.rect.center, self.geo)
        if game.boss is self:
            game.on_boss_defeated(self.rect.center)

    def physics(self, room):
        self.vy = min(MAX_FALL, self.vy + GRAVITY)
        return move_and_collide(room, self)

    def contact(self, game):
        p = game.player
        if self.alive and p.iframe == 0 and p.dash_t == 0 and self.rect.colliderect(p.rect):
            p.damage(game, self.dmg, self.rect.centerx)

    def update(self, game):
        raise NotImplementedError

    def draw(self, surf, ox, oy, t):
        raise NotImplementedError


def drop_coins(game, pos, total):
    n = min(6, max(1, total // 2))
    per = max(1, round(total / n))
    for _ in range(n):
        game.geo_drops.append(GeoDrop(pos[0], pos[1], per))


class GeoDrop:
    """Мешочек гео — притягивается к игроку."""

    def __init__(self, x, y, value):
        self.rect = pygame.Rect(int(x) - 3, int(y) - 3, 6, 6)
        self.vx = random.uniform(-2.2, 2.2)
        self.vy = random.uniform(-4.0, -2.0)
        self.fx = self.fy = 0.0
        self.value = value
        self.age = 0
        self.drop_t = 0
        self.alive = True

    def update(self, game):
        self.age += 1
        p = game.player
        d2 = ((p.rect.centerx - self.rect.centerx) ** 2 + (p.rect.centery - self.rect.centery) ** 2)
        if self.age > 12 and d2 < 80 * 80:
            d = max(1.0, d2 ** 0.5)
            self.vx += (p.rect.centerx - self.rect.centerx) / d * 0.55
            self.vy += (p.rect.centery - self.rect.centery) / d * 0.55
        else:
            self.vy = min(MAX_FALL, self.vy + GRAVITY)
        grounded, wall, _ = move_and_collide(game.room, self, use_plats=True)
        if grounded:
            self.vy = -abs(self.vy) * 0.45 if abs(self.vy) > 0.8 else 0
            self.vx *= 0.85
        if wall:
            self.vx = -self.vx * 0.6
        if d2 < 14 * 14 and self.age > 6:
            self.alive = False
            game.player.geo += self.value
            game.sfx.play('geo', 0.6)
        if self.age > 900:
            self.alive = False

    def draw(self, surf, ox, oy, t):
        r = self.rect.move(-ox, -oy)
        pygame.draw.polygon(surf, C('geo'), [(r.centerx, r.top), (r.right, r.centery),
                                             (r.centerx, r.bottom), (r.left, r.centery)])
        pygame.draw.polygon(surf, C('ui_back'), [(r.centerx, r.top), (r.right, r.centery),
                                                 (r.centerx, r.bottom), (r.left, r.centery)], 1)


class Crawler(Enemy):
    """Ползущий жук: ходит туда-сюда по земле."""

    def __init__(self, x, y):
        super().__init__(x, y - 12, 16, 12, CRAWLER_HP, 1, CRAWLER_GEO)
        self.dir = random.choice((-1, 1))
        self.knock_t = 0

    def update(self, game):
        room = game.room
        if self.knock_t > 0:
            self.knock_t -= 1
        else:
            self.vx = 0.6 * self.dir
        grounded, wall, _ = self.physics(room)
        if wall:
            self.dir = -self.dir
        elif grounded and self.knock_t == 0 and not self._ground_ahead(room):
            self.dir = -self.dir
        self.contact(game)
        self.flash = max(0, self.flash - 1)

    def _ground_ahead(self, room):
        ax = self.rect.centerx + self.dir * (self.rect.w // 2 + 4)
        ay = self.rect.bottom + 3
        tx, ty = ax // TILE, ay // TILE
        return room.is_blocked(tx, ty) or (tx, ty) in room.plats

    def draw(self, surf, ox, oy, t):
        r = self.rect.move(-ox, -oy)
        body = C('mask') if self.flash > 0 else C('enemy')
        # лапы
        step = (t // 8) % 2
        for i in range(4):
            lx = r.left + 2 + i * 4
            dy = 1 if (i % 2 == step) else 0
            pygame.draw.line(surf, body, (lx, r.bottom - 2), (lx + dy, r.bottom + 2), 1)
        # корпус и панцирь
        pygame.draw.ellipse(surf, body, r)
        shell = C('enemy_light')
        pygame.draw.arc(surf, shell, r.inflate(-2, -3), 0.5, 2.6, 1)
        pygame.draw.line(surf, shell, (r.centerx - 3, r.top + 2), (r.centerx - 3, r.centery), 1)
        pygame.draw.line(surf, shell, (r.centerx + 3, r.top + 2), (r.centerx + 3, r.centery), 1)
        # голова спереди
        hx = r.centerx + self.dir * 6
        pygame.draw.circle(surf, body, (hx, r.centery + 1), 4)
        # усики
        pygame.draw.line(surf, shell, (hx, r.top + 3), (hx + self.dir * 3, r.top - 2), 1)
        pygame.draw.line(surf, shell, (hx - self.dir * 2, r.top + 3),
                         (hx + self.dir, r.top - 2), 1)
        # глаз
        pygame.draw.rect(surf, C('enemy_eye'), (hx + self.dir - 1, r.centery - 2, 2, 2))


class Flyer(Enemy):
    """Летун: парит и кидается на игрока вблизи."""

    def __init__(self, x, y):
        super().__init__(x, y, 14, 12, FLYER_HP, 1, FLYER_GEO)
        self.home = pygame.Rect(x, y, 0, 0)
        self.t = random.uniform(0, 6.28)
        self.aggro = False

    def update(self, game):
        room = game.room
        self.t += 0.08
        p = game.player
        dx = p.rect.centerx - self.rect.centerx
        dy = p.rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)
        if dist < 150:
            self.aggro = True
        if self.aggro and dist > 320:
            self.aggro = False
        if self.aggro:
            d = max(1.0, dist)
            self.vx += dx / d * 0.07
            self.vy += dy / d * 0.07
            sp = math.hypot(self.vx, self.vy)
            if sp > 1.7:
                self.vx *= 1.7 / sp
                self.vy *= 1.7 / sp
        else:
            self.vx += (self.home.x + 7 - self.rect.centerx) * 0.002
            self.vy = math.sin(self.t) * 0.35
        move_and_collide(room, self, use_plats=False)
        if self.rect.left <= 0 or self.rect.right >= room.pw:
            self.vx *= -0.8
            self.rect.clamp(room.rect if hasattr(room, 'rect') else pygame.Rect(0, 0, room.pw, room.ph))
        self.contact(game)
        self.flash = max(0, self.flash - 1)

    def draw(self, surf, ox, oy, t):
        r = self.rect.move(-ox, -oy)
        body = C('mask') if self.flash > 0 else C('enemy')
        flap = (t // 5) % 3
        wing = C('enemy_light')
        # перепончатые крылья (3 фазы взмаха)
        wl = 7 + (flap == 0) * 2 - (flap == 2) * 2
        pygame.draw.polygon(surf, wing, [(r.left + 1, r.top + 2),
                                         (r.left - 5, r.top - wl), (r.left + 4, r.top - 1)])
        pygame.draw.polygon(surf, wing, [(r.right - 1, r.top + 2),
                                         (r.right + 5, r.top - wl), (r.right - 4, r.top - 1)])
        # тело с хвостиком
        pygame.draw.ellipse(surf, body, r)
        pygame.draw.polygon(surf, body, [(r.centerx - 2, r.bottom - 2),
                                         (r.centerx + 2, r.bottom - 2), (r.centerx, r.bottom + 3)])
        pygame.draw.ellipse(surf, wing, r.inflate(-6, -4), 1)
        # глаза
        pygame.draw.rect(surf, C('enemy_eye'), (r.centerx - 3, r.centery - 2, 2, 2))
        pygame.draw.rect(surf, C('enemy_eye'), (r.centerx + 1, r.centery - 2, 2, 2))


class Shockwave(Enemy):
    """Ударная волна босса — бежит по земле."""

    def __init__(self, x, y, dir_x):
        super().__init__(x, y - 10, 12, 10, 1, 1, 0)
        self.vx = 3.2 * dir_x
        self.age = 0
        self.flash = 0

    def update(self, game):
        self.age += 1
        self.vy = min(MAX_FALL, self.vy + GRAVITY)
        grounded, wall, _ = move_and_collide(game.room, self)
        if wall or self.age > 110 or self.rect.top > game.room.ph:
            self.alive = False
            return
        self.contact(game)

    def draw(self, surf, ox, oy, t):
        r = self.rect.move(-ox, -oy)
        col = C('boss_eye') if (t // 3) % 2 == 0 else C('boss_light')
        pygame.draw.polygon(surf, col, [(r.left, r.bottom), (r.centerx, r.top), (r.right, r.bottom)])


class Sentinel(Enemy):
    """Босс: ждёт, идёт, телеграфирует, таранит. Ниже половины HP — прыжки с волнами."""

    def __init__(self, x, y):
        super().__init__(x, y - 46, 44, 46, BOSS_HP, 1, BOSS_GEO)
        self.state = 'sleep'
        self.t = 0
        self.dir = -1
        self.flash = 0

    def activate(self, game):
        if self.state == 'sleep':
            self.state = 'walk'
            self.t = 70
            game.sfx.play('roar')
            game.message('ДОЗОРНЫЙ ГЛУБИН', 170, boss=True)
            game.on_boss_start()

    def update(self, game):
        room = game.room
        p = game.player
        self.t -= 1
        self.flash = max(0, self.flash - 1)

        if self.state == 'sleep':
            if p.rect.centerx > self.rect.left - 220:
                self.activate(game)
            return

        if self.state == 'walk':
            self.dir = 1 if p.rect.centerx > self.rect.centerx else -1
            self.vx = 0.9 * self.dir
            if self.t <= 0:
                if self.hp < self.max_hp / 2 and random.random() < 0.45:
                    self.state = 'leap'
                    self.vy = -8.2
                    self.vx = max(-3.5, min(3.5, (p.rect.centerx - self.rect.centerx) / 40))
                else:
                    self.state = 'telegraph'
                    self.t = 36
                    self.vx = 0
        elif self.state == 'telegraph':
            self.vx = 0
            self.dir = 1 if p.rect.centerx > self.rect.centerx else -1
            if self.t <= 0:
                self.state = 'charge'
                self.t = 40
                self.vx = 4.6 * self.dir
                game.sfx.play('roar', 0.7)
        elif self.state == 'charge':
            if self.t <= 0:
                self.state = 'walk'
                self.t = 80
        elif self.state == 'stagger':
            self.vx = 0
            if self.t <= 0:
                self.state = 'walk'
                self.t = 90

        grounded, wall, _ = self.physics(room)
        if self.state == 'leap' and grounded:
            game.shake = max(game.shake, 7)
            game.sfx.play('roar', 0.8)
            game.projectiles.append(Shockwave(self.rect.left, self.rect.bottom, -1))
            game.projectiles.append(Shockwave(self.rect.right, self.rect.bottom, 1))
            self.state = 'walk'
            self.t = 80
        if wall and self.state == 'charge':
            game.shake = max(game.shake, 8)
            game.sfx.play('hit', 0.8)
            self.state = 'stagger'
            self.t = 50
            game.particles.burst((self.rect.centerx + self.dir * 20, self.rect.centery),
                                 10, C('boss_eye'), speed=3, life=24)
        self.contact(game)

    def draw(self, surf, ox, oy, t):
        r = self.rect.move(-ox, -oy)
        body = C('mask') if self.flash > 0 else C('boss')
        # лапы
        step = (t // 10) % 2
        for i in range(3):
            lx = r.left + 6 + i * 13
            pygame.draw.line(surf, body, (lx, r.bottom - 6),
                             (lx + (2 if step else -2), r.bottom + 2), 2)
        # корпус и наплечники
        pygame.draw.ellipse(surf, body, (r.left, r.top + 8, r.w, r.h - 8))
        for sx in (r.left + 2, r.right - 12):
            pygame.draw.polygon(surf, C('boss_light'), [(sx, r.top + 14), (sx + 5, r.top + 4),
                                                        (sx + 10, r.top + 14)])
        pygame.draw.ellipse(surf, C('boss_light'), (r.left + 4, r.top + 14, r.w - 8, r.h - 22), 2)
        # рог
        pygame.draw.polygon(surf, C('boss_light'),
                            [(r.centerx - 6, r.top + 14), (r.centerx + self.dir * 10, r.top - 6),
                             (r.centerx + 6, r.top + 14)])
        # глаза
        glow = C('boss_eye')
        ex = r.centerx + self.dir * 8
        blink = self.state == 'telegraph' and (t // 4) % 2 == 0
        pygame.draw.circle(surf, (*glow, 70), (ex, r.top + 13), 5)
        pygame.draw.rect(surf, glow if not blink else C('mask'), (ex - 5, r.top + 12, 4, 3))
        pygame.draw.rect(surf, glow if not blink else C('mask'), (ex + 2, r.top + 12, 4, 3))
        # светящиеся трещины при половине HP
        if self.hp < self.max_hp / 2:
            pygame.draw.lines(surf, glow, False,
                              [(r.left + 8, r.top + 20), (r.left + 14, r.top + 26),
                               (r.left + 11, r.top + 33)], 1)
            pygame.draw.lines(surf, glow, False,
                              [(r.right - 10, r.top + 22), (r.right - 16, r.top + 29)], 1)
        # рывок: полоса
        if self.state == 'charge':
            pygame.draw.line(surf, C('boss_eye'), (r.left, r.centery), (r.right, r.centery), 1)
