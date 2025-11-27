import os
import sys
import math
import random
import pygame

# -----------------------------
# Config
# -----------------------------
WIDTH, HEIGHT = 1280, 720
FPS = 60

GRID_ROWS, GRID_COLS = 8, 8
TILE_SIZE = 72
PADDING = 6
BOARD_TOP_LEFT = (WIDTH // 2 - (GRID_COLS * TILE_SIZE) // 2,
                  HEIGHT // 2 - (GRID_ROWS * TILE_SIZE) // 2 + 20)

# Candy palette
CANDY_TYPES = [
    ("cherry",    (235, 84, 97)),
    ("lemon",     (251, 211, 58)),
    ("mint",      (84, 214, 170)),
    ("blueberry", (92, 129, 253)),
    ("grape",     (169, 119, 243)),
    ("orange",    (255, 155, 66)),
]

# Special types
NORMAL = 0
STRIPED_H = 1
STRIPED_V = 2

BG_TOP = (248, 250, 255)
BG_BOTTOM = (226, 233, 248)
GRID_LINE = (220, 226, 240)
HUD_TEXT = (60, 70, 90)
WHITE = (255, 255, 255)
HILIGHT_COLOR = (255, 255, 255)

# Audio files (optional)
AUDIO_PATHS = {
    "bg": [
        os.path.join("assets", "audio", "bg_music.ogg"),
        os.path.join("assets", "audio", "bg_music.mp3"),
        os.path.join("assets", "audio", "bg_music.wav"),
    ],
    "swap": [os.path.join("assets", "audio", "swap.wav")],
    "match": [os.path.join("assets", "audio", "match.wav")],
    "invalid": [os.path.join("assets", "audio", "invalid.wav")],
    "level_complete": [os.path.join("assets", "audio", "level_complete.wav")],
}

LEVELS = [
    {"target": 1200, "moves": 20},
    {"target": 2500, "moves": 22},
]

SCORE_PER_CANDY = 50
CASCADE_BONUS = 100

CRUSH_ANIM_TIME = 0.22

random.seed()


# -----------------------------
# Drawing helpers
# -----------------------------
def draw_vertical_gradient(surf, top_color, bottom_color):
    h = surf.get_height()
    w = surf.get_width()
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        pygame.draw.line(surf, (r, g, b), (0, y), (w, y))


def rounded_rect(surface, rect, color, radius=12):
    x, y, w, h = rect
    pygame.draw.rect(surface, color, (x + radius, y, w - 2 * radius, h))
    pygame.draw.rect(surface, color, (x, y + radius, w, h - 2 * radius))
    pygame.draw.circle(surface, color, (x + radius, y + radius), radius)
    pygame.draw.circle(surface, color, (x + w - radius, y + radius), radius)
    pygame.draw.circle(surface, color, (x + radius, y + h - radius), radius)
    pygame.draw.circle(surface, color, (x + w - radius, y + h - radius), radius)


def lighten(color, amt=30):
    r, g, b = color
    return (min(255, r + amt), min(255, g + amt), min(255, b + amt))


def darken(color, amt=30):
    r, g, b = color
    return (max(0, r - amt), max(0, g - amt), max(0, b - amt))


# -----------------------------
# Audio
# -----------------------------
class Audio:
    def __init__(self):
        self.sounds = {}
        try:
            pygame.mixer.init()
        except Exception:
            return

        for key, candidates in AUDIO_PATHS.items():
            for p in candidates:
                if os.path.exists(p):
                    try:
                        if key == "bg":
                            pygame.mixer.music.load(p)
                        else:
                            self.sounds[key] = pygame.mixer.Sound(p)
                        break
                    except Exception:
                        continue

    def play_music(self):
        try:
            pygame.mixer.music.set_volume(0.5)
            pygame.mixer.music.play(-1)
        except Exception:
            pass

    def play(self, key):
        try:
            s = self.sounds.get(key)
            if s:
                s.play()
        except Exception:
            pass


# -----------------------------
# Candy
# -----------------------------
class Candy:
    __slots__ = ("kind", "base_color", "phase", "special")

    def __init__(self, kind, base_color, special=NORMAL):
        self.kind = kind
        self.base_color = base_color
        self.phase = random.uniform(0, math.pi * 2)
        self.special = special

    def draw(self, surf, rect, t):
        x, y, w, h = rect
        bob = math.sin(t * 2.0 + self.phase) * 2.0
        y += int(bob)

        rounded_rect(surf, (x, y, w, h), self.base_color, radius=16)
        inset = 6
        rounded_rect(surf, (x + inset, y + inset, w - 2 * inset, h - 2 * inset),
                     lighten(self.base_color, 18), radius=12)

        gloss_surface = pygame.Surface((int(w * 0.55), int(h * 0.30)), pygame.SRCALPHA)
        pygame.draw.ellipse(gloss_surface, (255, 255, 255, 90), gloss_surface.get_rect())
        surf.blit(gloss_surface, (x + int(w * 0.20), y + int(h * 0.18)))

        rounded_rect(surf, (x, y + h - 10, w, 8), darken(self.base_color, 35), radius=6)

        if self.special == STRIPED_H:
            for i in range(3):
                yy = y + int((i + 1) * h / 4)
                pygame.draw.line(surf, WHITE, (x + 8, yy), (x + w - 8, yy), 3)
        elif self.special == STRIPED_V:
            for i in range(3):
                xx = x + int((i + 1) * w / 4)
                pygame.draw.line(surf, WHITE, (xx, y + 8), (xx, y + h - 8), 3)


# -----------------------------
# Board
# -----------------------------
class Board:
    def __init__(self, rows, cols):
        self.rows, self.cols = rows, cols
        self.grid = [[self._rand_candy() for _ in range(cols)] for _ in range(rows)]
        self.ensure_no_start_matches()
        self.selected = None

    def _rand_candy(self):
        name, color = random.choice(CANDY_TYPES)
        return Candy(name, color, NORMAL)

    def cell_rect(self, r, c):
        x = BOARD_TOP_LEFT[0] + c * TILE_SIZE
        y = BOARD_TOP_LEFT[1] + r * TILE_SIZE
        return (x + PADDING//2, y + PADDING//2, TILE_SIZE - PADDING, TILE_SIZE - PADDING)

    def in_bounds(self, r, c):
        return 0 <= r < self.rows and 0 <= c < self.cols

    def ensure_no_start_matches(self):
        changed = True
        while changed:
            changed = False
            matches = self.find_matches()
            if matches:
                changed = True
                for (r, c) in matches:
                    self.grid[r][c] = self._rand_candy()

    def select(self, r, c):
        if self.selected == (r, c):
            self.selected = None
        elif self.selected is None:
            self.selected = (r, c)
        else:
            r0, c0 = self.selected
            if abs(r - r0) + abs(c - c0) == 1:
                self.selected = None
                return (r0, c0), (r, c)
            else:
                self.selected = (r, c)
        return None

    def swap_cells(self, a, b):
        (r1, c1), (r2, c2) = a, b
        self.grid[r1][c1], self.grid[r2][c2] = self.grid[r2][c2], self.grid[r1][c1]

    def find_matches(self):
        matched = set()
        # horizontal
        for r in range(self.rows):
            run_start = 0
            for c in range(1, self.cols + 1):
                same = (c < self.cols and self.grid[r][c].kind == self.grid[r][c-1].kind)
                if not same:
                    run_len = c - run_start
                    if run_len >= 3:
                        for cc in range(run_start, c):
                            matched.add((r, cc))
                    run_start = c
        # vertical
        for c in range(self.cols):
            run_start = 0
            for r in range(1, self.rows + 1):
                same = (r < self.rows and self.grid[r][c].kind == self.grid[r-1][c].kind)
                if not same:
                    run_len = r - run_start
                    if run_len >= 3:
                        for rr in range(run_start, r):
                            matched.add((rr, c))
                    run_start = r
        return matched

    def crush_matches(self, matched):
        for (r, c) in matched:
            self.grid[r][c] = None

    def apply_gravity(self):
        for c in range(self.cols):
            write_row = self.rows - 1
            for r in range(self.rows - 1, -1, -1):
                if self.grid[r][c] is not None:
                    self.grid[write_row][c] = self.grid[r][c]
                    if write_row != r:
                        self.grid[r][c] = None
                    write_row -= 1
            for r in range(write_row, -1, -1):
                self.grid[r][c] = self._rand_candy()

    def pos_to_cell(self, px, py):
        bx, by = BOARD_TOP_LEFT
        gx = (px - bx) // TILE_SIZE
        gy = (py - by) // TILE_SIZE
        if 0 <= gx < self.cols and 0 <= gy < self.rows:
            return int(gy), int(gx)
        return None

    def draw(self, surf, t, sel=None):
        for r in range(self.rows + 1):
            y = BOARD_TOP_LEFT[1] + r * TILE_SIZE
            pygame.draw.line(surf, GRID_LINE,
                             (BOARD_TOP_LEFT[0], y),
                             (BOARD_TOP_LEFT[0] + self.cols * TILE_SIZE, y), 1)
        for c in range(self.cols + 1):
            x = BOARD_TOP_LEFT[0] + c * TILE_SIZE
            pygame.draw.line(surf, GRID_LINE,
                             (x, BOARD_TOP_LEFT[1]),
                             (x, BOARD_TOP_LEFT[1] + self.rows * TILE_SIZE), 1)

        for r in range(self.rows):
            for c in range(self.cols):
                rect = self.cell_rect(r, c)
                candy = self.grid[r][c]
                if candy:
                    candy.draw(surf, rect, t)

        if sel:
            r, c = sel
            x, y, w, h = self.cell_rect(r, c)
            pygame.draw.rect(surf, HILIGHT_COLOR, (x-2, y-2, w+4, h+4), width=3, border_radius=14)


# -----------------------------
# Game
# -----------------------------
STATE_MENU = 0
STATE_PLAY = 1
STATE_LEVEL_COMPLETE = 2
STATE_GAME_OVER = 3

class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Sweet Match Mania — Q3")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 36)
        self.big = pygame.font.SysFont(None, 64)

        self.audio = Audio()
        self.audio.play_music()

        self.bg = pygame.Surface((WIDTH, HEIGHT))
        draw_vertical_gradient(self.bg, BG_TOP, BG_BOTTOM)

        self.level_index = 0
        self.reset_level()

        self.state = STATE_MENU
        self.t = 0.0
        self.crushing = False
        self.crush_timer = 0.0

    def reset_level(self):
        self.board = Board(GRID_ROWS, GRID_COLS)
        cfg = LEVELS[self.level_index]
        self.moves = cfg["moves"]
        self.target = cfg["target"]
        self.score = 0

    def try_swap(self, a, b):
        self.board.swap_cells(a, b)
        matches = self.board.find_matches()
        if matches:
            self.audio.play("swap")
            self.start_crush_cycle(matches)
            self.moves -= 1
            return True
        else:
            self.audio.play("invalid")
            self.board.swap_cells(a, b)  # undo swap
            return False

    def start_crush_cycle(self, matches):
        self.crushing = True
        self.crush_timer = 0.0
        self.matches = matches

    def finish_crush_cycle(self):
        # clear matched candies
        self.board.crush_matches(self.matches)
        # scoring
        self.score += len(self.matches) * SCORE_PER_CANDY
        # gravity/refill
        self.board.apply_gravity()
        self.audio.play("match")
        # check for cascades
        new_matches = self.board.find_matches()
        if new_matches:
            self.start_crush_cycle(new_matches)
        else:
            self.crushing = False
            # check win/lose
            if self.score >= self.target:
                self.state = STATE_LEVEL_COMPLETE
                self.audio.play("level_complete")
            elif self.moves <= 0:
                self.state = STATE_GAME_OVER

    def handle_click(self, mx, my):
        if self.state != STATE_PLAY:
            return
        cell = self.board.pos_to_cell(mx, my)
        if not cell:
            self.board.selected = None
            return
        res = self.board.select(*cell)
        if res and not self.crushing:
            a, b = res
            self.try_swap(a, b)

    def draw_hud(self):
        top = 12
        def label(txt, x):
            surf = self.font.render(txt, True, HUD_TEXT)
            rect = surf.get_rect(midtop=(x, top))
            self.screen.blit(surf, rect)

        label(f"Level {self.level_index + 1}", WIDTH * 0.15)
        label(f"Score: {self.score}", WIDTH * 0.40)
        label(f"Target: {self.target}", WIDTH * 0.60)
        label(f"Moves: {self.moves}", WIDTH * 0.83)

    def draw_center_message(self, title, subtitle):
        title_s = self.big.render(title, True, (55, 65, 90))
        sub_s = self.font.render(subtitle, True, (90, 100, 120))
        self.screen.blit(title_s, title_s.get_rect(center=(WIDTH//2, HEIGHT//2 - 20)))
        self.screen.blit(sub_s, sub_s.get_rect(center=(WIDTH//2, HEIGHT//2 + 30)))

    def draw(self, dt):
        self.screen.blit(self.bg, (0, 0))

        if self.state in (STATE_PLAY, STATE_LEVEL_COMPLETE, STATE_GAME_OVER):
            self.draw_hud()

        if self.state == STATE_MENU:
            self.draw_center_message("Sweet Match Mania", "Press ENTER to start  |  ESC to quit")
        elif self.state == STATE_PLAY:
            self.board.draw(self.screen, self.t, self.board.selected)
            if self.crushing:
                alpha = int(120 + 120 * math.sin(self.t * 20))
                overlay = pygame.Surface((TILE_SIZE - PADDING, TILE_SIZE - PADDING), pygame.SRCALPHA)
                overlay.fill((255, 255, 255, alpha))
                for (r, c) in self.matches:
                    x, y, w, h = self.board.cell_rect(r, c)
                    self.screen.blit(overlay, (x, y))
        elif self.state == STATE_LEVEL_COMPLETE:
            self.board.draw(self.screen, self.t)
            self.draw_center_message("Level Complete!", "Press ENTER for next level  |  ESC to menu")
        elif self.state == STATE_GAME_OVER:
            self.board.draw(self.screen, self.t)
            self.draw_center_message("Game Over", "Press ENTER to retry  |  ESC to menu")

        pygame.display.flip()

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            self.t += dt

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if self.state == STATE_MENU:
                        if event.key == pygame.K_RETURN:
                            self.state = STATE_PLAY
                        elif event.key == pygame.K_ESCAPE:
                            running = False
                    elif self.state == STATE_PLAY:
                        if event.key == pygame.K_ESCAPE:
                            self.state = STATE_MENU
                    elif self.state == STATE_LEVEL_COMPLETE:
                        if event.key == pygame.K_RETURN:
                            self.level_index = (self.level_index + 1) % len(LEVELS)
                            self.reset_level()
                            self.state = STATE_PLAY
                        elif event.key == pygame.K_ESCAPE:
                            self.state = STATE_MENU
                    elif self.state == STATE_GAME_OVER:
                        if event.key == pygame.K_RETURN:
                            self.reset_level()
                            self.state = STATE_PLAY
                        elif event.key == pygame.K_ESCAPE:
                            self.state = STATE_MENU

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    self.handle_click(mx, my)

            # timed crush cycle
            if self.state == STATE_PLAY and self.crushing:
                self.crush_timer += dt
                if self.crush_timer >= CRUSH_ANIM_TIME:
                    self.finish_crush_cycle()

            self.draw(dt)

        pygame.quit()
        sys.exit(0)


if __name__ == "__main__":
    Game().run()
