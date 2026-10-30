"""Игрок: движение, бой, способности."""
import pygame

from .settings import (TILE, GRAVITY, MAX_FALL, WALK_SPEED, ACCEL, FRICTION,
                       JUMP_VEL, DJUMP_VEL, JUMP_EXTRA_GRAV, COYOTE, JUMP_BUFFER,
                       DASH_SPEED, DASH_TIME, DASH_COOLDOWN, ATTACK_COOLDOWN,
                       ATTACK_ACTIVE_FROM, ATTACK_ACTIVE_TO, ATTACK_BOX,
                       IFRAMES, MAX_HP, MAX_SOUL, HEAL_COST, HEAL_TIME)
from .world import move_and_collide
from .settings import C


class Player:
    def __init__(self, x, y):
        self.w, self.h = 12, 20
        self.rect = pygame.Rect(int(x), int(y - self.h), self.w, self.h)
        self.vx = self.vy = 0.0
        self.fx = self.fy = 0.0
        self.facing = 1
        self.hp = MAX_HP
        self.soul = 0
        self.geo = 0
        self.abilities = {'wings': False, 'dash': False}

        self.grounded = False
        self.coyote = 0
        self.buffer = 0
        self.air_jumps = 0
        self.drop_t = 0

        self.dash_t = 0
        self.dash_cd = 0
        self.dash_dir = 1
        self.air_dash_used = False

        self.atk_t = 0
        self.atk_cd = 0
        self._atk_timer = 0
        self.swing_id = 0

        self.iframe = 0
        self.flash = 0
        self.heal_t = 0
        self.deaths = 0
        self.ghosts = []          # след рывка
        self.last_safe = (self.rect.x, self.rect.y)
        self.spawn = ('awakening', self.rect.x, self.rect.y)

    # ---------- вспомогательное ----------
    @property
    def center(self):
        return self.rect.center

    @property
    def attack_box(self):
        if not (ATTACK_ACTIVE_FROM <= (self.atk_cd_time()) <= ATTACK_ACTIVE_TO):
            return None
        cx, cy = self.rect.center
        bw, bh = ATTACK_BOX
        return pygame.Rect(cx + (4 if self.facing > 0 else -4 - bw), cy - bh // 2 - 2, bw, bh)

    def atk_cd_time(self):
        """Сколько кадров осталось до конца замаха (обратный отсчёт атаки)."""
        return self._atk_timer

    def damage(self, game, amount, src_x):
        if self.iframe > 0 or self.dash_t > 0:
            return
        self.hp -= amount
        self.iframe = IFRAMES
        self.flash = 10
        self.heal_t = 0
        self.vx = 3.2 if self.rect.centerx >= src_x else -3.2
        self.vy = -3.0
        game.shake = max(game.shake, 5)
        game.sfx.play('hurt')
        game.particles.burst(self.rect.center, 10, C('danger'), speed=2.6, life=26)

    def hazard_hit(self, game):
        """Шипы: урон и возврат на последнюю безопасную точку."""
        if self.iframe > 0:
            return
        self.damage(game, 1, self.rect.centerx + self.facing)
        if self.hp > 0:
            self.rect.topleft = (int(self.last_safe[0]), int(self.last_safe[1]))
            self.vx = self.vy = 0

    # ---------- обновление ----------
    def update(self, game):
        inp = game.input
        room = game.room
        t = game.tick

        self.coyote = max(0, self.coyote - 1)
        self.buffer = max(0, self.buffer - 1)
        self.dash_cd = max(0, self.dash_cd - 1)
        self.atk_cd = max(0, self.atk_cd - 1)
        self.iframe = max(0, self.iframe - 1)
        self.flash = max(0, self.flash - 1)
        self.drop_t = max(0, self.drop_t - 1)
        if self.atk_t > 0:
            self.atk_t -= 1
        self._atk_timer = self.atk_t

        dir_x = (1 if inp.down('right') else 0) - (1 if inp.down('left') else 0)

        # --- лечение (фокус) ---
        if self.heal_t > 0:
            self.heal_t -= 1
            self.vx *= 0.6
            if dir_x or inp.pressed('attack') or inp.pressed('dash'):
                self.heal_t = 0
            elif self.heal_t == 0 and self.soul >= HEAL_COST:
                self.soul -= HEAL_COST
                self.hp = min(MAX_HP, self.hp + 1)
                game.sfx.play('heal')
                game.particles.burst(self.rect.center, 14, C('soul'), speed=1.6, life=40)

        # --- рывок ---
        if (inp.pressed('dash') and self.abilities['dash'] and self.dash_cd == 0
                and self.dash_t == 0 and self.heal_t == 0
                and (self.grounded or not self.air_dash_used)):
            self.dash_t = DASH_TIME
            self.dash_cd = DASH_COOLDOWN
            self.dash_dir = dir_x if dir_x else self.facing
            self.facing = self.dash_dir
            if not self.grounded:
                self.air_dash_used = True
            self.heal_t = 0
            game.sfx.play('dash')

        if self.dash_t > 0:
            self.dash_t -= 1
            self.vx = DASH_SPEED * self.dash_dir
            self.vy = 0
            self.ghosts.append((self.rect.x, self.rect.y, self.facing, 10))
            if self.dash_t == 0:
                self.vx *= 0.4
        else:
            # --- горизонталь ---
            if self.heal_t == 0:
                if dir_x:
                    self.vx += ACCEL * dir_x
                    self.facing = dir_x
                else:
                    if abs(self.vx) <= FRICTION:
                        self.vx = 0
                    else:
                        self.vx -= FRICTION * (1 if self.vx > 0 else -1)
                self.vx = max(-WALK_SPEED, min(WALK_SPEED, self.vx))

            # --- прыжки ---
            if inp.pressed('jump'):
                self.buffer = JUMP_BUFFER
                if inp.down('down') and self.grounded:
                    self.drop_t = 10  # прыжок вниз сквозь платформу
                    self.buffer = 0
                    self.grounded = False
            if self.buffer > 0:
                if self.grounded or self.coyote > 0:
                    self.vy = -JUMP_VEL
                    self.grounded = False
                    self.coyote = 0
                    self.buffer = 0
                    game.sfx.play('jump')
                    game.particles.burst((self.rect.centerx, self.rect.bottom), 5,
                                         C('rim'), speed=1.2, life=18)
                elif self.abilities['wings'] and self.air_jumps > 0:
                    self.vy = -DJUMP_VEL
                    self.air_jumps -= 1
                    self.buffer = 0
                    game.sfx.play('djump')
                    game.particles.burst((self.rect.centerx, self.rect.bottom), 8,
                                         C('mask'), speed=1.4, life=26)

            # --- гравитация (с укорачиванием прыжка) ---
            g = GRAVITY * (JUMP_EXTRA_GRAV if (self.vy < 0 and not inp.down('jump')) else 1.0)
            self.vy = min(MAX_FALL, self.vy + g)

        # --- атака ---
        if inp.pressed('attack') and self.atk_cd == 0 and self.heal_t == 0:
            self.atk_t = ATTACK_ACTIVE_TO + 1
            self.atk_cd = ATTACK_COOLDOWN
            self.swing_id += 1
            game.sfx.play('slash')

        # --- фокус начать ---
        if (inp.pressed('heal') and self.heal_t == 0 and self.grounded
                and self.soul >= HEAL_COST and self.hp < MAX_HP):
            self.heal_t = HEAL_TIME

        # --- перемещение и коллизии ---
        self.ghosts = [(x, y, f, life - 1) for (x, y, f, life) in self.ghosts if life > 1]
        was_grounded = self.grounded
        self.grounded, _, _ = move_and_collide(room, self)
        if self.grounded:
            self.coyote = COYOTE
            self.air_jumps = 1
            self.air_dash_used = False
            if not was_grounded and self.vy >= 0:
                game.particles.burst((self.rect.centerx, self.rect.bottom), 4,
                                     C('rim'), speed=1.0, life=14)
            self._remember_safe(room)

        # --- шипы ---
        if room.spike_tiles_in(self.rect):
            self.hazard_hit(game)

    def _remember_safe(self, room):
        feet_row = self.rect.bottom // TILE
        cx = self.rect.centerx // TILE
        solid_under = room.is_blocked(cx, feet_row) or (cx, feet_row) in room.plats
        near_spikes = any((cx + dx, feet_row - 1) in room.spikes or (cx + dx, feet_row) in room.spikes
                          for dx in (-1, 0, 1))
        if solid_under and not near_spikes:
            self.last_safe = (self.rect.x, self.rect.y)

    # ---------- отрисовка ----------
    def draw(self, surf, ox, oy, t):
        for (gx, gy, f, life) in self.ghosts:
            if life % 2 == 0:
                r = pygame.Rect(int(gx) - ox, int(gy) - oy, self.w, self.h)
                pygame.draw.polygon(surf, (52, 62, 92), self._cloak_pts(r))

        if self.iframe > 0 and self.flash <= 0 and (t // 3) % 2 == 0:
            return

        r = self.rect.move(-ox, -oy)
        cx, cy = r.center
        moving = abs(self.vx) > 0.4
        bob = ((t // 10) % 2) if (self.grounded and not moving) else 0
        lean = self.facing if (moving and self.grounded) else 0

        # фокус-лечение: пульсирующее кольцо
        if self.heal_t > 0:
            k = 1 - abs(self.heal_t - HEAL_TIME / 2) / (HEAL_TIME / 2)
            pygame.draw.circle(surf, C('soul'), (cx, cy), int(6 + 11 * k), 1)
            pygame.draw.circle(surf, (*C('soul'), 120), (cx, cy), int(3 + 7 * k))

        # ноги при беге
        if self.grounded and moving:
            ph = (t // 6) % 2
            pygame.draw.line(surf, C('cloak_dark'), (cx - 2, r.bottom - 3),
                             (cx - 3 - lean * 2, r.bottom + 1 + ph), 2)
            pygame.draw.line(surf, C('cloak_dark'), (cx + 2, r.bottom - 3),
                             (cx + 3 - lean * 2, r.bottom + 1 + (1 - ph)), 2)

        # плащ: верхний слой и тёмный подол
        pts = self._cloak_pts(r, bob, lean)
        pygame.draw.polygon(surf, C('player_cloak'), pts)
        hem_y = cy + 3
        pygame.draw.polygon(surf, C('cloak_dark'),
                            [(pts[3][0], hem_y), (pts[2][0], hem_y),
                             (pts[2][0] - 1, r.bottom - 1), (pts[3][0] + 1, r.bottom - 1)])
        pygame.draw.line(surf, C('player_cloak_edge'), pts[3], pts[2], 1)

        # рывок: полосы скорости за спиной
        if self.dash_t > 0:
            for i, dy in enumerate((-4, 0, 4)):
                ln = 10 - i * 2
                x1 = cx - self.dash_dir * 8
                pygame.draw.line(surf, (*C('rim'), 180), (x1, cy + dy),
                                 (x1 - self.dash_dir * ln, cy + dy), 1)

        # маска с рогами и светящимися глазами
        head = pygame.Rect(cx - 5, r.top - 4 + bob, 10, 9)
        pygame.draw.ellipse(surf, C('mask'), head)
        pygame.draw.line(surf, C('mask'), (cx - 4, head.top + 2), (cx - 8, head.top - 3), 2)
        pygame.draw.line(surf, C('mask'), (cx - 8, head.top - 3), (cx - 10, head.top - 2), 1)
        pygame.draw.line(surf, C('mask'), (cx + 4, head.top + 2), (cx + 8, head.top - 3), 2)
        pygame.draw.line(surf, C('mask'), (cx + 8, head.top - 3), (cx + 10, head.top - 2), 1)
        ex = 1 if self.facing > 0 else -1
        for dx in (-3, 2):
            eye = (cx + dx + ex, head.top + 3)
            pygame.draw.circle(surf, (*C('mask'), 60), eye, 3)
            pygame.draw.rect(surf, C('eyes'), (eye[0], eye[1], 2, 3))

        # удар: светящийся полумесяц
        box = self.attack_box
        if box:
            b = box.move(-ox, -oy).inflate(8, 10)
            if self.facing > 0:
                a0, a1 = -1.3, 1.3
            else:
                a0, a1 = 1.8, 4.4
            pygame.draw.arc(surf, C('mask'), b, a0, a1, 2)
            pygame.draw.arc(surf, (*C('rim'), 140), b.inflate(-4, -4), a0, a1, 1)

    def _cloak_pts(self, r, bob=0, lean=0):
        cx = r.centerx
        flare = 2 if self.grounded and abs(self.vx) > 0.5 else 0
        top = r.top + 5 + bob
        return [(cx - 5 + lean, top), (cx + 5 + lean, top),
                (cx + 7 + flare + lean * 2, r.bottom - 1),
                (cx - 7 - flare + lean * 2, r.bottom - 1)]
