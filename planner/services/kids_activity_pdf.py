"""
PDF generator for Kids Activity sheets.
Renders printable activity pages using ReportLab.
"""
import os
import random

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

# ── Colours ──────────────────────────────────────────────────────────
NAVY = colors.HexColor('#1B2A4A')
GOLD = colors.HexColor('#C9A84C')
LIGHT_BG = colors.HexColor('#F8F6F4')
BORDER = colors.HexColor('#EDE8E3')
BRAND = colors.HexColor('#C2855A')

# Pastel palette for activity sections
PASTEL_PINK = colors.HexColor('#FDE8E8')
PASTEL_BLUE = colors.HexColor('#DBEAFE')
PASTEL_GREEN = colors.HexColor('#D1FAE5')
PASTEL_YELLOW = colors.HexColor('#FEF3C7')
PASTEL_PURPLE = colors.HexColor('#EDE9FE')
PASTEL_ORANGE = colors.HexColor('#FFEDD5')

# Accent colours per activity type
ACCENT_COLORS = {
    'number_tracing': colors.HexColor('#F472B6'),   # pink
    'letter_tracing': colors.HexColor('#A78BFA'),    # purple
    'counting':       colors.HexColor('#34D399'),    # green
    'drawing':        colors.HexColor('#FB923C'),    # orange
    'coloring':       colors.HexColor('#60A5FA'),    # blue
    'maze':           colors.HexColor('#F87171'),    # red
    'matching':       colors.HexColor('#FBBF24'),    # amber
    'dot_to_dot':     colors.HexColor('#2DD4BF'),    # teal
    'word_search':    colors.HexColor('#818CF8'),    # indigo
    'math_problems':  colors.HexColor('#4ADE80'),    # emerald
    'pattern':        colors.HexColor('#E879F9'),    # fuchsia
    'crossword_clues': colors.HexColor('#38BDF8'),   # sky
    'spot_difference': colors.HexColor('#FB7185'),   # rose
    'odd_one_out':    colors.HexColor('#F97316'),    # orange
    'fill_in_blank':  colors.HexColor('#06B6D4'),    # cyan
    'riddle':         colors.HexColor('#8B5CF6'),    # violet
    'scramble':       colors.HexColor('#EC4899'),    # pink
    'true_false':     colors.HexColor('#14B8A6'),    # teal
    'sequencing':     colors.HexColor('#F59E0B'),    # amber
    'rhyming':        colors.HexColor('#D946EF'),    # fuchsia
    'category_sort':  colors.HexColor('#3B82F6'),    # blue
}

PASTEL_BG_COLORS = {
    'number_tracing': PASTEL_PINK,
    'letter_tracing': PASTEL_PURPLE,
    'counting':       PASTEL_GREEN,
    'drawing':        PASTEL_ORANGE,
    'maze':           PASTEL_PINK,
    'matching':       PASTEL_YELLOW,
    'dot_to_dot':     PASTEL_GREEN,
    'word_search':    PASTEL_PURPLE,
    'math_problems':  PASTEL_GREEN,
    'pattern':        PASTEL_PURPLE,
    'crossword_clues': PASTEL_BLUE,
    'spot_difference': PASTEL_ORANGE,
    'odd_one_out':    PASTEL_ORANGE,
    'fill_in_blank':  PASTEL_BLUE,
    'riddle':         PASTEL_PURPLE,
    'scramble':       PASTEL_PINK,
    'true_false':     PASTEL_GREEN,
    'sequencing':     PASTEL_YELLOW,
    'rhyming':        PASTEL_PINK,
    'category_sort':  PASTEL_BLUE,
}

PAGE_W, PAGE_H = A4


# ── Custom Flowables ─────────────────────────────────────────────────

class HeaderBanner(Flowable):
    """Draws a colorful branded header banner with child name and theme."""

    def __init__(self, width, child_name, theme):
        super().__init__()
        self.width = width
        self.child_name = child_name
        self.theme = theme

    def wrap(self, availWidth, availHeight):
        return self.width, 60

    def draw(self):
        c = self.canv
        # Rounded colourful banner background
        c.setFillColor(BRAND)
        c.roundRect(0, 0, self.width, 56, 12, fill=1, stroke=0)

        # Lighter inner strip
        c.setFillColor(colors.HexColor('#D4976B'))
        c.roundRect(4, 4, self.width - 8, 48, 10, fill=1, stroke=0)

        # Child name — large white text
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', 18)
        c.drawString(16, 28, f"{self.child_name}'s Activity Sheet")

        # Theme — smaller cream text
        c.setFillColor(colors.HexColor('#FFF5EB'))
        c.setFont('Helvetica', 10)
        c.drawString(16, 12, self.theme)

        # Decorative circles on the right
        c.setFillColor(colors.HexColor('#E8A87C'))
        c.circle(self.width - 30, 40, 14, fill=1, stroke=0)
        c.setFillColor(colors.HexColor('#F0C4A8'))
        c.circle(self.width - 55, 18, 10, fill=1, stroke=0)
        c.setFillColor(colors.HexColor('#C2855A'))
        c.circle(self.width - 20, 14, 7, fill=1, stroke=0)


class ActivitySectionBanner(Flowable):
    """Draws a coloured rounded banner for each activity with a number badge."""

    def __init__(self, width, number, title, act_type):
        super().__init__()
        self.width = width
        self.number = number
        self.title = title
        self.act_type = act_type

    def wrap(self, availWidth, availHeight):
        return self.width, 32

    def draw(self):
        c = self.canv
        bg = PASTEL_BG_COLORS.get(self.act_type, PASTEL_BLUE)
        accent = ACCENT_COLORS.get(self.act_type, BRAND)

        # Pastel background strip
        c.setFillColor(bg)
        c.roundRect(0, 0, self.width, 28, 8, fill=1, stroke=0)

        # Number badge circle
        c.setFillColor(accent)
        c.circle(20, 14, 12, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', 12)
        c.drawCentredString(20, 9, str(self.number))

        # Title text
        c.setFillColor(NAVY)
        c.setFont('Helvetica-Bold', 12)
        c.drawString(40, 9, self.title)


class MazeFlowable(Flowable):
    """Draws a proper solvable grid maze using recursive backtracking."""

    def __init__(self, width, height, start_label='Start', end_label='End'):
        super().__init__()
        self.width = width
        self.height = height
        self.start_label = start_label
        self.end_label = end_label
        self.rows = 8
        self.cols = 8

    def _generate_maze(self):
        """Generate maze using recursive backtracking. Returns wall sets."""
        rows, cols = self.rows, self.cols
        # Each cell tracks which walls are open
        # walls_h[row][col] = True means there IS a wall on the BOTTOM of cell (row, col)
        # walls_v[row][col] = True means there IS a wall on the RIGHT of cell (row, col)
        walls_h = [[True] * cols for _ in range(rows + 1)]  # horizontal walls
        walls_v = [[True] * (cols + 1) for _ in range(rows)]  # vertical walls

        visited = [[False] * cols for _ in range(rows)]
        stack = [(0, 0)]
        visited[0][0] = True

        # Use a mix of labels + random salt so same labels produce different mazes
        import time
        random.seed(hash(self.start_label + self.end_label + str(id(self))) % 2**31)

        while stack:
            r, c = stack[-1]
            # Find unvisited neighbours
            neighbours = []
            if r > 0 and not visited[r - 1][c]:
                neighbours.append((r - 1, c, 'up'))
            if r < rows - 1 and not visited[r + 1][c]:
                neighbours.append((r + 1, c, 'down'))
            if c > 0 and not visited[r][c - 1]:
                neighbours.append((r, c - 1, 'left'))
            if c < cols - 1 and not visited[r][c + 1]:
                neighbours.append((r, c + 1, 'right'))

            if neighbours:
                nr, nc, direction = random.choice(neighbours)
                # Remove wall between current and chosen
                if direction == 'up':
                    walls_h[r][c] = False       # remove bottom wall of cell above = top wall of current
                elif direction == 'down':
                    walls_h[r + 1][c] = False   # remove bottom wall of current
                elif direction == 'left':
                    walls_v[r][c] = False        # remove left wall of current
                elif direction == 'right':
                    walls_v[r][c + 1] = False    # remove right wall of current

                visited[nr][nc] = True
                stack.append((nr, nc))
            else:
                stack.pop()

        return walls_h, walls_v

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        c = self.canv
        rows, cols = self.rows, self.cols
        cell_w = self.width / cols
        cell_h = self.height / rows

        walls_h, walls_v = self._generate_maze()

        # Open the entry and exit on outer walls
        walls_v[0][0] = False
        walls_v[rows - 1][cols] = False

        # Light background for maze area
        c.setFillColor(colors.HexColor('#FFF5F5'))
        c.roundRect(-4, -4, self.width + 8, self.height + 8, 6, fill=1, stroke=0)

        # Colourful maze walls
        maze_color = ACCENT_COLORS.get('maze', NAVY)
        c.setStrokeColor(maze_color)
        c.setLineWidth(2.0)

        for row in range(rows + 1):
            y = row * cell_h
            for col in range(cols):
                if walls_h[row][col]:
                    x1 = col * cell_w
                    x2 = (col + 1) * cell_w
                    c.line(x1, y, x2, y)

        for row in range(rows):
            for col in range(cols + 1):
                if walls_v[row][col]:
                    x = col * cell_w
                    y1 = row * cell_h
                    y2 = (row + 1) * cell_h
                    c.line(x, y1, x, y2)

        # Start marker — green circle with arrow
        sx = -2
        sy = cell_h * 0.5
        c.setFillColor(colors.HexColor('#34D399'))
        c.circle(sx - 14, sy, 9, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', 10)
        c.drawCentredString(sx - 14, sy - 4, '>')

        # End marker — gold star
        end_x = self.width + 2
        end_y = (rows - 0.5) * cell_h
        c.setFillColor(colors.HexColor('#FBBF24'))
        self._draw_small_star(c, end_x + 12, end_y, 8)

        # Labels
        c.setFillColor(colors.HexColor('#34D399'))
        c.setFont('Helvetica-Bold', 7)
        c.drawCentredString(sx - 14, sy - 16, self.start_label)
        c.setFillColor(colors.HexColor('#F59E0B'))
        c.drawString(end_x + 22, end_y - 3, self.end_label)

    def _draw_small_star(self, c, x, y, r):
        import math
        points = []
        for i in range(10):
            angle = math.radians(i * 36 - 90)
            radius = r if i % 2 == 0 else r * 0.4
            points.append((x + radius * math.cos(angle), y + radius * math.sin(angle)))
        p = c.beginPath()
        p.moveTo(points[0][0], points[0][1])
        for px, py in points[1:]:
            p.lineTo(px, py)
        p.close()
        c.drawPath(p, stroke=1, fill=1)


class DotToDotFlowable(Flowable):
    """Draws numbered dots arranged in the shape of the reveal object."""

    # Shape templates: normalised points (0-1 range) that outline each shape.
    # Kids connect dot 1→2→3→… to draw the shape.
    SHAPE_TEMPLATES = {
        'cat': [
            # Sitting cat outline: ears → head → body → tail
            (0.35, 0.95), (0.30, 0.82), (0.22, 0.75), (0.20, 0.65),
            (0.28, 0.58), (0.42, 0.55), (0.50, 0.58), (0.58, 0.55),
            (0.72, 0.58), (0.80, 0.65), (0.78, 0.75), (0.70, 0.82),
            (0.65, 0.95), (0.72, 0.50), (0.75, 0.35), (0.70, 0.20),
            (0.55, 0.12), (0.40, 0.12), (0.28, 0.18), (0.25, 0.35),
            (0.28, 0.50),
        ],
        'star': [
            (0.50, 0.95), (0.60, 0.68), (0.90, 0.62), (0.67, 0.45),
            (0.78, 0.18), (0.50, 0.32), (0.22, 0.18), (0.33, 0.45),
            (0.10, 0.62), (0.40, 0.68),
        ],
        'house': [
            (0.20, 0.10), (0.20, 0.55), (0.50, 0.90), (0.80, 0.55),
            (0.80, 0.10), (0.60, 0.10), (0.60, 0.35), (0.40, 0.35),
            (0.40, 0.10),
        ],
        'heart': [
            (0.50, 0.20), (0.35, 0.12), (0.20, 0.18), (0.10, 0.35),
            (0.12, 0.55), (0.25, 0.70), (0.50, 0.90), (0.75, 0.70),
            (0.88, 0.55), (0.90, 0.35), (0.80, 0.18), (0.65, 0.12),
        ],
        'fish': [
            (0.15, 0.50), (0.10, 0.65), (0.20, 0.78), (0.40, 0.80),
            (0.60, 0.72), (0.70, 0.58), (0.70, 0.42), (0.60, 0.28),
            (0.40, 0.20), (0.20, 0.22), (0.10, 0.35),
            (0.82, 0.68), (0.95, 0.78), (0.95, 0.22), (0.82, 0.32),
        ],
        'butterfly': [
            (0.50, 0.15), (0.50, 0.90),  # body top/bottom
            (0.38, 0.78), (0.20, 0.82), (0.10, 0.65), (0.18, 0.50),
            (0.38, 0.55), (0.50, 0.52),
            (0.62, 0.55), (0.82, 0.50), (0.90, 0.65), (0.80, 0.82),
            (0.62, 0.78),
        ],
        'tree': [
            (0.42, 0.10), (0.42, 0.40), (0.20, 0.40), (0.15, 0.55),
            (0.25, 0.55), (0.18, 0.70), (0.30, 0.70), (0.25, 0.85),
            (0.50, 0.95), (0.75, 0.85), (0.70, 0.70), (0.82, 0.70),
            (0.75, 0.55), (0.85, 0.55), (0.80, 0.40), (0.58, 0.40),
            (0.58, 0.10),
        ],
        'rocket': [
            (0.50, 0.95), (0.40, 0.80), (0.38, 0.55), (0.28, 0.40),
            (0.38, 0.35), (0.42, 0.15), (0.50, 0.10), (0.58, 0.15),
            (0.62, 0.35), (0.72, 0.40), (0.62, 0.55), (0.60, 0.80),
        ],
        'flower': [
            (0.50, 0.10), (0.45, 0.35),  # stem bottom to center
            (0.30, 0.30), (0.25, 0.45), (0.35, 0.50),  # left petal
            (0.30, 0.65), (0.42, 0.68), (0.50, 0.58),  # top petal
            (0.58, 0.68), (0.70, 0.65),  # right top
            (0.65, 0.50), (0.75, 0.45), (0.70, 0.30),  # right petal
            (0.55, 0.35),  # back to center
        ],
    }

    # Keywords → shape template mapping
    KEYWORD_MAP = {
        'cat': 'cat', 'kitten': 'cat', 'kitty': 'cat', 'sleeping cat': 'cat',
        'star': 'star', 'stars': 'star',
        'house': 'house', 'home': 'house', 'cottage': 'house', 'cabin': 'house',
        'heart': 'heart', 'love': 'heart', 'valentine': 'heart',
        'fish': 'fish', 'ocean': 'fish', 'sea': 'fish',
        'butterfly': 'butterfly', 'moth': 'butterfly',
        'tree': 'tree', 'forest': 'tree', 'plant': 'tree',
        'rocket': 'rocket', 'spaceship': 'rocket', 'space': 'rocket',
        'flower': 'flower', 'rose': 'flower', 'daisy': 'flower',
        'bird': 'star', 'dog': 'cat', 'puppy': 'cat', 'bunny': 'cat',
        'rabbit': 'cat', 'dinosaur': 'tree', 'robot': 'house',
        'car': 'house', 'boat': 'fish', 'ship': 'fish',
    }

    def __init__(self, width, height, total_dots=10, reveal='a shape'):
        super().__init__()
        self.width = width
        self.height = height
        self.total_dots = min(max(total_dots, 5), 20)
        self.reveal = reveal

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def _get_shape_points(self):
        """Pick the right shape template based on the reveal text."""
        reveal_lower = self.reveal.lower()

        # Try to match keywords in the reveal text
        matched_shape = None
        for keyword, shape_name in self.KEYWORD_MAP.items():
            if keyword in reveal_lower:
                matched_shape = shape_name
                break

        if matched_shape and matched_shape in self.SHAPE_TEMPLATES:
            template = self.SHAPE_TEMPLATES[matched_shape]
        else:
            # Fallback to star (looks nice and is universally recognisable)
            template = self.SHAPE_TEMPLATES['star']

        # Resample template to match total_dots using linear interpolation
        n = self.total_dots
        t_len = len(template)
        if n == t_len:
            return list(template)
        if n < t_len:
            # Pick evenly spaced points from template
            indices = [int(i * (t_len - 1) / (n - 1)) for i in range(n)]
            return [template[idx] for idx in indices]
        # n > t_len: interpolate extra points along the outline
        points = []
        for i in range(n):
            t = i * (t_len - 1) / (n - 1)
            idx = int(t)
            frac = t - idx
            if idx >= t_len - 1:
                points.append(template[-1])
            else:
                x = template[idx][0] + frac * (template[idx + 1][0] - template[idx][0])
                y = template[idx][1] + frac * (template[idx + 1][1] - template[idx][1])
                points.append((x, y))
        return points

    def draw(self):
        c = self.canv

        # Light background
        c.setFillColor(colors.HexColor('#D1FAE5'))
        c.roundRect(0, 0, self.width, self.height, 8, fill=1, stroke=0)

        dot_color = ACCENT_COLORS.get('dot_to_dot', NAVY)

        # Margins so dots don't sit at the very edge
        margin_x = self.width * 0.12
        margin_y = self.height * 0.12
        draw_w = self.width - 2 * margin_x
        draw_h = self.height - 2 * margin_y - 12  # leave room for hint text

        shape_points = self._get_shape_points()

        for i, (nx, ny) in enumerate(shape_points):
            x = margin_x + nx * draw_w
            y = margin_y + 12 + ny * draw_h  # +12 for hint text at bottom

            # Coloured dot
            c.setFillColor(dot_color)
            c.setStrokeColor(dot_color)
            c.circle(x, y, 4, fill=1, stroke=0)

            # Number label next to dot
            c.setFillColor(NAVY)
            c.setFont('Helvetica-Bold', 8)
            c.drawString(x + 6, y - 3, str(i + 1))

        # Hint text
        c.setFont('Helvetica', 8)
        c.setFillColor(colors.HexColor('#059669'))
        cx = self.width / 2
        c.drawCentredString(cx, 8, f'Connect 1 \u2192 {self.total_dots} to reveal: {self.reveal}')


class TracingFlowable(Flowable):
    """Draws dotted letters or numbers for tracing."""

    def __init__(self, width, height, items=None, is_numbers=True):
        super().__init__()
        self.width = width
        self.height = height
        self.items = items or []
        self.is_numbers = is_numbers

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        c = self.canv
        if not self.items:
            return

        items_per_row = min(5, len(self.items))
        cell_w = self.width / items_per_row
        cell_h = self.height / max(1, (len(self.items) + items_per_row - 1) // items_per_row)

        # Soft background
        guide_color = ACCENT_COLORS.get(
            'number_tracing' if self.is_numbers else 'letter_tracing',
            colors.HexColor('#A78BFA'),
        )
        bg_color = PASTEL_BG_COLORS.get(
            'number_tracing' if self.is_numbers else 'letter_tracing',
            PASTEL_PURPLE,
        )

        for i, item in enumerate(self.items[:10]):
            row = i // items_per_row
            col = i % items_per_row
            x = col * cell_w + cell_w / 2
            y = self.height - row * cell_h - cell_h / 2

            # Soft coloured circle behind each character
            c.setFillColor(bg_color)
            c.circle(x, y - 4, cell_w * 0.32, fill=1, stroke=0)

            # Dotted outline character in accent colour
            c.setStrokeColor(guide_color)
            c.setLineWidth(0.5)
            c.setDash(2, 2)

            c.setFont('Helvetica-Bold', 36)
            c.setFillColor(guide_color)
            c.drawCentredString(x, y - 12, str(item))

            # Baseline for writing — coloured
            c.setDash()
            c.setStrokeColor(guide_color)
            c.setLineWidth(0.8)
            c.line(x - cell_w * 0.35, y - 18, x + cell_w * 0.35, y - 18)


class DrawingFrameFlowable(Flowable):
    """Draws an empty bordered frame for drawing with a prompt."""

    def __init__(self, width, height, prompt='Draw here'):
        super().__init__()
        self.width = width
        self.height = height
        self.prompt = prompt

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        c = self.canv

        # Soft orange background
        c.setFillColor(colors.HexColor('#FFF7ED'))
        c.roundRect(0, 0, self.width, self.height, 10, fill=1, stroke=0)

        # Colourful dashed border
        accent = ACCENT_COLORS.get('drawing', BRAND)
        c.setStrokeColor(accent)
        c.setLineWidth(1.5)
        c.setDash(6, 4)
        c.roundRect(4, 4, self.width - 8, self.height - 8, 8)

        # Pencil icon hint (small circle)
        c.setDash()
        c.setFillColor(accent)
        c.circle(self.width / 2, self.height - 18, 6, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', 8)
        c.drawCentredString(self.width / 2, self.height - 21, '\u270F')

        # Prompt at top
        c.setFillColor(NAVY)
        c.setFont('Helvetica-Bold', 10)
        c.drawCentredString(self.width / 2, self.height - 34, self.prompt)


class ColoringSceneFlowable(Flowable):
    """Draws outline sketches for kids to color, based on scene keywords."""

    def __init__(self, width, height, scene=''):
        super().__init__()
        self.width = width
        self.height = height
        self.scene = scene.lower()

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def _detect_subject(self):
        """Find the single best-match subject from the scene text.
        Returns the subject key. Ordered so specific animals/objects match
        before vague words like 'garden' or 'night'.
        """
        scene = self.scene
        # Ordered from most-specific to least-specific
        subjects = [
            ('butterfly', ['butterfly', 'butterflies']),
            ('cat',       ['cat', 'kitten', 'kitty']),
            ('rabbit',    ['rabbit', 'bunny', 'hare']),
            ('bird',      ['bird', 'parrot', 'robin', 'sparrow']),
            ('fish',      ['fish', 'aquarium', 'underwater']),
            ('dinosaur',  ['dinosaur', 'dino', 'trex', 'prehistoric']),
            ('robot',     ['robot', 'machine', 'android']),
            ('car',       ['car', 'vehicle', 'truck']),
            ('castle',    ['castle', 'palace', 'kingdom', 'princess', 'prince', 'knight']),
            ('rocket',    ['rocket', 'spaceship', 'astronaut']),
            ('house',     ['house', 'home', 'cottage', 'cabin']),
            ('flower',    ['flower', 'flowers', 'bloom', 'petal', 'rose', 'daisy']),
            ('tree',      ['tree', 'forest']),
            ('heart',     ['heart', 'love', 'valentine']),
            ('sun',       ['sun', 'sunny', 'sunrise', 'morning']),
            ('moon',      ['moon', 'crescent']),
            ('rainbow',   ['rainbow']),
            ('star',      ['star', 'stars', 'twinkle']),
            ('ocean',     ['ocean', 'sea', 'wave', 'beach']),
            ('cloud',     ['cloud', 'clouds', 'fluffy']),
            ('garden',    ['garden', 'park']),
            ('night',     ['night', 'sky', 'sleepy']),
        ]
        for key, keywords in subjects:
            if any(w in scene for w in keywords):
                return key
        return None

    def draw(self):
        import math
        c = self.canv
        cx, cy = self.width / 2, self.height / 2

        # Soft blue background
        c.setFillColor(colors.HexColor('#EFF6FF'))
        c.roundRect(0, 0, self.width, self.height, 10, fill=1, stroke=0)

        # Colourful border
        c.setStrokeColor(ACCENT_COLORS.get('coloring', colors.HexColor('#60A5FA')))
        c.setLineWidth(1.5)
        c.roundRect(2, 2, self.width - 4, self.height - 4, 8, fill=0)

        # Drawing settings
        c.setLineWidth(2.0)
        c.setStrokeColor(colors.HexColor('#6366F1'))
        c.setFillColor(colors.white)

        subject = self._detect_subject()
        drawn = False

        # ── Butterfly (large, centered) ──
        if subject == 'butterfly':
            bx, by = cx, cy
            s = min(self.width, self.height) * 0.38  # scale factor
            # Body
            c.ellipse(bx - 4, by - s * 0.5, bx + 4, by + s * 0.5, stroke=1, fill=0)
            # Upper wings (large)
            c.ellipse(bx - s, by, bx - 4, by + s * 0.7, stroke=1, fill=0)
            c.ellipse(bx + 4, by, bx + s, by + s * 0.7, stroke=1, fill=0)
            # Lower wings
            c.ellipse(bx - s * 0.75, by - s * 0.55, bx - 4, by + s * 0.05, stroke=1, fill=0)
            c.ellipse(bx + 4, by - s * 0.55, bx + s * 0.75, by + s * 0.05, stroke=1, fill=0)
            # Wing decorations (inner circles)
            c.circle(bx - s * 0.5, by + s * 0.35, s * 0.18, stroke=1, fill=0)
            c.circle(bx + s * 0.5, by + s * 0.35, s * 0.18, stroke=1, fill=0)
            c.circle(bx - s * 0.4, by - s * 0.2, s * 0.12, stroke=1, fill=0)
            c.circle(bx + s * 0.4, by - s * 0.2, s * 0.12, stroke=1, fill=0)
            # Antennae
            c.setLineWidth(1.5)
            p = c.beginPath()
            p.moveTo(bx - 2, by + s * 0.5)
            p.curveTo(bx - s * 0.35, by + s * 0.85, bx - s * 0.4, by + s * 0.9, bx - s * 0.25, by + s * 0.82)
            c.drawPath(p, stroke=1, fill=0)
            c.circle(bx - s * 0.25, by + s * 0.82, 3, stroke=1, fill=0)
            p = c.beginPath()
            p.moveTo(bx + 2, by + s * 0.5)
            p.curveTo(bx + s * 0.35, by + s * 0.85, bx + s * 0.4, by + s * 0.9, bx + s * 0.25, by + s * 0.82)
            c.drawPath(p, stroke=1, fill=0)
            c.circle(bx + s * 0.25, by + s * 0.82, 3, stroke=1, fill=0)
            drawn = True

        # ── Cat (large, centered) ──
        elif subject == 'cat':
            s = min(self.width, self.height) * 0.35
            kx, ky = cx, cy - s * 0.15
            # Body (large oval)
            c.ellipse(kx - s * 0.6, ky - s * 0.6, kx + s * 0.6, ky + s * 0.25, stroke=1, fill=0)
            # Head
            c.circle(kx, ky + s * 0.6, s * 0.42, stroke=1, fill=0)
            # Ears
            for side in [-1, 1]:
                p = c.beginPath()
                p.moveTo(kx + side * s * 0.3, ky + s * 0.9)
                p.lineTo(kx + side * s * 0.22, ky + s * 1.15)
                p.lineTo(kx + side * s * 0.08, ky + s * 0.95)
                c.drawPath(p, stroke=1, fill=0)
            # Eyes
            c.ellipse(kx - s * 0.18, ky + s * 0.58, kx - s * 0.06, ky + s * 0.72, stroke=1, fill=0)
            c.ellipse(kx + s * 0.06, ky + s * 0.58, kx + s * 0.18, ky + s * 0.72, stroke=1, fill=0)
            # Nose
            p = c.beginPath()
            p.moveTo(kx, ky + s * 0.52)
            p.lineTo(kx - s * 0.06, ky + s * 0.44)
            p.lineTo(kx + s * 0.06, ky + s * 0.44)
            p.close()
            c.drawPath(p, stroke=1, fill=0)
            # Whiskers
            c.setLineWidth(1)
            for side in [-1, 1]:
                c.line(kx + side * s * 0.08, ky + s * 0.48,
                       kx + side * s * 0.45, ky + s * 0.52)
                c.line(kx + side * s * 0.08, ky + s * 0.45,
                       kx + side * s * 0.42, ky + s * 0.42)
            c.setLineWidth(2.0)
            # Tail
            p = c.beginPath()
            p.moveTo(kx + s * 0.6, ky - s * 0.3)
            p.curveTo(kx + s, ky - s * 0.4, kx + s * 1.1, ky + s * 0.1, kx + s * 0.85, ky + s * 0.2)
            c.drawPath(p, stroke=1, fill=0)
            drawn = True

        # ── Rabbit/Bunny ──
        elif subject == 'rabbit':
            s = min(self.width, self.height) * 0.32
            rx, ry = cx, cy - s * 0.2
            # Body
            c.ellipse(rx - s * 0.65, ry - s * 0.7, rx + s * 0.65, ry + s * 0.2, stroke=1, fill=0)
            # Head
            c.circle(rx, ry + s * 0.55, s * 0.4, stroke=1, fill=0)
            # Ears
            c.ellipse(rx - s * 0.25, ry + s * 0.85, rx - s * 0.07, ry + s * 1.45, stroke=1, fill=0)
            c.ellipse(rx + s * 0.07, ry + s * 0.85, rx + s * 0.25, ry + s * 1.45, stroke=1, fill=0)
            # Eyes
            c.circle(rx - s * 0.15, ry + s * 0.62, s * 0.06, stroke=1, fill=0)
            c.circle(rx + s * 0.15, ry + s * 0.62, s * 0.06, stroke=1, fill=0)
            # Nose
            c.circle(rx, ry + s * 0.48, s * 0.05, stroke=1, fill=0)
            # Tail
            c.circle(rx + s * 0.6, ry - s * 0.35, s * 0.15, stroke=1, fill=0)
            drawn = True

        # ── Bird ──
        elif subject == 'bird':
            s = min(self.width, self.height) * 0.35
            bx, by = cx - s * 0.1, cy
            # Body
            c.ellipse(bx - s * 0.55, by - s * 0.35, bx + s * 0.45, by + s * 0.35, stroke=1, fill=0)
            # Head
            c.circle(bx + s * 0.55, by + s * 0.2, s * 0.3, stroke=1, fill=0)
            # Beak
            p = c.beginPath()
            p.moveTo(bx + s * 0.82, by + s * 0.25)
            p.lineTo(bx + s * 1.1, by + s * 0.2)
            p.lineTo(bx + s * 0.82, by + s * 0.12)
            c.drawPath(p, stroke=1, fill=0)
            # Eye
            c.circle(bx + s * 0.6, by + s * 0.28, s * 0.05, stroke=1, fill=0)
            # Wing
            c.ellipse(bx - s * 0.3, by + s * 0.05, bx + s * 0.25, by + s * 0.38, stroke=1, fill=0)
            # Tail
            p = c.beginPath()
            p.moveTo(bx - s * 0.55, by)
            p.lineTo(bx - s * 0.9, by + s * 0.2)
            p.lineTo(bx - s * 0.9, by - s * 0.12)
            p.close()
            c.drawPath(p, stroke=1, fill=0)
            drawn = True

        # ── Fish ──
        elif subject in ('fish', 'ocean'):
            s = min(self.width, self.height) * 0.35
            fx, fy = cx, cy
            # Body
            c.ellipse(fx - s * 0.7, fy - s * 0.4, fx + s * 0.5, fy + s * 0.4, stroke=1, fill=0)
            # Tail
            p = c.beginPath()
            p.moveTo(fx + s * 0.5, fy)
            p.lineTo(fx + s * 0.95, fy + s * 0.4)
            p.lineTo(fx + s * 0.95, fy - s * 0.4)
            p.close()
            c.drawPath(p, stroke=1, fill=0)
            # Eye
            c.circle(fx - s * 0.3, fy + s * 0.1, s * 0.08, stroke=1, fill=0)
            c.circle(fx - s * 0.28, fy + s * 0.12, s * 0.03, stroke=1, fill=1)
            # Mouth
            c.arc(fx - s * 0.58, fy - s * 0.1, fx - s * 0.38, fy + s * 0.05, 180, 180)
            # Fin
            p = c.beginPath()
            p.moveTo(fx - s * 0.1, fy + s * 0.4)
            p.curveTo(fx + s * 0.05, fy + s * 0.72, fx + s * 0.2, fy + s * 0.65, fx + s * 0.15, fy + s * 0.4)
            c.drawPath(p, stroke=1, fill=0)
            # Scales pattern
            for row in range(2):
                for col in range(3):
                    sx2 = fx - s * 0.3 + col * s * 0.2
                    sy2 = fy - s * 0.1 + row * s * 0.18
                    c.arc(sx2 - s * 0.06, sy2 - s * 0.06, sx2 + s * 0.06, sy2 + s * 0.06, 0, 180)
            drawn = True

        # ── Flower (large, centered) ──
        elif subject in ('flower', 'garden'):
            s = min(self.width, self.height) * 0.3
            fx, fy = cx, cy + s * 0.15
            # Petals
            c.setLineWidth(2.0)
            petal_r = s * 0.32
            for angle in range(0, 360, 60):
                rad = math.radians(angle)
                px = fx + s * 0.38 * math.cos(rad)
                py = fy + s * 0.38 * math.sin(rad)
                c.circle(px, py, petal_r, stroke=1, fill=0)
            # Center
            c.circle(fx, fy, s * 0.2, stroke=1, fill=0)
            # Stem
            c.setLineWidth(2.5)
            c.line(fx, fy - s * 0.32, fx, fy - s * 1.4)
            # Leaves
            c.setLineWidth(1.5)
            p = c.beginPath()
            p.moveTo(fx, fy - s * 0.8)
            p.curveTo(fx + s * 0.5, fy - s * 0.65, fx + s * 0.5, fy - s * 1.0, fx, fy - s * 0.9)
            c.drawPath(p, stroke=1, fill=0)
            p = c.beginPath()
            p.moveTo(fx, fy - s * 1.1)
            p.curveTo(fx - s * 0.45, fy - s * 0.95, fx - s * 0.45, fy - s * 1.25, fx, fy - s * 1.2)
            c.drawPath(p, stroke=1, fill=0)
            drawn = True

        # ── Sun ──
        elif subject == 'sun':
            s = min(self.width, self.height) * 0.28
            c.circle(cx, cy, s, stroke=1, fill=0)
            # Smiley face
            c.setLineWidth(1.5)
            c.circle(cx - s * 0.3, cy + s * 0.2, s * 0.08, stroke=1, fill=0)
            c.circle(cx + s * 0.3, cy + s * 0.2, s * 0.08, stroke=1, fill=0)
            c.arc(cx - s * 0.35, cy - s * 0.2, cx + s * 0.35, cy + s * 0.1, 180, 180)
            # Rays
            c.setLineWidth(2.0)
            for angle in range(0, 360, 30):
                rad = math.radians(angle)
                c.line(cx + s * 1.15 * math.cos(rad), cy + s * 1.15 * math.sin(rad),
                       cx + s * 1.45 * math.cos(rad), cy + s * 1.45 * math.sin(rad))
            drawn = True

        # ── Moon ──
        elif subject in ('moon', 'night'):
            s = min(self.width, self.height) * 0.35
            mx, my = cx, cy
            c.circle(mx, my, s, stroke=1, fill=0)
            c.setFillColor(colors.HexColor('#EFF6FF'))
            c.setStrokeColor(colors.HexColor('#EFF6FF'))
            c.circle(mx + s * 0.4, my + s * 0.25, s * 0.85, stroke=1, fill=1)
            c.setStrokeColor(colors.HexColor('#6366F1'))
            c.setFillColor(colors.white)
            c.circle(mx, my, s, stroke=1, fill=0)
            # Sleeping face
            c.setLineWidth(1.5)
            c.arc(mx - s * 0.35, my + s * 0.05, mx - s * 0.1, my + s * 0.25, 0, 180)
            c.arc(mx + s * 0.05, my + s * 0.05, mx + s * 0.3, my + s * 0.25, 0, 180)
            c.arc(mx - s * 0.25, my - s * 0.3, mx + s * 0.15, my - s * 0.1, 180, 180)
            # Stars around
            self._draw_star(c, cx + s * 1.1, cy + s * 0.6, s * 0.15)
            self._draw_star(c, cx + s * 0.9, cy - s * 0.7, s * 0.1)
            self._draw_star(c, cx - s * 0.8, cy + s * 0.8, s * 0.12)
            drawn = True

        # ── Heart ──
        elif subject == 'heart':
            s = min(self.width, self.height) * 0.38
            hx, hy = cx, cy
            c.setLineWidth(2.5)
            p = c.beginPath()
            p.moveTo(hx, hy - s * 0.6)
            p.curveTo(hx - s, hy + s * 0.15, hx - s, hy + s * 0.7, hx, hy + s * 0.4)
            p.curveTo(hx + s, hy + s * 0.7, hx + s, hy + s * 0.15, hx, hy - s * 0.6)
            c.drawPath(p, stroke=1, fill=0)
            drawn = True

        # ── House ──
        elif subject == 'house':
            s = min(self.width, self.height) * 0.32
            hx, hy = cx - s * 0.5, cy - s * 0.6
            hw, hh = s, s * 0.8
            c.rect(hx, hy, hw, hh, stroke=1, fill=0)
            # Roof
            p = c.beginPath()
            p.moveTo(hx - s * 0.15, hy + hh)
            p.lineTo(hx + hw / 2, hy + hh + s * 0.55)
            p.lineTo(hx + hw + s * 0.15, hy + hh)
            p.close()
            c.drawPath(p, stroke=1, fill=0)
            # Door
            dw, dh = hw * 0.25, hh * 0.5
            c.rect(hx + hw / 2 - dw / 2, hy, dw, dh, stroke=1, fill=0)
            c.circle(hx + hw / 2 + dw * 0.25, hy + dh * 0.5, 2.5, stroke=1, fill=0)
            # Windows
            ww = hw * 0.2
            c.rect(hx + hw * 0.1, hy + hh * 0.45, ww, ww, stroke=1, fill=0)
            c.line(hx + hw * 0.1, hy + hh * 0.45 + ww / 2, hx + hw * 0.1 + ww, hy + hh * 0.45 + ww / 2)
            c.line(hx + hw * 0.1 + ww / 2, hy + hh * 0.45, hx + hw * 0.1 + ww / 2, hy + hh * 0.45 + ww)
            c.rect(hx + hw * 0.7, hy + hh * 0.45, ww, ww, stroke=1, fill=0)
            c.line(hx + hw * 0.7, hy + hh * 0.45 + ww / 2, hx + hw * 0.7 + ww, hy + hh * 0.45 + ww / 2)
            c.line(hx + hw * 0.7 + ww / 2, hy + hh * 0.45, hx + hw * 0.7 + ww / 2, hy + hh * 0.45 + ww)
            drawn = True

        # ── Tree ──
        elif subject == 'tree':
            s = min(self.width, self.height) * 0.35
            tx, ty = cx, cy - s * 0.5
            # Trunk
            c.rect(tx - s * 0.1, ty, s * 0.2, s * 0.55, stroke=1, fill=0)
            # Foliage
            c.circle(tx, ty + s * 0.9, s * 0.42, stroke=1, fill=0)
            c.circle(tx - s * 0.3, ty + s * 0.7, s * 0.32, stroke=1, fill=0)
            c.circle(tx + s * 0.3, ty + s * 0.7, s * 0.32, stroke=1, fill=0)
            c.circle(tx - s * 0.15, ty + s * 1.05, s * 0.25, stroke=1, fill=0)
            c.circle(tx + s * 0.15, ty + s * 1.05, s * 0.25, stroke=1, fill=0)
            drawn = True

        # ── Star ──
        elif subject == 'star':
            s = min(self.width, self.height) * 0.38
            self._draw_star(c, cx, cy, s)
            # Smaller stars around
            self._draw_star(c, cx - s * 1.2, cy + s * 0.6, s * 0.2)
            self._draw_star(c, cx + s * 1.1, cy - s * 0.5, s * 0.18)
            self._draw_star(c, cx - s * 0.8, cy - s * 0.8, s * 0.15)
            self._draw_star(c, cx + s * 0.7, cy + s * 0.9, s * 0.22)
            drawn = True

        # ── Cloud ──
        elif subject == 'cloud':
            s = min(self.width, self.height) * 0.3
            bx, by = cx, cy
            c.circle(bx, by, s * 0.5, stroke=1, fill=0)
            c.circle(bx - s * 0.45, by - s * 0.1, s * 0.38, stroke=1, fill=0)
            c.circle(bx + s * 0.45, by - s * 0.1, s * 0.38, stroke=1, fill=0)
            c.circle(bx - s * 0.22, by + s * 0.18, s * 0.32, stroke=1, fill=0)
            c.circle(bx + s * 0.22, by + s * 0.18, s * 0.32, stroke=1, fill=0)
            drawn = True

        # ── Car ──
        elif subject == 'car':
            s = min(self.width, self.height) * 0.32
            cx2, cy2 = cx, cy - s * 0.1
            c.rect(cx2 - s, cy2, s * 2, s * 0.65, stroke=1, fill=0)
            # Roof
            p = c.beginPath()
            p.moveTo(cx2 - s * 0.45, cy2 + s * 0.65)
            p.lineTo(cx2 - s * 0.25, cy2 + s * 1.15)
            p.lineTo(cx2 + s * 0.6, cy2 + s * 1.15)
            p.lineTo(cx2 + s * 0.85, cy2 + s * 0.65)
            c.drawPath(p, stroke=1, fill=0)
            # Wheels
            for wx in [cx2 - s * 0.55, cx2 + s * 0.55]:
                c.circle(wx, cy2 - s * 0.05, s * 0.22, stroke=1, fill=0)
                c.circle(wx, cy2 - s * 0.05, s * 0.1, stroke=1, fill=0)
            # Windows
            c.rect(cx2 - s * 0.35, cy2 + s * 0.72, s * 0.45, s * 0.32, stroke=1, fill=0)
            c.rect(cx2 + s * 0.18, cy2 + s * 0.72, s * 0.45, s * 0.32, stroke=1, fill=0)
            drawn = True

        # ── Dinosaur ──
        elif subject == 'dinosaur':
            s = min(self.width, self.height) * 0.3
            dx, dy = cx, cy - s * 0.3
            c.ellipse(dx - s * 0.6, dy, dx + s * 0.5, dy + s * 0.7, stroke=1, fill=0)
            c.ellipse(dx + s * 0.4, dy + s * 0.5, dx + s * 1.0, dy + s * 0.95, stroke=1, fill=0)
            c.circle(dx + s * 0.75, dy + s * 0.82, s * 0.06, stroke=1, fill=0)
            c.line(dx + s * 0.92, dy + s * 0.7, dx + s * 1.0, dy + s * 0.7)
            c.rect(dx - s * 0.35, dy - s * 0.38, s * 0.18, s * 0.4, stroke=1, fill=0)
            c.rect(dx + s * 0.15, dy - s * 0.38, s * 0.18, s * 0.4, stroke=1, fill=0)
            p = c.beginPath()
            p.moveTo(dx - s * 0.6, dy + s * 0.35)
            p.curveTo(dx - s, dy + s * 0.4, dx - s * 1.15, dy + s * 0.15, dx - s * 1.05, dy + s * 0.05)
            c.drawPath(p, stroke=1, fill=0)
            for i in range(4):
                sx2 = dx - s * 0.25 + i * s * 0.25
                p = c.beginPath()
                p.moveTo(sx2 - s * 0.08, dy + s * 0.7)
                p.lineTo(sx2, dy + s * 0.88)
                p.lineTo(sx2 + s * 0.08, dy + s * 0.7)
                c.drawPath(p, stroke=1, fill=0)
            drawn = True

        # ── Robot ──
        elif subject == 'robot':
            s = min(self.width, self.height) * 0.28
            rx2, ry2 = cx, cy - s * 0.1
            c.rect(rx2 - s * 0.4, ry2 + s * 0.45, s * 0.8, s * 0.55, stroke=1, fill=0)
            c.line(rx2, ry2 + s, rx2, ry2 + s * 1.2)
            c.circle(rx2, ry2 + s * 1.25, s * 0.08, stroke=1, fill=0)
            c.rect(rx2 - s * 0.25, ry2 + s * 0.65, s * 0.2, s * 0.2, stroke=1, fill=0)
            c.rect(rx2 + s * 0.05, ry2 + s * 0.65, s * 0.2, s * 0.2, stroke=1, fill=0)
            c.rect(rx2 - s * 0.2, ry2 + s * 0.5, s * 0.4, s * 0.1, stroke=1, fill=0)
            c.rect(rx2 - s * 0.5, ry2 - s * 0.15, s, s * 0.6, stroke=1, fill=0)
            c.circle(rx2, ry2 + s * 0.2, s * 0.1, stroke=1, fill=0)
            c.circle(rx2, ry2 + s * 0.0, s * 0.08, stroke=1, fill=0)
            c.rect(rx2 - s * 0.7, ry2 + s * 0.08, s * 0.2, s * 0.38, stroke=1, fill=0)
            c.rect(rx2 + s * 0.5, ry2 + s * 0.08, s * 0.2, s * 0.38, stroke=1, fill=0)
            c.rect(rx2 - s * 0.3, ry2 - s * 0.58, s * 0.25, s * 0.45, stroke=1, fill=0)
            c.rect(rx2 + s * 0.05, ry2 - s * 0.58, s * 0.25, s * 0.45, stroke=1, fill=0)
            drawn = True

        # ── Castle ──
        elif subject == 'castle':
            s = min(self.width, self.height) * 0.3
            bx2, by2 = cx - s * 0.8, cy - s * 0.6
            bw, bh = s * 1.6, s * 0.95
            c.rect(bx2, by2, bw, bh, stroke=1, fill=0)
            tw = s * 0.32
            for tx2 in [bx2 - s * 0.15, bx2 + bw - s * 0.17]:
                c.rect(tx2, by2 + bh, tw, s * 0.4, stroke=1, fill=0)
                for b in range(3):
                    c.rect(tx2 + b * tw * 0.35, by2 + bh + s * 0.4, tw * 0.25, s * 0.15, stroke=1, fill=0)
            c.rect(bx2 + bw / 2 - s * 0.18, by2, s * 0.36, s * 0.5, stroke=1, fill=0)
            c.arc(bx2 + bw / 2 - s * 0.18, by2 + s * 0.3,
                  bx2 + bw / 2 + s * 0.18, by2 + s * 0.66, 0, 180)
            c.circle(bx2 + s * 0.4, by2 + bh * 0.65, s * 0.1, stroke=1, fill=0)
            c.circle(bx2 + bw - s * 0.4, by2 + bh * 0.65, s * 0.1, stroke=1, fill=0)
            c.line(bx2 + bw / 2, by2 + bh, bx2 + bw / 2, by2 + bh + s * 0.65)
            p = c.beginPath()
            p.moveTo(bx2 + bw / 2, by2 + bh + s * 0.65)
            p.lineTo(bx2 + bw / 2 + s * 0.25, by2 + bh + s * 0.55)
            p.lineTo(bx2 + bw / 2, by2 + bh + s * 0.45)
            c.drawPath(p, stroke=1, fill=0)
            drawn = True

        # ── Rocket ──
        elif subject == 'rocket':
            s = min(self.width, self.height) * 0.3
            rx3, ry3 = cx, cy - s * 0.3
            c.rect(rx3 - s * 0.25, ry3, s * 0.5, s * 1.0, stroke=1, fill=0)
            p = c.beginPath()
            p.moveTo(rx3 - s * 0.25, ry3 + s)
            p.lineTo(rx3, ry3 + s * 1.38)
            p.lineTo(rx3 + s * 0.25, ry3 + s)
            c.drawPath(p, stroke=1, fill=0)
            c.circle(rx3, ry3 + s * 0.7, s * 0.14, stroke=1, fill=0)
            for side in [-1, 1]:
                p = c.beginPath()
                p.moveTo(rx3 + side * s * 0.25, ry3)
                p.lineTo(rx3 + side * s * 0.48, ry3 - s * 0.25)
                p.lineTo(rx3 + side * s * 0.25, ry3 + s * 0.25)
                c.drawPath(p, stroke=1, fill=0)
            p = c.beginPath()
            p.moveTo(rx3 - s * 0.15, ry3)
            p.curveTo(rx3 - s * 0.08, ry3 - s * 0.3, rx3 + s * 0.08, ry3 - s * 0.3, rx3 + s * 0.15, ry3)
            c.drawPath(p, stroke=1, fill=0)
            drawn = True

        # ── Rainbow ──
        elif subject == 'rainbow':
            s = min(self.width, self.height) * 0.35
            for i, r in enumerate([s * 1.0, s * 0.85, s * 0.7, s * 0.55, s * 0.4]):
                c.arc(cx - r, cy - r + s * 0.1, cx + r, cy + r + s * 0.1, 0, 180)
            for bx3 in [cx - s, cx + s * 0.75]:
                c.circle(bx3, cy + s * 0.1, s * 0.2, stroke=1, fill=0)
                c.circle(bx3 + s * 0.15, cy + s * 0.15, s * 0.16, stroke=1, fill=0)
                c.circle(bx3 - s * 0.12, cy + s * 0.15, s * 0.14, stroke=1, fill=0)
            drawn = True

        # ── Fallback: cute scene ──
        if not drawn:
            s = min(self.width, self.height) * 0.22
            c.setLineWidth(1.5)
            # Sun top-right
            c.circle(cx + s * 2, cy + s * 1.5, s * 0.65, stroke=1, fill=0)
            c.arc(cx + s * 1.78, cy + s * 1.28, cx + s * 2.22, cy + s * 1.52, 180, 180)
            c.circle(cx + s * 1.88, cy + s * 1.6, s * 0.06, stroke=1, fill=0)
            c.circle(cx + s * 2.12, cy + s * 1.6, s * 0.06, stroke=1, fill=0)
            for angle in range(0, 360, 45):
                rad = math.radians(angle)
                c.line(cx + s * 2 + s * 0.78 * math.cos(rad), cy + s * 1.5 + s * 0.78 * math.sin(rad),
                       cx + s * 2 + s * 1.0 * math.cos(rad), cy + s * 1.5 + s * 1.0 * math.sin(rad))
            # Star center-left
            self._draw_star(c, cx - s * 0.8, cy + s * 0.3, s * 1.0)
            # Heart bottom-right
            hx2, hy2 = cx + s * 1.0, cy - s * 1.0
            p = c.beginPath()
            p.moveTo(hx2, hy2 - s * 0.5)
            p.curveTo(hx2 - s * 0.7, hy2 + s * 0.1, hx2 - s * 0.7, hy2 + s * 0.65, hx2, hy2 + s * 0.35)
            p.curveTo(hx2 + s * 0.7, hy2 + s * 0.65, hx2 + s * 0.7, hy2 + s * 0.1, hx2, hy2 - s * 0.5)
            c.drawPath(p, stroke=1, fill=0)
            # Flower bottom-left
            fx2, fy2 = cx - s * 1.8, cy - s * 0.8
            for angle in range(0, 360, 72):
                rad = math.radians(angle)
                c.circle(fx2 + s * 0.35 * math.cos(rad), fy2 + s * 0.35 * math.sin(rad),
                         s * 0.25, stroke=1, fill=0)
            c.circle(fx2, fy2, s * 0.18, stroke=1, fill=0)

        # "Color me!" label
        c.setFont('Helvetica-Bold', 9)
        c.setFillColor(ACCENT_COLORS.get('coloring', colors.HexColor('#60A5FA')))
        c.drawCentredString(cx, 8, '\u2605 Color me! \u2605')

    def _draw_star(self, c, x, y, r):
        import math
        points = []
        for i in range(10):
            angle = math.radians(i * 36 - 90)
            radius = r if i % 2 == 0 else r * 0.4
            points.append((x + radius * math.cos(angle), y + radius * math.sin(angle)))
        p = c.beginPath()
        p.moveTo(points[0][0], points[0][1])
        for px, py in points[1:]:
            p.lineTo(px, py)
        p.close()
        c.drawPath(p, stroke=1, fill=0)


# ── PDF Builder ──────────────────────────────────────────────────────

class KidsActivityPDFGenerator:

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        self.styles.add(ParagraphStyle(
            'ActivityTitle',
            parent=self.styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=14,
            textColor=NAVY,
            spaceAfter=4 * mm,
        ))
        self.styles.add(ParagraphStyle(
            'ActivityLabel',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=GOLD,
            spaceAfter=2 * mm,
        ))
        self.styles.add(ParagraphStyle(
            'Body',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#333333'),
        ))
        self.styles.add(ParagraphStyle(
            'Footer',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=7,
            textColor=colors.HexColor('#AAAAAA'),
            alignment=1,  # center
        ))

    def generate_for_day(self, activity_day):
        """Generate a PDF activity sheet for one child's one day."""
        child = activity_day.child
        plan = activity_day.plan

        # File path
        filename = f'activities_{plan.id}_{child.id}_day{activity_day.day_of_week}.pdf'
        filepath = os.path.join(settings.MEDIA_ROOT, 'kids_activity_pdfs', filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # If already generated, return existing
        if os.path.exists(filepath):
            return filepath

        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            leftMargin=1.5 * cm,
            rightMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
        )

        content_width = PAGE_W - 3 * cm
        story = []

        # ── Header ───────────────────────────────────────────────
        story.append(HeaderBanner(content_width, child.name, plan.theme))
        story.append(Spacer(1, 6 * mm))

        # ── Activities ───────────────────────────────────────────
        activities = (activity_day.worksheet_content or {}).get('activities', [])

        for i, act in enumerate(activities):
            act_type = act.get('type', '')
            title = act.get('title', f'Activity {i + 1}')
            data = act.get('data', {})

            # Colourful activity section banner
            story.append(Spacer(1, 4 * mm))
            story.append(ActivitySectionBanner(content_width, i + 1, title, act_type))
            story.append(Spacer(1, 3 * mm))

            if act_type == 'number_tracing':
                numbers = data.get('numbers', data.get('items', [1, 2, 3, 4, 5]))
                story.append(Paragraph('Trace the numbers:', self.styles['Body']))
                story.append(Spacer(1, 2 * mm))
                story.append(TracingFlowable(content_width, 5 * cm, items=numbers, is_numbers=True))

            elif act_type == 'letter_tracing':
                letters = data.get('letters', data.get('items', ['A', 'B', 'C']))
                story.append(Paragraph('Trace the letters:', self.styles['Body']))
                story.append(Spacer(1, 2 * mm))
                story.append(TracingFlowable(content_width, 5 * cm, items=letters, is_numbers=False))

            elif act_type == 'counting':
                prompt = data.get('prompt', 'Count the items')
                story.append(Paragraph(prompt, self.styles['Body']))
                story.append(Spacer(1, 2 * mm))
                # Answer line
                story.append(Paragraph('Answer: ___________', self.styles['Body']))

            elif act_type == 'drawing':
                prompt = data.get('prompt', 'Draw something fun!')
                story.append(DrawingFrameFlowable(content_width, 7 * cm, prompt=prompt))

            elif act_type == 'maze':
                start = data.get('start_label', 'Start')
                end = data.get('end_label', 'End')
                story.append(Paragraph(f'Help {start} reach {end}!', self.styles['Body']))
                story.append(Spacer(1, 2 * mm))
                story.append(MazeFlowable(content_width * 0.7, 6 * cm, start_label=start, end_label=end))

            elif act_type == 'matching':
                left = data.get('left', [])
                right = data.get('right', [])
                if left and right:
                    story.append(Paragraph('Draw a line to match:', self.styles['Body']))
                    story.append(Spacer(1, 2 * mm))
                    right_shuffled = right[:]
                    random.shuffle(right_shuffled)
                    match_accent = ACCENT_COLORS.get('matching', GOLD)
                    # Coloured dots connector
                    dot_str = '\u25CF \u2500 \u2500 \u2500 \u2500 \u25CF'
                    table_data = []
                    for j in range(max(len(left), len(right_shuffled))):
                        l_val = left[j] if j < len(left) else ''
                        r_val = right_shuffled[j] if j < len(right_shuffled) else ''
                        table_data.append([l_val, dot_str, r_val])
                    t = Table(table_data, colWidths=[content_width * 0.3, content_width * 0.4, content_width * 0.3])
                    row_colors = [PASTEL_YELLOW, colors.white]
                    style_cmds = [
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 11),
                        ('TEXTCOLOR', (0, 0), (0, -1), NAVY),
                        ('TEXTCOLOR', (2, 0), (2, -1), NAVY),
                        ('TEXTCOLOR', (1, 0), (1, -1), match_accent),
                        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                        ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ]
                    for row_idx in range(len(table_data)):
                        bg = row_colors[row_idx % 2]
                        style_cmds.append(('BACKGROUND', (0, row_idx), (-1, row_idx), bg))
                    t.setStyle(TableStyle(style_cmds))
                    story.append(t)

            elif act_type == 'dot_to_dot':
                total = data.get('total_dots', 10)
                reveal = data.get('reveal', 'a shape')
                story.append(DotToDotFlowable(content_width * 0.6, 6 * cm, total_dots=total, reveal=reveal))

            elif act_type == 'word_search':
                words = data.get('words', [])
                if words:
                    story.append(Paragraph(
                        f'Find these words: <b>{", ".join(words)}</b>',
                        self.styles['Body'],
                    ))
                    story.append(Spacer(1, 2 * mm))
                    story.append(self._build_word_search_grid(words, content_width))

            elif act_type == 'math_problems':
                problems = data.get('problems', [])
                math_color = ACCENT_COLORS.get('math_problems', colors.HexColor('#4ADE80'))
                for idx, p in enumerate(problems):
                    bg = PASTEL_GREEN if idx % 2 == 0 else colors.white
                    story.append(Paragraph(
                        f'<font color="#065F46"><b>{p}</b></font>',
                        ParagraphStyle(
                            f'math_{idx}', parent=self.styles['Body'],
                            fontSize=12, leading=18,
                            backColor=bg, borderPadding=6,
                        ),
                    ))
                    story.append(Spacer(1, 2 * mm))

            elif act_type == 'pattern':
                seq = data.get('sequence', '')
                story.append(Paragraph('Complete the pattern:', self.styles['Body']))
                story.append(Spacer(1, 2 * mm))
                story.append(Paragraph(
                    f'<font size="18" color="#7C3AED">{seq}</font>',
                    ParagraphStyle(
                        'pattern', parent=self.styles['Body'],
                        fontSize=18, alignment=1,
                        backColor=PASTEL_PURPLE, borderPadding=8,
                    ),
                ))

            elif act_type == 'spot_difference':
                scene = data.get('scene', '')
                diffs = data.get('differences', [])
                story.append(Paragraph(f'<i>{scene}</i>', self.styles['Body']))
                story.append(Spacer(1, 2 * mm))
                story.append(DrawingFrameFlowable(content_width, 5 * cm, prompt='Look carefully!'))
                story.append(Spacer(1, 2 * mm))
                story.append(Paragraph(
                    f'Can you find {len(diffs)} differences?',
                    self.styles['Body'],
                ))

            elif act_type == 'odd_one_out':
                items = data.get('items', [])
                reason = data.get('reason', '')
                if items:
                    # Show items in coloured boxes in a row
                    accent = ACCENT_COLORS.get('odd_one_out')
                    table_data = [items]
                    col_w = content_width / max(len(items), 1)
                    t = Table(table_data, colWidths=[col_w] * len(items))
                    style_cmds = [
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 13),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('TEXTCOLOR', (0, 0), (-1, -1), NAVY),
                        ('TOPPADDING', (0, 0), (-1, -1), 12),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                    ]
                    for ci in range(len(items)):
                        style_cmds.append(('BACKGROUND', (ci, 0), (ci, 0),
                                           PASTEL_ORANGE if ci % 2 == 0 else PASTEL_YELLOW))
                        style_cmds.append(('BOX', (ci, 0), (ci, 0), 1.5, accent))
                    t.setStyle(TableStyle(style_cmds))
                    story.append(Paragraph(
                        'Which one does <b>NOT</b> belong? Circle it!',
                        self.styles['Body'],
                    ))
                    story.append(Spacer(1, 3 * mm))
                    story.append(t)
                    story.append(Spacer(1, 3 * mm))
                    story.append(Paragraph(
                        'Why? _______________________________________________',
                        self.styles['Body'],
                    ))

            elif act_type == 'fill_in_blank':
                sentences = data.get('sentences', [])
                accent = ACCENT_COLORS.get('fill_in_blank')
                for idx, sentence in enumerate(sentences):
                    bg = PASTEL_BLUE if idx % 2 == 0 else colors.white
                    # Highlight the blank
                    display = sentence.replace('___', '<u><b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</b></u>')
                    story.append(Paragraph(
                        f'<font color="#0E7490">{idx + 1}. {display}</font>',
                        ParagraphStyle(
                            f'fib_{idx}', parent=self.styles['Body'],
                            fontSize=12, leading=20,
                            backColor=bg, borderPadding=8,
                        ),
                    ))
                    story.append(Spacer(1, 2 * mm))

            elif act_type == 'riddle':
                riddle_text = data.get('riddle', '')
                hint = data.get('hint', '')
                accent = ACCENT_COLORS.get('riddle')
                # Riddle in a purple box
                story.append(Paragraph(
                    f'<font color="#5B21B6" size="13"><b>{riddle_text}</b></font>',
                    ParagraphStyle(
                        'riddle_q', parent=self.styles['Body'],
                        fontSize=13, leading=20, alignment=1,
                        backColor=PASTEL_PURPLE, borderPadding=12,
                    ),
                ))
                story.append(Spacer(1, 3 * mm))
                if hint:
                    story.append(Paragraph(
                        f'<font color="#7C3AED"><i>Hint: {hint}</i></font>',
                        self.styles['Body'],
                    ))
                    story.append(Spacer(1, 2 * mm))
                story.append(Paragraph(
                    'Answer: _______________________________________________',
                    ParagraphStyle(
                        'riddle_a', parent=self.styles['Body'],
                        fontSize=12, leading=18,
                    ),
                ))

            elif act_type == 'scramble':
                words_list = data.get('words', [])
                accent = ACCENT_COLORS.get('scramble')
                story.append(Paragraph(
                    'Unscramble the letters to make a word!',
                    self.styles['Body'],
                ))
                story.append(Spacer(1, 3 * mm))
                for idx, w in enumerate(words_list):
                    scrambled = w.get('scrambled', '')
                    hint = w.get('hint', '')
                    # Letter tiles
                    letters = list(scrambled.upper())
                    table_data = [letters]
                    tile_w = min(content_width / max(len(letters) + 2, 1), 1.0 * cm)
                    t = Table(table_data, colWidths=[tile_w] * len(letters))
                    style_cmds = [
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 16),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
                        ('TOPPADDING', (0, 0), (-1, -1), 8),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ]
                    pink_shades = [colors.HexColor('#EC4899'), colors.HexColor('#F472B6')]
                    for ci in range(len(letters)):
                        style_cmds.append(('BACKGROUND', (ci, 0), (ci, 0), pink_shades[ci % 2]))
                        style_cmds.append(('BOX', (ci, 0), (ci, 0), 1, colors.white))
                    t.setStyle(TableStyle(style_cmds))
                    story.append(t)
                    if hint:
                        story.append(Paragraph(
                            f'<font color="#BE185D"><i>Hint: {hint}</i></font>',
                            self.styles['Body'],
                        ))
                    story.append(Spacer(1, 1 * mm))
                    # Answer line with boxes
                    answer_boxes = ['___'] * len(letters)
                    story.append(Paragraph(
                        f'<font size="14" color="#1a1a1a">&nbsp;&nbsp;{"&nbsp;&nbsp;".join(answer_boxes)}</font>',
                        ParagraphStyle(
                            f'scramble_a_{idx}', parent=self.styles['Body'],
                            fontSize=14, alignment=1,
                        ),
                    ))
                    story.append(Spacer(1, 3 * mm))

            elif act_type == 'true_false':
                questions = data.get('questions', [])
                accent = ACCENT_COLORS.get('true_false')
                for idx, q in enumerate(questions):
                    statement = q.get('statement', '')
                    bg = PASTEL_GREEN if idx % 2 == 0 else colors.white
                    story.append(Paragraph(
                        f'<font color="#134E4A"><b>{idx + 1}. {statement}</b></font>',
                        ParagraphStyle(
                            f'tf_q_{idx}', parent=self.styles['Body'],
                            fontSize=11, leading=16,
                            backColor=bg, borderPadding=8,
                        ),
                    ))
                    # T / F circles to mark
                    tf_data = [['TRUE', '', 'FALSE']]
                    t = Table(tf_data, colWidths=[content_width * 0.3, content_width * 0.4, content_width * 0.3])
                    t.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 11),
                        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                        ('ALIGN', (2, 0), (2, 0), 'CENTER'),
                        ('TEXTCOLOR', (0, 0), (0, 0), colors.HexColor('#059669')),
                        ('TEXTCOLOR', (2, 0), (2, 0), colors.HexColor('#DC2626')),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('TOPPADDING', (0, 0), (-1, -1), 4),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                        ('BOX', (0, 0), (0, 0), 1.5, colors.HexColor('#059669')),
                        ('BOX', (2, 0), (2, 0), 1.5, colors.HexColor('#DC2626')),
                    ]))
                    story.append(t)
                    story.append(Spacer(1, 2 * mm))

            elif act_type == 'sequencing':
                seq_title = data.get('title', 'Put in order')
                steps = data.get('steps', [])
                if steps:
                    # Shuffle steps for the puzzle
                    shuffled = steps[:]
                    random.shuffle(shuffled)
                    accent = ACCENT_COLORS.get('sequencing')
                    story.append(Paragraph(
                        f'<b>Put these steps in the right order:</b> <i>{seq_title}</i>',
                        self.styles['Body'],
                    ))
                    story.append(Spacer(1, 3 * mm))
                    table_data = []
                    for idx, step in enumerate(shuffled):
                        table_data.append(['___', step])
                    t = Table(table_data, colWidths=[content_width * 0.12, content_width * 0.88])
                    style_cmds = [
                        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 11),
                        ('TEXTCOLOR', (0, 0), (0, -1), accent),
                        ('TEXTCOLOR', (1, 0), (1, -1), NAVY),
                        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('TOPPADDING', (0, 0), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ]
                    for row_idx in range(len(table_data)):
                        bg = PASTEL_YELLOW if row_idx % 2 == 0 else colors.white
                        style_cmds.append(('BACKGROUND', (0, row_idx), (-1, row_idx), bg))
                    t.setStyle(TableStyle(style_cmds))
                    story.append(t)

            elif act_type == 'rhyming':
                pairs = data.get('pairs', [])
                accent = ACCENT_COLORS.get('rhyming')
                story.append(Paragraph(
                    'Write a word that <b>rhymes</b> with each word:',
                    self.styles['Body'],
                ))
                story.append(Spacer(1, 3 * mm))
                for idx, pair in enumerate(pairs):
                    word = pair.get('word', '')
                    bg = PASTEL_PINK if idx % 2 == 0 else colors.white
                    story.append(Paragraph(
                        f'<font color="#A21CAF" size="13"><b>{word}</b></font>'
                        f'&nbsp;&nbsp;&nbsp;\u27A1&nbsp;&nbsp;&nbsp;'
                        f'<u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>',
                        ParagraphStyle(
                            f'rhyme_{idx}', parent=self.styles['Body'],
                            fontSize=13, leading=22,
                            backColor=bg, borderPadding=8,
                        ),
                    ))
                    story.append(Spacer(1, 1 * mm))

            elif act_type == 'category_sort':
                categories = data.get('categories', {})
                all_items = data.get('all_items', [])
                accent = ACCENT_COLORS.get('category_sort')
                if all_items and categories:
                    # Shuffled item tiles
                    shuffled_items = all_items[:]
                    random.shuffle(shuffled_items)
                    story.append(Paragraph(
                        'Sort these items into the right groups:',
                        self.styles['Body'],
                    ))
                    story.append(Spacer(1, 3 * mm))
                    # Items as tiles
                    items_row = [shuffled_items]
                    col_w = content_width / max(len(shuffled_items), 1)
                    t = Table(items_row, colWidths=[col_w] * len(shuffled_items))
                    style_cmds = [
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('TEXTCOLOR', (0, 0), (-1, -1), NAVY),
                        ('TOPPADDING', (0, 0), (-1, -1), 8),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ]
                    blues = [PASTEL_BLUE, colors.HexColor('#BFDBFE')]
                    for ci in range(len(shuffled_items)):
                        style_cmds.append(('BACKGROUND', (ci, 0), (ci, 0), blues[ci % 2]))
                        style_cmds.append(('BOX', (ci, 0), (ci, 0), 1, accent))
                    t.setStyle(TableStyle(style_cmds))
                    story.append(t)
                    story.append(Spacer(1, 4 * mm))
                    # Category boxes
                    cat_names = list(categories.keys())
                    cat_data = [cat_names]
                    blank_rows = [['___ ___ ___'] * len(cat_names) for _ in range(2)]
                    cat_data.extend(blank_rows)
                    col_w = content_width / max(len(cat_names), 1)
                    t2 = Table(cat_data, colWidths=[col_w] * len(cat_names))
                    t2.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, 0), 12),
                        ('FONTSIZE', (0, 1), (-1, -1), 10),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#9CA3AF')),
                        ('BACKGROUND', (0, 0), (-1, 0), accent),
                        ('TOPPADDING', (0, 0), (-1, -1), 8),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                        ('BOX', (0, 0), (-1, -1), 1, accent),
                        ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER),
                    ]))
                    story.append(t2)

            elif act_type == 'crossword_clues':
                clues = data.get('clues', [])
                accent = ACCENT_COLORS.get('crossword_clues')
                for idx, clue_item in enumerate(clues):
                    clue_text = clue_item.get('clue', '')
                    answer = clue_item.get('answer', '')
                    length = clue_item.get('length', len(answer))
                    bg = PASTEL_BLUE if idx % 2 == 0 else colors.white
                    story.append(Paragraph(
                        f'<font color="#0369A1"><b>{idx + 1}. {clue_text}</b></font>'
                        f'&nbsp;&nbsp;({length} letters)',
                        ParagraphStyle(
                            f'cw_{idx}', parent=self.styles['Body'],
                            fontSize=11, leading=16,
                            backColor=bg, borderPadding=6,
                        ),
                    ))
                    # Letter boxes
                    boxes = [''] * length
                    t = Table([boxes], colWidths=[0.7 * cm] * length, rowHeights=[0.7 * cm])
                    t.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 12),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('BOX', (0, 0), (-1, -1), 1.5, accent),
                        ('INNERGRID', (0, 0), (-1, -1), 1, colors.HexColor('#93C5FD')),
                    ]))
                    story.append(Spacer(1, 1 * mm))
                    story.append(t)
                    story.append(Spacer(1, 3 * mm))

            else:
                # Unknown type — render as text
                story.append(Paragraph(str(data), self.styles['Body']))

            story.append(Spacer(1, 3 * mm))

        # ── Footer ───────────────────────────────────────────────
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph(
            '<font color="#C2855A">\u2605</font> Generated by <b>Dayo</b> · '
            'AI-generated content. Activities are suggestions only. '
            '<font color="#C2855A">\u2605</font>',
            self.styles['Footer'],
        ))

        doc.build(story)
        return filepath

    def _build_word_search_grid(self, words, content_width):
        """Build a word search grid with collision-safe horizontal + vertical placement."""
        import string
        grid_size = max(8, max(len(w) for w in words) + 2) if words else 8
        grid_size = min(grid_size, 12)

        # None means unfilled — we'll backfill with random letters later
        grid = [[None] * grid_size for _ in range(grid_size)]

        def can_place(word, row, col, direction):
            """Check if word fits without conflicting with existing letters."""
            for k, ch in enumerate(word):
                r = row + (k if direction == 'vertical' else 0)
                c = col + (k if direction == 'horizontal' else 0)
                if r >= grid_size or c >= grid_size:
                    return False
                if grid[r][c] is not None and grid[r][c] != ch:
                    return False
            return True

        def place_word(word, row, col, direction):
            for k, ch in enumerate(word):
                r = row + (k if direction == 'vertical' else 0)
                c = col + (k if direction == 'horizontal' else 0)
                grid[r][c] = ch

        # Try to place each word with collision detection
        for word in words[:6]:
            word = word.upper()
            if len(word) > grid_size:
                continue
            placed = False
            # Try both directions, randomised positions, up to 40 attempts
            for _ in range(40):
                direction = random.choice(['horizontal', 'vertical'])
                if direction == 'horizontal':
                    row = random.randint(0, grid_size - 1)
                    col = random.randint(0, grid_size - len(word))
                else:
                    row = random.randint(0, grid_size - len(word))
                    col = random.randint(0, grid_size - 1)
                if can_place(word, row, col, direction):
                    place_word(word, row, col, direction)
                    placed = True
                    break
            # Fallback: force horizontal if random attempts fail
            if not placed:
                for row in range(grid_size):
                    for col in range(grid_size - len(word) + 1):
                        if can_place(word, row, col, 'horizontal'):
                            place_word(word, row, col, 'horizontal')
                            placed = True
                            break
                    if placed:
                        break

        # Fill empty cells with random letters
        for r in range(grid_size):
            for c_idx in range(grid_size):
                if grid[r][c_idx] is None:
                    grid[r][c_idx] = random.choice(string.ascii_uppercase)

        cell_size = min(content_width / grid_size, 0.8 * cm)
        t = Table(grid, colWidths=[cell_size] * grid_size, rowHeights=[cell_size] * grid_size)

        # Colourful checkerboard background
        ws_accent = ACCENT_COLORS.get('word_search', colors.HexColor('#818CF8'))
        style_cmds = [
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#C7D2FE')),
            ('TEXTCOLOR', (0, 0), (-1, -1), NAVY),
        ]
        for r in range(grid_size):
            for c_idx in range(grid_size):
                if (r + c_idx) % 2 == 0:
                    style_cmds.append(('BACKGROUND', (c_idx, r), (c_idx, r), PASTEL_PURPLE))
        t.setStyle(TableStyle(style_cmds))
        return t
