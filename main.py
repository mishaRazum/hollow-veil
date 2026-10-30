"""Hollow Veil — точка входа.

Запуск:            python main.py
Smoke-тест:        python main.py --smoke   (без окна, проверяет всю логику)
"""
import sys


def main():
    if '--smoke' in sys.argv:
        run_smoke()
        return
    if '--shots' in sys.argv:
        run_shots()
        return
    from game.game import Game
    Game().run()


def run_shots():
    """Headless-скриншоты игровых сцен для проверки графики."""
    import os
    import pygame
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
    from game.game import Game

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshots')
    os.makedirs(out, exist_ok=True)
    g = Game()

    def snap(name):
        g.draw()
        pygame.image.save(g.window, os.path.join(out, name + '.png'))
        print('shot:', name)

    g.tick = 42
    snap('00_title')

    g.new_game()
    for _ in range(40):
        g.step()
    snap('01_awakening')

    g.load_room('corridor')
    for _ in range(25):
        g.step()
    g.player.rect.topleft = (300, 172)
    g.input.held.add('right')
    for _ in range(14):
        g.step()
    g.input.just.add('attack')
    for _ in range(3):
        g.step()
    g.input.held.clear()
    snap('02_corridor')

    g.load_room('atrium')
    for _ in range(25):
        g.step()
    g.player.rect.topleft = (120, 316)
    g.input.just.add('jump')
    for _ in range(14):
        g.step()
    snap('03_atrium')

    g.load_room('shaft')
    for _ in range(25):
        g.step()
    g.player.rect.topleft = (120, 364)
    for _ in range(25):
        g.step()
    snap('04_shaft')

    g.load_room('hall')
    for _ in range(25):
        g.step()
    g.player.abilities['dash'] = True
    g.player.rect.topleft = (700, 172)
    g.input.held.add('right')
    g.input.just.add('dash')
    for _ in range(5):
        g.step()
    g.input.held.clear()
    snap('05_hall_dash')

    g.load_room('caverns')
    for _ in range(25):
        g.step()
    g.player.rect.topleft = (700, 204)
    for _ in range(30):
        g.step()
    snap('06_caverns')

    g.load_room('sanctum')
    g.player.rect.topleft = (300, 236)
    for _ in range(80):
        g.step()
        if g.state != 'play':
            break
    snap('07_boss')

    g.state = 'victory'
    snap('08_victory')
    print('SHOTS DONE')


def run_smoke():
    import os
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
    from game.game import Game
    from game import savegame

    g = Game()
    g.new_game()
    assert g.room_name == 'awakening', 'стартовая комната неверна'
    p = g.player

    # --- меню: отрисовка всех состояний ---
    g.draw()
    g.state = 'play'
    g.draw()
    g.state = 'pause'
    g.draw()
    g.show_map = True
    g.state = 'play'
    g.draw()
    g.show_map = False
    g.state = 'play'

    # --- движение и прыжки ---
    x0, y0 = p.rect.x, p.rect.y
    for i in range(180):
        g.input.held.add('right')
        if i % 40 == 0:
            g.input.just.add('jump')
        g.step()
        g.draw()
    g.input.held.clear()
    assert p.rect.x > x0 + 40, f'игрок не сдвинулся вправо: {p.rect.x - x0}'
    assert p.rect.y < y0 + 100, 'игрок провалился сквозь пол'

    # --- атака убивает врага ---
    from game.enemies import Crawler
    dummy = Crawler(p.rect.x + 22, p.rect.y + p.rect.h)
    g.room_enemies().append(dummy)
    for i in range(60):
        if i % 20 == 0:
            g.input.just.add('attack')
        g.step()
    assert not dummy.alive, 'манекен не умер от удара'

    # --- урон и неуязвимость ---
    hp0 = p.hp
    p.iframe = 0
    p.damage(g, 1, p.rect.centerx + 10)
    assert p.hp == hp0 - 1 and p.iframe > 0, 'урон/ифреймы не работают'

    # --- шипы: урон и возврат на безопасную точку ---
    g.load_room('corridor')
    p.rect.topleft = (22 * 16, 13 * 16 - 10)  # внутрь шипов первой ямы
    p.iframe = 0
    hp0 = p.hp
    p.hazard_hit(g)
    assert p.hp == hp0 - 1, 'шипы не наносят урон'
    assert p.iframe > 0, 'нет неуязвимости после шипов'

    # --- способности: рывок и двойной прыжок ---
    p.abilities['wings'] = True
    p.abilities['dash'] = True
    p.grounded = False
    p.air_dash_used = False
    p.dash_cd = 0
    p.rect.topleft = (200, 100)
    p.vy = 2.0
    g.input.just.add('dash')
    g.step()
    assert p.dash_t > 0 or abs(p.vx) > 4, 'рывок не сработал'
    p.dash_t = 0
    p.air_jumps = 1
    p.vy = 1.0
    vy0 = p.vy
    g.input.just.add('jump')
    g.step()
    assert p.vy < vy0, 'двойной прыжок не сработал'

    # --- все точки спавна у выходов безопасны (координаты — в целевой комнате) ---
    from game.settings import MAX_HP
    for rn, room in g.rooms.items():
        g.load_room(rn)
        g.step()
        for d, ex in room.exits.items():
            g.load_room(ex['to'])
            g.player.hp = MAX_HP
            g.player.iframe = 0
            g.player.rect.topleft = (ex['sx'], ex['sy'] - g.player.rect.h)
            for _ in range(70):
                g.step()
            assert g.player.hp > 0, f'спавн у выхода {rn}:{d} убивает игрока'

    # --- босс: активация и смерть ---
    g.load_room('sanctum')
    boss = g.boss
    assert boss is not None, 'босс не заспавнился'
    g.player.hp = 999  # чтобы тест не прервался смертью игрока
    g.player.rect.topleft = (boss.rect.left - 200, boss.rect.top)
    for _ in range(600):
        g.step()
        if g.state != 'play':
            break
    assert boss.state != 'sleep', 'босс не активировался'
    boss.hurt(g, 999, 0, p.swing_id + 1)
    assert g.boss_dead, 'флаг победы над боссом не установлен'
    assert g.seal_pos is not None, 'печать не появилась'
    g.draw()

    # --- сейв/лоад ---
    savegame.save(savegame.collect(g))
    data = savegame.load()
    assert data and data['room'] == 'sanctum' and data['boss_dead'], 'сейв неполный'
    g2 = Game()
    g2.load_save()
    assert g2.boss_dead and g2.player.abilities['wings'], 'лоад не восстановил прогресс'
    savegame.clear()

    print('SMOKE OK')


if __name__ == '__main__':
    main()
