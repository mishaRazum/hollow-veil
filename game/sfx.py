"""Процедурные звуки: синтезируются при запуске, файлов-ассетов нет."""
import array
import math
import random

import pygame

RATE = 22050


class Sfx:
    def __init__(self):
        self.ok = False
        self.sounds = {}
        try:
            pygame.mixer.init(RATE, -16, 1, 512)
        except Exception:
            return
        try:
            self._build()
            self.ok = True
        except Exception:
            self.sounds = {}

    def _tone(self, dur, f0, f1, vol=0.35, shape='sine', noise=0.0):
        n = int(RATE * dur)
        buf = array.array('h')
        phase = 0.0
        for i in range(n):
            t = i / n
            f = f0 + (f1 - f0) * t
            phase += 2 * math.pi * f / RATE
            if shape == 'square':
                s = 1.0 if math.sin(phase) > 0 else -1.0
            else:
                s = math.sin(phase)
            if noise:
                s = s * (1 - noise) + noise * (random.random() * 2 - 1)
            env = max(0.0, 1.0 - t) ** 1.3
            buf.append(int(max(-1.0, min(1.0, s * env * vol)) * 32767))
        return buf.tobytes()

    def _build(self):
        def mk(dur, f0, f1, vol=0.35, shape='sine', noise=0.0):
            return pygame.mixer.Sound(buffer=self._tone(dur, f0, f1, vol, shape, noise))

        self.sounds = {
            'jump': mk(0.12, 280, 560, 0.22),
            'djump': mk(0.13, 380, 760, 0.22),
            'dash': mk(0.16, 900, 200, 0.2, noise=0.85),
            'slash': mk(0.07, 1400, 500, 0.16, noise=0.9),
            'hit': mk(0.08, 320, 120, 0.28, 'square'),
            'hurt': mk(0.25, 160, 60, 0.32, 'square'),
            'die': mk(0.4, 220, 40, 0.28),
            'geo': mk(0.06, 1100, 1500, 0.16),
            'heal': mk(0.4, 520, 880, 0.2),
            'bench': mk(0.5, 330, 495, 0.2),
            'pickup': mk(0.6, 392, 784, 0.24),
            'roar': mk(0.7, 90, 45, 0.36, 'square', noise=0.4),
            'bossdie': mk(0.9, 180, 30, 0.34),
        }

    def play(self, name, vol=1.0):
        if not self.ok:
            return
        snd = self.sounds.get(name)
        if snd is None:
            return
        try:
            snd.set_volume(max(0.0, min(1.0, vol)))
            snd.play()
        except Exception:
            pass
