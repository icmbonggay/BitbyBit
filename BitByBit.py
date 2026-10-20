"""Bit by Bit: a small, good looking habit tracker built with tkinter.

Run it with:  python3 BitByBit.py
Your habits are saved next to this file in habits.json.
"""

import json
import math
import re
import shutil
import sys
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog
from tkinter import font as tkfont
from tkinter import messagebox

try:  # Pillow is optional. Without it, only PNG and GIF pictures can be used.
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

DATA_FILE = Path(__file__).with_name("habits.json")
ICON_DIR = Path(__file__).with_name("icons")  # uploaded pictures are kept here
MAX_NAME_LENGTH = 28
ICON_PIXELS = 28  # size of an uploaded picture inside its chip

# ---------------------------------------------------------------------------
# Look and feel
# ---------------------------------------------------------------------------

# Colours follow Apple's system palette (iOS and macOS "grouped" look).
THEMES = {
    "dark": {
        "bg": "#000000", "card": "#1C1C1E", "card_hover": "#2C2C2E",
        "border": "#38383A", "text": "#FFFFFF", "muted": "#8E8E93",
        "track": "#3A3A3C", "accent": "#0A84FF", "success": "#30D158",
        "danger": "#FF453A", "on_accent": "#FFFFFF",
    },
    "light": {
        "bg": "#F2F2F7", "card": "#FFFFFF", "card_hover": "#F5F5FA",
        "border": "#E5E5EA", "text": "#000000", "muted": "#8E8E93",
        "track": "#E5E5EA", "accent": "#007AFF", "success": "#34C759",
        "danger": "#FF3B30", "on_accent": "#FFFFFF",
    },
}

# Every habit gets its own colour (a bit brighter in dark mode, like iOS).
HABIT_COLORS = {
    "light": ["#007AFF", "#FF9500", "#34C759", "#FF2D55",
              "#AF52DE", "#32ADE6", "#FF3B30", "#5856D6"],
    "dark": ["#0A84FF", "#FF9F0A", "#30D158", "#FF375F",
             "#BF5AF2", "#64D2FF", "#FF453A", "#5E5CE6"],
}
COLOR_COUNT = 8

FLAME_OUTER = "#FF9500"
FLAME_INNER = "#FFCC00"

FONT_CHOICES = [".AppleSystemUIFont", "SF Pro Text", "Helvetica Neue", "Segoe UI", "Inter",
                "Helvetica", "DejaVu Sans", "Arial"]


def rounded_rect(canvas, x1, y1, x2, y2, r, **options):
    """Draw a rounded rectangle on a canvas (tkinter has no built in one).

    The corners are real quarter circles, so r is the true corner radius.
    """
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    points = []
    # each corner: (centre x, centre y, start angle in degrees)
    for corner_x, corner_y, start in ((x2 - r, y1 + r, -90), (x2 - r, y2 - r, 0),
                                      (x1 + r, y2 - r, 90), (x1 + r, y1 + r, 180)):
        for step in range(11):
            angle = math.radians(start + step * 9)
            points += [corner_x + r * math.cos(angle),
                       corner_y + r * math.sin(angle)]
    return canvas.create_polygon(points, **options)


def draw_flame(canvas, cx, cy, size, lit=True, theme=None, tags=()):
    """A little flame drawn from polygons, so no emoji fonts are needed."""
    outer = [(0.05, -1.0), (0.38, -0.5), (0.68, 0.12), (0.52, 0.78),
             (0.0, 1.0), (-0.52, 0.78), (-0.66, 0.12), (-0.3, -0.2),
             (-0.14, -0.62)]
    inner = [(0.04, -0.2), (0.3, 0.2), (0.34, 0.62), (0.0, 0.85),
             (-0.34, 0.62), (-0.28, 0.2)]

    def flat(points, scale=1.0, dy=0.0):
        out = []
        for x, y in points:
            out += [cx + x * size * scale, cy + (y * scale + dy) * size]
        return out

    if lit:
        outer_color, inner_color = FLAME_OUTER, FLAME_INNER
    else:
        outer_color, inner_color = theme["track"], theme["border"]
    canvas.create_polygon(flat(outer), smooth=True, fill=outer_color,
                          outline=outer_color, tags=tags)
    canvas.create_polygon(flat(inner, 0.8, 0.12), smooth=True,
                          fill=inner_color, outline=inner_color, tags=tags)


def fit_text(text, font, max_pixels):
    """Shorten text with '...' so it fits in max_pixels."""
    if font.measure(text) <= max_pixels:
        return text
    while text and font.measure(text + "...") > max_pixels:
        text = text[:-1]
    return text + "..."


def mix(color_a, color_b, amount):
    """Blend two #RRGGBB colours. amount=0 gives color_a, 1 gives color_b."""
    a = [int(color_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(color_b[i:i + 2], 16) for i in (1, 3, 5)]
    blended = [round(x * (1 - amount) + y * amount) for x, y in zip(a, b)]
    return "#%02x%02x%02x" % tuple(blended)


# ---------------------------------------------------------------------------
# Icons
#
# A habit's icon is stored as text:
#   None            -> the first letter of the habit name (the default)
#   "builtin:star"  -> one of the drawn icons in BUILTIN_ICONS below
#   "file:run.png"  -> a picture you uploaded, kept in the icons folder
# ---------------------------------------------------------------------------

BUILTIN_ICONS = ["star", "heart", "book", "dumbbell", "drop", "moon", "sun",
                 "bolt", "leaf", "code", "coffee", "music", "target", "clock"]


def draw_builtin_icon(canvas, key, cx, cy, size, color, bg, tags=()):
    """Draw one of the built in icons. Shapes are described on a -1..1 grid."""
    stroke = max(2, size / 6)

    def pts(coords):
        return [value for x, y in coords
                for value in (cx + x * size, cy + y * size)]

    def line(*coords, fill=color, width=stroke):
        canvas.create_line(pts(coords), fill=fill, width=width,
                           capstyle="round", joinstyle="round", tags=tags)

    def poly(coords, smooth=False):
        canvas.create_polygon(pts(coords), fill=color, outline=color,
                              smooth=smooth, tags=tags)

    def oval(x1, y1, x2, y2, fill=color, outline="", width=stroke):
        canvas.create_oval(cx + x1 * size, cy + y1 * size,
                           cx + x2 * size, cy + y2 * size,
                           fill=fill, outline=outline, width=width, tags=tags)

    if key == "star":
        poly([(math.cos(-math.pi / 2 + i * math.pi / 5) * (1 if i % 2 == 0 else 0.45),
               math.sin(-math.pi / 2 + i * math.pi / 5) * (1 if i % 2 == 0 else 0.45))
              for i in range(10)])
    elif key == "heart":
        points = []
        for i in range(48):
            a = i * 2 * math.pi / 48
            points.append((math.sin(a) ** 3,
                           -(13 * math.cos(a) - 5 * math.cos(2 * a)
                             - 2 * math.cos(3 * a) - math.cos(4 * a)) / 16 + 0.08))
        poly(points)
    elif key == "book":
        poly([(-0.95, -0.6), (-0.07, -0.42), (-0.07, 0.8), (-0.95, 0.62)])
        poly([(0.95, -0.6), (0.07, -0.42), (0.07, 0.8), (0.95, 0.62)])
    elif key == "dumbbell":
        line((-0.55, 0), (0.55, 0))
        poly([(-0.8, -0.55), (-0.55, -0.55), (-0.55, 0.55), (-0.8, 0.55)])
        poly([(0.8, -0.55), (0.55, -0.55), (0.55, 0.55), (0.8, 0.55)])
        poly([(-1, -0.3), (-0.8, -0.3), (-0.8, 0.3), (-1, 0.3)])
        poly([(1, -0.3), (0.8, -0.3), (0.8, 0.3), (1, 0.3)])
    elif key == "drop":
        poly([(0, -1), (0.5, -0.05), (0.66, 0.4), (0, 1), (-0.66, 0.4),
              (-0.5, -0.05)], smooth=True)
    elif key == "moon":
        oval(-0.9, -0.9, 0.9, 0.9)
        oval(-0.3, -1.05, 1.2, 0.45, fill=bg)
    elif key == "sun":
        oval(-0.4, -0.4, 0.4, 0.4)
        for i in range(8):
            a = i * math.pi / 4
            line((math.cos(a) * 0.68, math.sin(a) * 0.68),
                 (math.cos(a) * 0.98, math.sin(a) * 0.98))
    elif key == "bolt":
        poly([(0.2, -1), (-0.6, 0.15), (-0.05, 0.15), (-0.25, 1),
              (0.6, -0.2), (0.05, -0.2)])
    elif key == "leaf":
        poly([(-0.8, 0.8), (-0.78, 0.0), (-0.2, -0.62), (0.88, -0.88),
              (0.72, 0.05), (0.1, 0.7)], smooth=True)
        line((-0.8, 0.8), (0.35, -0.4), fill=bg, width=max(1.5, size / 9))
    elif key == "code":
        line((-0.4, -0.6), (-0.95, 0), (-0.4, 0.6))
        line((0.4, -0.6), (0.95, 0), (0.4, 0.6))
        line((0.14, -0.8), (-0.14, 0.8))
    elif key == "coffee":
        poly([(-0.8, -0.15), (0.4, -0.15), (0.4, 0.4), (0.1, 0.85),
              (-0.5, 0.85), (-0.8, 0.4)])
        oval(0.2, 0.0, 0.95, 0.55, fill="", outline=color)
        line((-0.45, -0.9), (-0.45, -0.5))
        line((0.0, -0.9), (0.0, -0.5))
    elif key == "music":
        oval(-0.8, 0.2, -0.15, 0.85)
        line((-0.2, 0.55), (-0.2, -0.85))
        poly([(-0.2, -0.85), (0.85, -0.55), (0.85, -0.15), (-0.2, -0.45)])
    elif key == "target":
        oval(-0.95, -0.95, 0.95, 0.95, fill="", outline=color)
        oval(-0.5, -0.5, 0.5, 0.5, fill="", outline=color)
        oval(-0.12, -0.12, 0.12, 0.12)
    elif key == "clock":
        oval(-0.92, -0.92, 0.92, 0.92, fill="", outline=color)
        line((0, 0), (0, -0.55))
        line((0, 0), (0.4, 0.22))


def draw_icon_chip(canvas, app, icon, name, cx, cy, size, accent, tags=()):
    """Draw a habit's icon like an app icon: a coloured square with a white glyph."""
    half = size / 2
    radius = size * 0.30
    kind, _, value = (icon or "").partition(":")
    image = app.get_icon_image(value) if kind == "file" else None

    # pictures sit on a soft tint so see-through PNGs still look right
    fill = mix(accent, "#FFFFFF", 0.82) if image is not None else accent
    rounded_rect(canvas, cx - half, cy - half, cx + half, cy + half, radius,
                 fill=fill, outline="", tags=tags)
    if image is not None:
        canvas.create_image(cx, cy, image=image, tags=tags)
    elif kind == "builtin" and value in BUILTIN_ICONS:
        draw_builtin_icon(canvas, value, cx, cy, size * 0.27, "#FFFFFF",
                          accent, tags)
    else:
        letter = (name.strip()[:1] or "?").upper()
        canvas.create_text(cx, cy, text=letter, fill="#FFFFFF", tags=tags,
                           font=app.fonts["chip"])


def import_icon_image(source):
    """Copy a picture into the icons folder and return the stored file name."""
    source = Path(source)
    extension = source.suffix.lower()
    if Image is None and extension not in (".png", ".gif"):
        raise ValueError("Only PNG and GIF pictures work right now "
                         "(install Pillow for more types).")
    ICON_DIR.mkdir(exist_ok=True)
    stem = re.sub(r"[^a-z0-9]+", "-", source.stem.lower()).strip("-") or "icon"
    final_extension = ".png" if Image is not None else extension

    target, number = ICON_DIR / f"{stem}{final_extension}", 2
    while target.exists():
        target = ICON_DIR / f"{stem}-{number}{final_extension}"
        number += 1

    if Image is not None:
        try:
            picture = Image.open(source).convert("RGBA")
        except Exception:
            raise ValueError("That file could not be read as a picture.")
        picture.thumbnail((96, 96))  # keeps the icons folder small
        picture.save(target)
    else:
        shutil.copyfile(source, target)
    return target.name


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class Habit:
    def __init__(self, name, last_logged_date=None, streak=0,
                 history=None, color=0, best_streak=None, icon=None):
        self.name = name
        self.icon = icon  # see the Icons section above
        self.last_logged_date = last_logged_date
        self.streak = streak
        self.best_streak = max(streak, best_streak or 0)
        self.history = set(history or [])  # every day this habit was logged
        self.color = color
        if last_logged_date:
            self.history.add(last_logged_date)

    def log_streak(self):
        today = date.today()
        if self.last_logged_date is None:
            self.streak = 1
        else:
            difference = (today - self.last_logged_date).days
            if difference == 0:
                return "You've already logged this streak."
            if difference < 0:
                return "Error in logging your streak."
            if difference == 1:
                self.streak += 1
            else:
                self.reset_streak()
                self.streak += 1

        self.last_logged_date = today
        self.history.add(today)
        self.best_streak = max(self.best_streak, self.streak)
        return self.streak

    def undo_log(self):
        """Take back today's log, e.g. if you tapped the check by accident."""
        today = date.today()
        if not self.done_today():
            return
        old_streak = self.streak
        self.history.discard(today)
        self.streak = max(0, old_streak - 1)
        self.last_logged_date = max(self.history) if self.history else None
        if self.best_streak == old_streak:
            # the log we just undid set the record, so work it out again
            self.best_streak = max(self.streak, self.best_streak_from_history())

    def best_streak_from_history(self):
        best = run = 0
        previous = None
        for day in sorted(self.history):
            run = run + 1 if previous and (day - previous).days == 1 else 1
            best = max(best, run)
            previous = day
        return best

    def reset_streak(self):
        self.streak = 0

    def done_today(self):
        return self.last_logged_date == date.today()

    def current_streak(self):
        """The streak you would see today. It is 0 once you miss a day."""
        if self.last_logged_date is None:
            return 0
        if (date.today() - self.last_logged_date).days > 1:
            return 0
        return self.streak

    def display_streak(self):
        return f"Current streak for {self.name}: {self.current_streak()}"

    def to_dict(self):
        return {
            "name": self.name,
            "streak": self.streak,
            "best_streak": self.best_streak,
            "last_logged_date": (self.last_logged_date.isoformat()
                                 if self.last_logged_date else None),
            "history": sorted(day.isoformat() for day in self.history),
            "color": self.color,
            "icon": self.icon,
        }

    @classmethod
    def from_dict(cls, data):
        last = data.get("last_logged_date")
        return cls(
            data["name"],
            date.fromisoformat(last) if last else None,
            data.get("streak", 0),
            [date.fromisoformat(day) for day in data.get("history", [])],
            data.get("color", 0),
            data.get("best_streak"),
            data.get("icon"),
        )


class HabitTracker:
    def __init__(self):
        self.habits = []
        self.theme = "dark"

    def add_habit(self, name, date=None, streak=0, icon=None):
        name = name.strip()
        if not name:
            return "Please type a habit name first."
        if len(name) > MAX_NAME_LENGTH:
            return f"Keep it under {MAX_NAME_LENGTH} characters."
        for habit in self.habits:
            if habit.name.lower() == name.lower():
                return f"Habit '{name}' already exists."
        color = len(self.habits) % COLOR_COUNT
        self.habits.append(Habit(name, date, streak, color=color, icon=icon))
        return f"Habit '{name}' added successfully."

    def remove_habit(self, name):
        for habit in self.habits:
            if habit.name == name:
                self.habits.remove(habit)
                return f"Habit '{name}' removed successfully."
        return "Habit not found."

    def display_habits(self):
        return ", ".join(habit.name for habit in self.habits)

    def done_today_count(self):
        return sum(1 for habit in self.habits if habit.done_today())

    def top_streak(self):
        return max((habit.current_streak() for habit in self.habits), default=0)

    # -- saving and loading -------------------------------------------------

    def save(self):
        payload = {"theme": self.theme,
                   "habits": [habit.to_dict() for habit in self.habits]}
        try:
            DATA_FILE.write_text(json.dumps(payload, indent=2))
        except OSError:
            pass  # not being able to save should never crash the app

    def load(self):
        try:
            payload = json.loads(DATA_FILE.read_text())
            self.habits = [Habit.from_dict(item) for item in payload["habits"]]
            self.theme = payload.get("theme", "dark")
        except (OSError, ValueError, KeyError, TypeError):
            self.habits = []  # first run, or the file was unreadable


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

class Header(tk.Canvas):
    """Small date, a large title, and the light/dark switch."""

    def __init__(self, parent, app):
        super().__init__(parent, height=62, bg=app.t["bg"],
                         highlightthickness=0, bd=0)
        self.app = app
        self.bind("<Configure>", lambda e: self.draw())
        self.tag_bind("theme", "<Button-1>", lambda e: app.toggle_theme())
        self.tag_bind("theme", "<Enter>", lambda e: self.config(cursor="hand2"))
        self.tag_bind("theme", "<Leave>", lambda e: self.config(cursor=""))

    def draw(self):
        t, f = self.app.t, self.app.fonts
        w = self.winfo_width()
        self.delete("all")
        today = date.today()
        self.create_text(2, 8, text=f"{today:%A, %B} {today.day}".upper(),
                         anchor="w", font=f["label"], fill=t["muted"])
        self.create_text(0, 37, text="Habits", anchor="w", font=f["title"],
                         fill=t["text"])

        # theme switch: a circle that is half filled
        cx, cy = w - 14, 37
        self.create_oval(cx - 14, cy - 14, cx + 14, cy + 14, fill=t["card"],
                         outline="", tags="theme")
        self.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, outline=t["muted"],
                         width=1.5, tags="theme")
        self.create_arc(cx - 6, cy - 6, cx + 6, cy + 6, start=90, extent=180,
                        fill=t["muted"], outline=t["muted"], width=1.5,
                        tags="theme")


class StatsCard(tk.Canvas):
    """A progress ring for today and the best running streak."""

    def __init__(self, parent, app):
        super().__init__(parent, height=80, bg=app.t["bg"],
                         highlightthickness=0, bd=0)
        self.app = app
        self.bind("<Configure>", lambda e: self.draw())

    def draw(self):
        app, t, f = self.app, self.app.t, self.app.fonts
        tracker = app.tracker
        w, h = self.winfo_width(), self.winfo_height()
        self.delete("all")
        rounded_rect(self, 0, 0, w, h, 18, fill=t["card"], outline="")

        total = len(tracker.habits)
        done = tracker.done_today_count()
        all_done = total > 0 and done == total

        # progress ring
        cx, cy, r = 44, h / 2, 20
        self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=t["track"],
                         width=5)
        if total and done:
            color = t["success"] if all_done else t["accent"]
            if all_done:
                self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color,
                                 width=5)
            else:
                self.create_arc(cx - r, cy - r, cx + r, cy + r, start=90,
                                extent=-360 * done / total, style="arc",
                                outline=color, width=5)
        self.create_text(cx, cy, text=f"{done}/{total}" if total else "-",
                         font=f["stat_s"], fill=t["text"])

        if not total:
            subtitle = "Add a habit to get started"
        elif all_done:
            subtitle = "All done. Nice work!"
        else:
            subtitle = f"{done} of {total} completed"
        self.create_text(82, h / 2 - 9, text="Today", anchor="w",
                         font=f["row_b"], fill=t["text"])
        self.create_text(82, h / 2 + 10, text=subtitle, anchor="w",
                         font=f["sub"], fill=t["muted"])

        # best current streak, kept well away from the right edge
        top = tracker.top_streak()
        gx = w - 56  # centre of the little group
        draw_flame(self, gx - 12, h / 2 - 7, 7, lit=top > 0, theme=t)
        self.create_text(gx - 2, h / 2 - 7, text=str(top), anchor="w",
                         font=f["stat"], fill=t["text"] if top else t["muted"])
        self.create_text(gx, h / 2 + 15, text="top streak", anchor="center",
                         font=f["tiny"], fill=t["muted"])


class AddBar(tk.Canvas):
    """A plain text field with an icon button and an Add button."""

    PLACEHOLDER = "New habit"

    def __init__(self, parent, app):
        super().__init__(parent, height=44, bg=app.t["bg"],
                         highlightthickness=0, bd=0)
        self.app = app
        t = app.t
        self.icon = None  # icon chosen for the habit that is about to be added
        self.showing_placeholder = True
        self.entry = tk.Entry(self, relief="flat", bd=0, highlightthickness=0,
                              bg=t["card"], fg=t["muted"],
                              insertbackground=t["accent"],
                              font=app.fonts["body_l"])
        self.entry.insert(0, self.PLACEHOLDER)
        self.entry.bind("<FocusIn>", self.on_focus_in)
        self.entry.bind("<FocusOut>", self.on_focus_out)
        self.entry.bind("<Return>", lambda e: self.submit())
        self.entry_window = self.create_window(50, 22, window=self.entry,
                                               anchor="w")
        self.bind("<Configure>", lambda e: self.draw())
        for tag, action in (("add", lambda e: self.submit()),
                            ("icon", lambda e: self.pick_icon())):
            self.tag_bind(tag, "<Button-1>", action)
            self.tag_bind(tag, "<Enter>", lambda e: self.config(cursor="hand2"))
            self.tag_bind(tag, "<Leave>", lambda e: self.config(cursor=""))

    def next_color(self):
        return self.app.habit_color(len(self.app.tracker.habits))

    def typed_name(self):
        return "" if self.showing_placeholder else self.entry.get()

    def pick_icon(self):
        def chosen(icon):
            self.icon = icon
            self.draw()
            self.entry.focus_set()
        IconPicker(self.app, self.icon, self.typed_name() or "New habit",
                   self.next_color(), chosen)

    def on_focus_in(self, _event):
        if self.showing_placeholder:
            self.entry.delete(0, "end")
            self.entry.config(fg=self.app.t["text"])
            self.showing_placeholder = False

    def on_focus_out(self, _event):
        if not self.entry.get().strip():
            self.entry.delete(0, "end")
            self.entry.insert(0, self.PLACEHOLDER)
            self.entry.config(fg=self.app.t["muted"])
            self.showing_placeholder = True

    def submit(self):
        added = self.app.add_habit(self.typed_name(), self.icon)
        if added:
            self.entry.delete(0, "end")
            self.icon = None  # the next habit starts with the default icon
            self.draw()
        self.entry.focus_set()

    def draw(self):
        t = self.app.t
        w, h = self.winfo_width(), self.winfo_height()
        self.delete("shape")
        rounded_rect(self, 0, 0, w, h, 22, fill=t["card"], outline="",
                     tags="shape")
        # icon button: shows the chosen icon, or a faded star as a hint
        if self.icon:
            draw_icon_chip(self, self.app, self.icon, self.typed_name(), 26,
                           h / 2, 26, self.next_color(), ("shape", "icon"))
        else:
            rounded_rect(self, 13, h / 2 - 13, 39, h / 2 + 13, 8,
                         fill=t["track"], outline="", tags=("shape", "icon"))
            draw_builtin_icon(self, "star", 26, h / 2, 7, t["muted"],
                              t["track"], ("shape", "icon"))
        # text button
        self.create_rectangle(w - 70, 0, w - 22, h, fill=t["card"], outline="",
                              tags=("shape", "add"))
        self.create_text(w - 40, h / 2, text="Add", font=self.app.fonts["button"],
                         fill=t["accent"], tags=("shape", "add"))
        self.itemconfigure(self.entry_window, width=max(50, w - 50 - 74))
        self.tag_lower("shape")


class HabitCard(tk.Canvas):
    """One row of the habit list: check circle, icon, name, streak, last 7 days.

    Rows sit directly on top of each other like a grouped list. position says
    whether the row is the "first", "middle", "last" or "single" one, so only
    the outer corners of the group are rounded.
    """

    HEIGHT = 58

    def __init__(self, parent, app, habit, position="single"):
        super().__init__(parent, height=self.HEIGHT, bg=app.t["bg"],
                         highlightthickness=0, bd=0)
        self.app = app
        self.habit = habit
        self.position = position
        self.hover = False
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Enter>", lambda e: self.set_hover(True))
        self.bind("<Leave>", lambda e: self.set_hover(False))
        for tag, action in (("check", lambda e: app.toggle_habit(habit)),
                            ("icon", lambda e: app.choose_icon_for(habit)),
                            ("delete", lambda e: app.delete_habit(habit))):
            self.tag_bind(tag, "<Button-1>", action)
            self.tag_bind(tag, "<Enter>", lambda e: self.config(cursor="hand2"))
            self.tag_bind(tag, "<Leave>", lambda e: self.config(cursor=""))

    def set_hover(self, value):
        self.hover = value
        self.draw()

    def draw(self):
        app, t, f, habit = self.app, self.app.t, self.app.fonts, self.habit
        w, h = self.winfo_width(), self.winfo_height()
        accent = app.habit_color(habit.color)
        done = habit.done_today()
        first = self.position in ("first", "single")
        last = self.position in ("last", "single")
        cy = h / 2
        self.delete("all")

        # Draw a rounded rectangle that is taller than the row, so the parts
        # that should stay square are cut off by the edge of the canvas.
        rounded_rect(self, -1, 0 if first else -30, w + 1,
                     h if last else h + 30, 18,
                     fill=t["card_hover"] if self.hover else t["card"],
                     outline="")
        if not last:
            self.create_line(88, h - 1, w - 16, h - 1, fill=t["border"])

        # check circle (click to log today, click again to undo)
        cx = 30
        if done:
            self.create_oval(cx - 10, cy - 10, cx + 10, cy + 10, fill=accent,
                             outline=accent, tags="check")
            self.create_line(cx - 4, cy + 0.5, cx - 1, cy + 3.5, cx + 4.5,
                             cy - 3.5, fill="white", width=2, capstyle="round",
                             joinstyle="round", tags="check")
        else:
            self.create_oval(cx - 10, cy - 10, cx + 10, cy + 10, fill=t["card"],
                             outline=accent, width=1.5, tags="check")

        # icon (click it to change it)
        draw_icon_chip(self, app, habit.icon, habit.name, 62, cy, 30, accent,
                       "icon")

        # name
        streak = habit.current_streak()
        name_space = w - 88 - 110
        self.create_text(88, cy - 9, anchor="w", font=f["row"], fill=t["text"],
                         text=fit_text(habit.name, f["row"], name_space))

        # streak line under the name
        if streak > 0:
            draw_flame(self, 92, cy + 9, 4, lit=True, theme=t)
            text, x = f"{streak} day streak", 101
            if habit.best_streak > streak:
                text += f"  \u00b7  Best {habit.best_streak}"
        else:
            text, x = (f"Best {habit.best_streak}" if habit.best_streak
                       else "Not started yet"), 88
        self.create_text(x, cy + 9, text=text, anchor="w", font=f["sub"],
                         fill=t["muted"])

        # last 7 days, as small dots on the right
        today = date.today()
        for i in range(7):
            day = today - timedelta(days=6 - i)
            x = w - 94 + i * 10
            self.create_oval(x - 2.5, cy - 2.5, x + 2.5, cy + 2.5,
                             fill=accent if day in habit.history else t["track"],
                             outline="")

        # delete button, only while hovering
        if self.hover:
            dx = w - 18
            self.create_oval(dx - 8, cy - 8, dx + 8, cy + 8, fill=t["track"],
                             outline="", tags="delete")
            self.create_line(dx - 3, cy - 3, dx + 3, cy + 3,
                             fill=t["danger"], width=1.5, capstyle="round",
                             tags="delete")
            self.create_line(dx - 3, cy + 3, dx + 3, cy - 3,
                             fill=t["danger"], width=1.5, capstyle="round",
                             tags="delete")


class IconPicker(tk.Toplevel):
    """A small window with every icon to choose from, plus an upload tile."""

    COLUMNS = 4
    CELL = 66
    GAP = 8

    def __init__(self, app, current, name, accent, on_pick):
        super().__init__(app.root)
        self.app, self.current, self.name = app, current, name
        self.accent, self.on_pick = accent, on_pick
        t = app.t

        self.title("Choose an icon")
        self.configure(bg=t["bg"])
        self.resizable(False, False)
        self.transient(app.root)
        self.bind("<Escape>", lambda e: self.destroy())

        # the options: default letter, drawn icons, the current picture (if
        # any), and finally the upload tile
        self.options = [None] + [f"builtin:{key}" for key in BUILTIN_ICONS]
        if current and current.startswith("file:"):
            self.options.append(current)
        self.options.append("upload")

        rows = math.ceil(len(self.options) / self.COLUMNS)
        width = self.COLUMNS * self.CELL + (self.COLUMNS + 1) * self.GAP
        height = rows * self.CELL + (rows + 1) * self.GAP

        tk.Label(self, text="Choose an icon", bg=t["bg"], fg=t["text"],
                 font=app.fonts["row_b"]).pack(anchor="w", padx=20,
                                               pady=(18, 0))
        tk.Label(self, text="Pick one, or upload your own picture.",
                 bg=t["bg"], fg=t["muted"], font=app.fonts["sub"]
                 ).pack(anchor="w", padx=20, pady=(2, 8))
        self.grid_canvas = tk.Canvas(self, width=width, height=height,
                                     bg=t["card"], highlightthickness=0, bd=0)
        self.grid_canvas.pack(padx=20)
        self.status = tk.Label(self, text="", bg=t["bg"], fg=t["danger"],
                               font=app.fonts["sub"], wraplength=width - 20)
        self.status.pack(pady=(6, 14))

        self.grid_canvas.bind("<Button-1>", self.on_click)
        self.grid_canvas.bind("<Motion>", self.on_motion)
        self.hovered = None
        self.draw()
        self.place_next_to(app.root)
        self.grab_set()

    def place_next_to(self, root):
        self.update_idletasks()
        x = root.winfo_rootx() + (root.winfo_width() - self.winfo_width()) // 2
        y = root.winfo_rooty() + 90
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def cell_box(self, index):
        row, column = divmod(index, self.COLUMNS)
        x = self.GAP + column * (self.CELL + self.GAP)
        y = self.GAP + row * (self.CELL + self.GAP)
        return x, y, x + self.CELL, y + self.CELL

    def index_at(self, x, y):
        for index in range(len(self.options)):
            x1, y1, x2, y2 = self.cell_box(index)
            if x1 <= x <= x2 and y1 <= y <= y2:
                return index
        return None

    def draw(self):
        t, f, canvas = self.app.t, self.app.fonts, self.grid_canvas
        canvas.delete("all")
        for index, option in enumerate(self.options):
            x1, y1, x2, y2 = self.cell_box(index)
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            if index == self.hovered:
                rounded_rect(canvas, x1, y1, x2, y2, 18, fill=t["card_hover"],
                             outline="")
            if option == "upload":
                rounded_rect(canvas, cx - 22, cy - 28, cx + 22, cy + 16, 14,
                             fill=t["track"], outline="")
                canvas.create_line(cx - 7, cy - 12, cx + 7, cy - 12,
                                   fill=t["muted"], width=2, capstyle="round")
                canvas.create_line(cx, cy - 19, cx, cy - 5, fill=t["muted"],
                                   width=2, capstyle="round")
                canvas.create_text(cx, cy + 26, text="Upload", font=f["tiny"],
                                   fill=t["muted"])
                continue
            if option == self.current:
                rounded_rect(canvas, cx - 27, cy - 27, cx + 27, cy + 27, 18,
                             fill="", outline=t["accent"], width=3)
            draw_icon_chip(canvas, self.app, option, self.name, cx, cy, 44,
                           self.accent)

    def on_motion(self, event):
        index = self.index_at(event.x, event.y)
        if index != self.hovered:
            self.hovered = index
            self.grid_canvas.config(cursor="hand2" if index is not None else "")
            self.draw()

    def on_click(self, event):
        index = self.index_at(event.x, event.y)
        if index is None:
            return
        option = self.options[index]
        if option == "upload":
            self.upload()
        else:
            self.choose(option)

    def choose(self, option):
        self.grab_release()
        self.destroy()
        self.on_pick(option)

    def upload(self):
        types = "*.png *.gif"
        if Image is not None:
            types += " *.jpg *.jpeg *.bmp *.webp"
        path = filedialog.askopenfilename(
            parent=self, title="Choose a picture",
            filetypes=[("Pictures", types), ("All files", "*.*")])
        if not path:
            return
        try:
            self.choose(self.app.import_icon(path))
        except ValueError as problem:
            self.status.config(text=str(problem))


class EmptyState(tk.Canvas):
    def __init__(self, parent, app):
        super().__init__(parent, height=220, bg=app.t["bg"],
                         highlightthickness=0, bd=0)
        self.app = app
        self.bind("<Configure>", lambda e: self.draw())

    def draw(self):
        t, f = self.app.t, self.app.fonts
        w = self.winfo_width()
        self.delete("all")
        cx = w / 2
        rounded_rect(self, cx - 28, 30, cx + 28, 86, 17, fill=t["accent"],
                     outline="")
        for i, bar_height in enumerate((11, 21, 31)):
            x = cx - 16 + i * 12
            rounded_rect(self, x, 73 - bar_height, x + 8, 73, 3,
                         fill="#FFFFFF", outline="")
        self.create_text(cx, 112, text="No habits yet", font=f["row_b"],
                         fill=t["text"])
        self.create_text(cx, 132, text="Type one above and press Enter.\n"
                         "Small steps add up, bit by bit.", justify="center",
                         anchor="n", font=f["sub"], fill=t["muted"])


class ScrollList(tk.Frame):
    """A vertically scrolling container for the habit cards."""

    def __init__(self, parent, bg):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.window = self.canvas.create_window(0, 0, window=self.inner,
                                                anchor="nw")
        self.inner.bind("<Configure>", self.on_inner_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        for widget in (self.canvas, self.inner):
            widget.bind("<Enter>", self.bind_wheel)
            widget.bind("<Leave>", self.unbind_wheel)

    def on_inner_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)

    def bind_wheel(self, _event):
        self.canvas.bind_all("<MouseWheel>", self.on_wheel)
        self.canvas.bind_all("<Button-4>", lambda e: self.scroll(-1))
        self.canvas.bind_all("<Button-5>", lambda e: self.scroll(1))

    def unbind_wheel(self, _event):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def on_wheel(self, event):
        # macOS reports small deltas, Windows reports multiples of 120
        step = event.delta if abs(event.delta) < 10 else event.delta / 120
        self.scroll(-step)

    def scroll(self, amount):
        if self.inner.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(amount * 2) or int(amount), "units")


# ---------------------------------------------------------------------------
# The app
# ---------------------------------------------------------------------------

class BitByBitApp:
    def __init__(self):
        self.tracker = HabitTracker()
        self.tracker.load()

        self.root = tk.Tk()
        self.root.title("Bit by Bit")
        self.root.geometry("440x740")
        self.root.minsize(400, 520)

        if sys.platform == "darwin":
            family = ".AppleSystemUIFont"  # the real SF font on a Mac
        else:
            families = set(tkfont.families())
            family = next((name for name in FONT_CHOICES if name in families),
                          "TkDefaultFont")
        self.fonts = {
            "title": tkfont.Font(family=family, size=26, weight="bold"),
            "row": tkfont.Font(family=family, size=13),
            "row_b": tkfont.Font(family=family, size=13, weight="bold"),
            "sub": tkfont.Font(family=family, size=11),
            "heading": tkfont.Font(family=family, size=13, weight="bold"),
            "chip": tkfont.Font(family=family, size=13, weight="bold"),
            "big": tkfont.Font(family=family, size=34, weight="bold"),
            "stat": tkfont.Font(family=family, size=15, weight="bold"),
            "stat_s": tkfont.Font(family=family, size=10, weight="bold"),
            "body": tkfont.Font(family=family, size=11),
            "body_l": tkfont.Font(family=family, size=13),
            "button": tkfont.Font(family=family, size=13, weight="bold"),
            "small": tkfont.Font(family=family, size=11),
            "tiny": tkfont.Font(family=family, size=9),
            "label": tkfont.Font(family=family, size=10, weight="bold"),
        }

        self.icon_images = {}  # cache of uploaded pictures (tk needs us to keep them)
        self.toast_job = None
        self.shown_day = date.today()
        self.build()
        self.root.after(30000, self.check_new_day)

    @property
    def t(self):
        return THEMES[self.tracker.theme]

    def habit_color(self, index):
        return HABIT_COLORS[self.tracker.theme][index % COLOR_COUNT]

    # -- building the screen ------------------------------------------------

    def build(self):
        for child in self.root.winfo_children():
            child.destroy()
        t = self.t
        self.root.configure(bg=t["bg"])

        page = tk.Frame(self.root, bg=t["bg"])
        page.pack(fill="both", expand=True, padx=24, pady=(16, 12))

        self.header = Header(page, self)
        self.header.pack(fill="x")
        self.stats = StatsCard(page, self)
        self.stats.pack(fill="x", pady=(6, 10))
        self.add_bar = AddBar(page, self)
        self.add_bar.pack(fill="x")

        self.section = tk.Label(page, text="", bg=t["bg"], fg=t["muted"],
                                font=self.fonts["label"], anchor="w")
        self.section.pack(fill="x", padx=(14, 0), pady=(18, 6))

        self.toast = tk.Label(page, text="", bg=t["bg"], fg=t["muted"],
                              font=self.fonts["body"], height=1)
        self.toast.pack(side="bottom", fill="x", pady=(8, 0))

        self.list = ScrollList(page, t["bg"])
        self.list.pack(fill="both", expand=True)
        self.populate()

    def populate(self):
        for child in self.list.inner.winfo_children():
            child.destroy()
        self.cards = {}
        habits = self.tracker.habits
        self.section.config(text="HABITS" if habits else "")
        if not habits:
            EmptyState(self.list.inner, self).pack(fill="x")
        for index, habit in enumerate(habits):
            if len(habits) == 1:
                position = "single"
            elif index == 0:
                position = "first"
            elif index == len(habits) - 1:
                position = "last"
            else:
                position = "middle"
            card = HabitCard(self.list.inner, self, habit, position)
            card.pack(fill="x")
            self.cards[habit.name] = card
        self.stats.draw()

    def show_message(self, text, good=True):
        color = self.t["success"] if good else self.t["danger"]
        self.toast.config(text=text, fg=color)
        if self.toast_job:
            self.root.after_cancel(self.toast_job)
        self.toast_job = self.root.after(3000, lambda: self.toast.config(text=""))

    # -- actions ------------------------------------------------------------

    def get_icon_image(self, filename):
        """Load an uploaded picture from the icons folder (None if unreadable)."""
        if filename not in self.icon_images:
            image = None
            try:
                path = str(ICON_DIR / filename)
                if Image is not None:
                    picture = Image.open(path).convert("RGBA")
                    picture.thumbnail((ICON_PIXELS, ICON_PIXELS))
                    image = ImageTk.PhotoImage(picture)
                else:
                    image = tk.PhotoImage(file=path)
                    biggest = max(image.width(), image.height())
                    if biggest > ICON_PIXELS:
                        image = image.subsample(math.ceil(biggest / ICON_PIXELS))
                    elif biggest * 2 <= ICON_PIXELS:
                        image = image.zoom(ICON_PIXELS // biggest)
            except Exception:
                image = None
            self.icon_images[filename] = image
        return self.icon_images[filename]

    def import_icon(self, path):
        """Store an uploaded picture. Returns the icon text, or raises ValueError."""
        filename = import_icon_image(path)
        if self.get_icon_image(filename) is None:
            (ICON_DIR / filename).unlink(missing_ok=True)
            raise ValueError("That file could not be read as a picture.")
        return f"file:{filename}"

    def choose_icon_for(self, habit):
        accent = self.habit_color(habit.color)

        def chosen(icon):
            habit.icon = icon
            self.tracker.save()
            self.cards[habit.name].draw()
            self.show_message(f"Updated the icon for '{habit.name}'.")
        IconPicker(self, habit.icon, habit.name, accent, chosen)

    def add_habit(self, name, icon=None):
        message = self.tracker.add_habit(name, icon=icon)
        added = message.endswith("added successfully.")
        if added:
            self.tracker.save()
            self.populate()
            # scroll down so the new habit is visible
            self.root.update_idletasks()
            self.list.canvas.yview_moveto(1.0)
        self.show_message(message, good=added)
        return added

    def toggle_habit(self, habit):
        if habit.done_today():
            habit.undo_log()
            message = f"Unmarked '{habit.name}' for today."
        else:
            result = habit.log_streak()
            message = (f"{habit.name}: {result} day streak. Keep going!"
                       if isinstance(result, int) else result)
        self.tracker.save()
        self.cards[habit.name].draw()
        self.stats.draw()
        self.show_message(message)

    def delete_habit(self, habit):
        if messagebox.askyesno("Remove habit",
                               f"Remove '{habit.name}' and its streak?"):
            message = self.tracker.remove_habit(habit.name)
            self.tracker.save()
            self.populate()
            self.show_message(message, good=False)

    def toggle_theme(self):
        self.tracker.theme = "light" if self.tracker.theme == "dark" else "dark"
        self.tracker.save()
        self.build()

    def check_new_day(self):
        """Refresh everything when midnight passes while the app is open."""
        if date.today() != self.shown_day:
            self.shown_day = date.today()
            self.header.draw()
            self.populate()
        self.root.after(30000, self.check_new_day)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    BitByBitApp().run()
