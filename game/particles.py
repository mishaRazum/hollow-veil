"""Частицы: пыль, искры, души, следы."""
import math
import random

import pygame


class Particle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'life', 'max_life', 'color', 'size', 'grav', 'homing')

    def __init__(self, x, y, vx, vy, life, color, size, grav):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = vx, vy
        self.life = self.max_life = life
        self.color = color
        self.size = size
        self.grav = grav
        self.homing = False


class ParticleSystem:
    def __init__(self):
        self.parts = []

    def clear(self):
        self.parts.clear()

    def burst(self, pos, n, color, speed=2.0, life=24, size=2, grav=0.06, up=0.0):
        for _ in range(n):
            a = random.uniform(0, 6.28)
            s = random.uniform(speed * 0.3, speed)
            self.parts.append(Particle(pos[0], pos[1],
                                       math.cos(a) * s, math.sin(a) * s - up,
                                       int(life * random.uniform(0.6, 1.2)),
                                       color, size, grav))

    def soul_stream(self, pos, target, n=4):
        for _ in range(n):
            p = Particle(pos[0], pos[1], 0, 0, 40, (240, 246, 255), 2, 0)
            p.homing = True
            self.parts.append(p)

    def update(self, target=None):
        alive = []
        for p in self.parts:
            p.life -= 1
            if p.life <= 0:
                continue
            if p.homing and target is not None:
                tx, ty = target
                dx, dy = tx - p.x, ty - p.y
                d = max(1.0, (dx * dx + dy * dy) ** 0.5)
                p.vx += dx / d * 0.5
                p.vy += dy / d * 0.5
            p.vy += p.grav
            p.x += p.vx
            p.y += p.vy
            alive.append(p)
        self.parts = alive

    def draw(self, surf, ox, oy):
        for p in self.parts:
            a = max(0, min(255, int(255 * p.life / p.max_life)))
            col = (*p.color[:3], a) if len(p.color) == 3 else p.color
            s = pygame.Rect(int(p.x - ox), int(p.y - oy), p.size, p.size)
            try:
                surf.fill(col, s)
            except ValueError:
                surf.fill(p.color[:3], s)
