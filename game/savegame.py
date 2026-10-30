"""Сохранения в JSON рядом с игрой."""
import json
from pathlib import Path

SAVE_PATH = Path(__file__).resolve().parent.parent / 'save.json'


def save(data):
    try:
        SAVE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
        return True
    except OSError:
        return False


def load():
    try:
        return json.loads(SAVE_PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def clear():
    try:
        SAVE_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def collect(game):
    p = game.player
    return {
        'room': game.room_name,
        'x': p.rect.x,
        'y': p.rect.y,
        'hp': p.hp,
        'soul': p.soul,
        'geo': p.geo,
        'abilities': p.abilities,
        'collected': sorted(game.collected),
        'visited': sorted(game.visited),
        'boss_dead': game.boss_dead,
        'spawn': list(p.spawn),
        'deaths': game.deaths,
        'playtime': game.playtime,
    }


def apply(game, data):
    p = game.player
    p.hp = int(data.get('hp', 5))
    p.soul = int(data.get('soul', 0))
    p.geo = int(data.get('geo', 0))
    p.abilities.update(data.get('abilities', {}))
    p.deaths = int(data.get('deaths', 0))
    game.collected = set(data.get('collected', []))
    game.visited = set(data.get('visited', [])) or {data.get('room', 'awakening')}
    game.boss_dead = bool(data.get('boss_dead', False))
    game.deaths = int(data.get('deaths', 0))
    game.playtime = float(data.get('playtime', 0.0))
    sp = data.get('spawn')
    if sp and len(sp) == 3:
        p.spawn = (sp[0], float(sp[1]), float(sp[2]))
    else:
        p.spawn = (data.get('room', 'awakening'), float(data['x']), float(data['y']))
