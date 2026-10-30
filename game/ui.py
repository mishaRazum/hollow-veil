"""Интерфейс: HUD, меню, пауза, смерть, победа, карта."""
import pygame

from .settings import INTERNAL_W, INTERNAL_H, MAX_HP, MAX_SOUL, C

CONTROLS_LINES = [
    'A/D или стрелки — движение',
    'SPACE / Z — прыжок (двойной — после находки)',
    'J / X — удар',
    'K / C / Shift — рывок (после находки)',
    'F — фокус: лечение за душу (33)',
    'E — взаимодействие, TAB — карта, ESC — пауза',
]


def make_fonts():
    names = 'arial,dejavusans,verdana'
    return {
        'sm': pygame.font.SysFont(names, 11),
        'md': pygame.font.SysFont(names, 15),
        'lg': pygame.font.SysFont(names, 40, bold=True),
        'xl': pygame.font.SysFont(names, 54, bold=True),
    }


def text(surf, font, s, x, y, color, anchor='topleft', alpha=255, shadow=True):
    img = font.render(s, True, color)
    if alpha < 255:
        img.set_alpha(alpha)
    r = img.get_rect(**{anchor: (x, y)})
    if shadow:
        sh = font.render(s, True, (0, 0, 0))
        if alpha < 255:
            sh.set_alpha(alpha)
        surf.blit(sh, r.move(1, 1))
    surf.blit(img, r)
    return r


def diamond(surf, cx, cy, rad, color, fill=True, width=1):
    pts = [(cx, cy - rad), (cx + rad, cy), (cx, cy + rad), (cx - rad, cy)]
    if fill:
        pygame.draw.polygon(surf, color, pts)
    pygame.draw.polygon(surf, color, pts, width)


def draw_hud(surf, game):
    p = game.player
    # сфера души: двойное кольцо, заливка снизу вверх, блик
    orb_r = 10
    orb = pygame.Rect(8, 8, orb_r * 2, orb_r * 2)
    c = orb.center
    pygame.draw.circle(surf, C('ui_back'), c, orb_r)
    frac = max(0.0, min(1.0, p.soul / MAX_SOUL))
    if frac > 0:
        fill_h = int(orb_r * 2 * frac)
        temp = pygame.Surface((orb_r * 2, orb_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(temp, C('soul'), (orb_r, orb_r), orb_r - 1)
        temp.set_clip(pygame.Rect(0, orb_r * 2 - fill_h, orb_r * 2, fill_h))
        surf.blit(temp, orb.topleft)
    pygame.draw.circle(surf, C('rim'), c, orb_r, 1)
    pygame.draw.circle(surf, C('rim_dim'), c, orb_r + 2, 1)
    pygame.draw.arc(surf, (255, 255, 255), orb.inflate(-5, -5), 2.3, 3.3, 1)

    # маски здоровья с блеском
    for i in range(MAX_HP):
        cx = 36 + i * 15
        cy = 16
        if i < p.hp:
            diamond(surf, cx, cy, 6, C('mask'))
            pygame.draw.line(surf, C('ui_back'), (cx - 2, cy - 1), (cx - 1, cy - 2), 1)
        else:
            diamond(surf, cx, cy, 6, C('ui_back'))
            diamond(surf, cx, cy, 6, C('rim_dim'), fill=False)

    # гео
    diamond(surf, 40, 34, 4, C('geo'))
    pygame.draw.line(surf, C('ui_back'), (39, 32), (40, 31), 1)
    text(surf, game.fonts['md'], str(p.geo), 50, 27, C('geo'), shadow=True)

    # подсказки способностей
    if p.abilities['dash']:
        text(surf, game.fonts['sm'], 'РЫВОК', 8, 48, C('text_dim'), shadow=False)


def draw_boss_bar(surf, game):
    boss = game.boss
    if boss is None or not boss.alive or boss.state == 'sleep':
        return
    w, x0, y0 = 300, (INTERNAL_W - 300) // 2, INTERNAL_H - 26
    text(surf, game.fonts['sm'], 'ДОЗОРНЫЙ ГЛУБИН', INTERNAL_W // 2, y0 - 12,
         C('boss_eye'), anchor='midtop')
    pygame.draw.rect(surf, C('ui_back'), (x0, y0, w, 8))
    frac = max(0.0, boss.hp / boss.max_hp)
    pygame.draw.rect(surf, C('boss_eye'), (x0, y0, int(w * frac), 8))
    pygame.draw.rect(surf, C('rim'), (x0, y0, w, 8), 1)


def draw_messages(surf, game):
    # крупные сообщения (пикапы, босс) — в верхней трети, обычные — снизу
    big = [m for m in game.messages if m.get('big') or m.get('boss')]
    small = [m for m in game.messages if not (m.get('big') or m.get('boss'))]
    y = 92
    for m in big:
        a = _msg_alpha(m)
        text(surf, game.fonts['lg'], m['text'], INTERNAL_W // 2, y,
             C('accent') if m.get('boss') else C('text'), anchor='midtop', alpha=a)
        y += 42
    y = INTERNAL_H - 58
    for m in small:
        a = _msg_alpha(m)
        font = game.fonts['lg'] if m.get('big') else game.fonts['md']
        text(surf, font, m['text'], INTERNAL_W // 2, y, C('text'), anchor='midtop', alpha=a)
        y -= 26


def _msg_alpha(m):
    if m['t'] < 12:
        return int(255 * m['t'] / 12)
    if m['t'] > m['dur'] - 20:
        return max(0, int(255 * (m['dur'] - m['t']) / 20))
    return 255


def draw_world_overlays(surf, game):
    """Подсказки взаимодействия (E) над скамьями/табличками/пикапами."""
    if game.interact_target is None:
        return
    kind, x, y, label = game.interact_target
    sx, sy = int(x - game.cam_x), int(y - game.cam_y)
    if 0 < sx < INTERNAL_W and 0 < sy < INTERNAL_H:
        bob = 2 if (game.tick // 20) % 2 == 0 else 0
        pygame.draw.rect(surf, C('ui_back'), (sx - 6, sy - 14 + bob, 12, 12), border_radius=3)
        pygame.draw.rect(surf, C('rim'), (sx - 6, sy - 14 + bob, 12, 12), 1, border_radius=3)
        text(surf, game.fonts['sm'], 'E', sx, sy - 13 + bob, C('text'), anchor='midtop', shadow=False)
        text(surf, game.fonts['sm'], label, sx, sy + 8, C('text_dim'), anchor='midtop')


def draw_map(surf, game):
    overlay = pygame.Surface((INTERNAL_W, INTERNAL_H), pygame.SRCALPHA)
    overlay.fill((6, 8, 16, 215))
    surf.blit(overlay, (0, 0))
    text(surf, game.fonts['md'], 'КАРТА', INTERNAL_W // 2, 24, C('text'), anchor='midtop')

    cw, ch = 36, 22
    ox, oy = INTERNAL_W // 2 - 80, 70
    for name, (gx, gy) in game.map_pos.items():
        if name not in game.visited:
            continue
        x, y = ox + gx * (cw + 6), oy + gy * (ch + 6)
        cur = name == game.room_name
        col = C('rim') if cur else C('rim_dim')
        pygame.draw.rect(surf, C('ui_back'), (x, y, cw, ch), border_radius=2)
        pygame.draw.rect(surf, col, (x, y, cw, ch), 1, border_radius=2)
        if cur:
            pygame.draw.circle(surf, C('mask'), (x + cw // 2, y + ch // 2), 3)
    text(surf, game.fonts['sm'], game.room.display_name, INTERNAL_W // 2,
         INTERNAL_H - 40, C('text_dim'), anchor='midtop')


def draw_pause(surf, game):
    overlay = pygame.Surface((INTERNAL_W, INTERNAL_H), pygame.SRCALPHA)
    overlay.fill((6, 8, 16, 200))
    surf.blit(overlay, (0, 0))
    text(surf, game.fonts['lg'], 'ПАУЗА', INTERNAL_W // 2, 70, C('text'), anchor='midtop')
    y = 150
    for line in CONTROLS_LINES:
        text(surf, game.fonts['md'], line, INTERNAL_W // 2, y, C('text_dim'), anchor='midtop')
        y += 22
    text(surf, game.fonts['sm'], 'ESC — продолжить', INTERNAL_W // 2, y + 16,
         C('text'), anchor='midtop')


def draw_death(surf, game):
    k = min(1.0, game.death_t / 40.0)
    if game.death_t > 55:
        k = max(0.0, 1.0 - (game.death_t - 55) / 40.0)
    fade = pygame.Surface((INTERNAL_W, INTERNAL_H))
    fade.fill((4, 5, 10))
    fade.set_alpha(int(255 * k))
    surf.blit(fade, (0, 0))


def draw_victory(surf, game):
    surf.fill((6, 8, 16))
    for i in range(40):
        x = (i * 97 + game.tick // 3) % INTERNAL_W
        y = (i * 53) % INTERNAL_H
        surf.fill((30, 38, 60), (x, y, 2, 2))
    text(surf, game.fonts['xl'], 'ХРАМ ПАЛ', INTERNAL_W // 2, 90, C('accent'), anchor='midtop')
    text(surf, game.fonts['md'], 'Дозорный повержен. Демо-версия завершена.',
         INTERNAL_W // 2, 160, C('text'), anchor='midtop')
    mins, secs = divmod(int(game.playtime), 60)
    stats = f'Гео: {game.player.geo}   Смертей: {game.deaths}   Время: {mins}:{secs:02d}'
    text(surf, game.fonts['md'], stats, INTERNAL_W // 2, 200, C('text_dim'), anchor='midtop')
    text(surf, game.fonts['sm'], 'ENTER — в меню (прогресс сохранён)',
         INTERNAL_W // 2, 250, C('text'), anchor='midtop')


def draw_title(surf, game):
    surf.fill((7, 9, 18))
    # медленный пульс и мотыльки
    pr = 90 + (game.tick % 120)
    a = max(0, 40 - pr // 4)
    pygame.draw.circle(surf, (a, a + 6, a + 16), (INTERNAL_W // 2, 120), pr, 2)
    for i in range(26):
        x = (i * 131 + game.tick // 2) % INTERNAL_W
        y = (i * 79 + game.tick // 5) % INTERNAL_H
        surf.fill((36, 44, 70), (x, y, 2, 2))

    bob = 2 if (game.tick // 30) % 2 == 0 else 0
    text(surf, game.fonts['xl'], 'HOLLOW VEIL', INTERNAL_W // 2, 70 + bob,
         C('text'), anchor='midtop')
    text(surf, game.fonts['md'], 'полая вуаль · метроидвания-демо',
         INTERNAL_W // 2, 130, C('text_dim'), anchor='midtop')

    y = 210
    if game.has_save():
        text(surf, game.fonts['md'], 'ENTER — продолжить', INTERNAL_W // 2, y,
             C('text'), anchor='midtop')
        text(surf, game.fonts['sm'], 'N — новая игра', INTERNAL_W // 2, y + 26,
             C('text_dim'), anchor='midtop')
    else:
        text(surf, game.fonts['md'], 'ENTER — начать', INTERNAL_W // 2, y,
             C('text'), anchor='midtop')
    text(surf, game.fonts['sm'], 'ESC — выход', INTERNAL_W // 2, INTERNAL_H - 24,
         C('text_dim'), anchor='midtop')
