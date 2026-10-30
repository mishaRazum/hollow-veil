"""Глобальные настройки и константы игры."""

# --- Окно и рендер ---
TILE = 16
INTERNAL_W, INTERNAL_H = 640, 360   # внутреннее «пиксельное» разрешение
WINDOW_W, WINDOW_H = 1280, 720
FPS = 60
STEP = 1.0 / FPS

# --- Физика игрока (в кадрах при 60 FPS) ---
GRAVITY = 0.42
MAX_FALL = 7.5
WALK_SPEED = 2.3
ACCEL = 0.4
FRICTION = 0.35
JUMP_VEL = 7.3        # высота одиночного прыжка ~63px (почти 4 тайла)
DJUMP_VEL = 6.6       # двойной прыжок добавляет ~52px
JUMP_EXTRA_GRAV = 1.2 # гравитация при отпущенной кнопке прыжка (короткий прыжок)
COYOTE = 6
JUMP_BUFFER = 7
DASH_SPEED = 7.5
DASH_TIME = 10
DASH_COOLDOWN = 30
ATTACK_COOLDOWN = 18
ATTACK_ACTIVE_FROM = 2
ATTACK_ACTIVE_TO = 9
ATTACK_BOX = (30, 26)  # ширина, высота хитбокса удара
IFRAMES = 60
MAX_HP = 5
MAX_SOUL = 99
SOUL_PER_HIT = 11
HEAL_COST = 33
HEAL_TIME = 45

# --- Экономика врагов ---
CRAWLER_HP, CRAWLER_GEO = 2, 5
FLYER_HP, FLYER_GEO = 2, 7
BOSS_HP, BOSS_GEO = 45, 100

# --- Палитра (мрачные недра) ---
PALETTE = {
    'bg_deep': (7, 9, 18),
    'tile': (24, 30, 48),
    'tile_dark': (14, 18, 32),
    'rim': (122, 136, 178),
    'rim_dim': (66, 76, 110),
    'spike': (168, 180, 214),
    'platform': (52, 62, 96),
    'player_cloak': (24, 29, 44),
    'player_cloak_edge': (52, 62, 92),
    'cloak_dark': (15, 19, 30),
    'mask': (232, 236, 242),
    'eyes': (13, 16, 26),
    'moss': (96, 124, 112),
    'moss_light': (132, 160, 142),
    'enemy': (40, 32, 54),
    'enemy_light': (96, 82, 120),
    'enemy_eye': (222, 228, 240),
    'boss': (74, 42, 38),
    'boss_light': (156, 84, 52),
    'boss_eye': (255, 150, 60),
    'geo': (206, 214, 236),
    'soul': (240, 246, 255),
    'text': (232, 236, 242),
    'text_dim': (128, 138, 168),
    'ui_back': (16, 20, 34),
    'danger': (224, 108, 84),
    'accent': (216, 196, 130),
}

def C(name):
    return PALETTE[name]
