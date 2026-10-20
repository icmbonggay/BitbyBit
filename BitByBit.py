"""Bit by Bit: a small, good looking habit tracker built with tkinter.

Run it with:  python3 BitByBit.py
Your habits are saved next to this file in habits.json.
"""

import json
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox

DATA_FILE = Path(__file__).with_name("habits.json")
MAX_NAME_LENGTH = 28

# ---------------------------------------------------------------------------
# Look and feel
# ---------------------------------------------------------------------------

THEMES = {
    "dark": {
        "bg": "#0E1016", "card": "#171A23", "card_hover": "#1D212C",
        "border": "#252A38", "text": "#F3F5FA", "muted": "#8990A6",
        "track": "#2A3040", "accent": "#7C5CFF", "success": "#34D399",
        "danger": "#F87171", "on_accent": "#FFFFFF",
    },
    "light": {
        "bg": "#F4F5FA", "card": "#FFFFFF", "card_hover": "#FAFAFE",
        "border": "#E3E6F0", "text": "#151821", "muted": "#6C7389",
        "track": "#E5E8F2", "accent": "#6C47FF", "success": "#10B981",
        "danger": "#EF4444", "on_accent": "#FFFFFF",
    },
}

# Every habit gets its own accent colour.
HABIT_COLORS = ["#7C5CFF", "#FF7A59", "#2EC4A6", "#FFB020", "#EF5DA8", "#3FA7FF"]

FLAME_OUTER = "#FF7A3D"
FLAME_INNER = "#FFC857"

FONT_CHOICES = ["SF Pro Display", "Helvetica Neue", "Segoe UI", "Inter",
                "Helvetica", "DejaVu Sans", "Arial"]


def rounded_rect(canvas, x1, y1, x2, y2, r, **options):
    """Draw a rounded rectangle on a canvas (tkinter has no built in one)."""
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **options)


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


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class Habit:
    def __init__(self, name, last_logged_date=None, streak=0,
                 history=None, color=0, best_streak=None):
        self.name = name
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
        )


class HabitTracker:
    def __init__(self):
        self.habits = []
        self.theme = "dark"

    def add_habit(self, name, date=None, streak=0):
        name = name.strip()
        if not name:
            return "Please type a habit name first."
        if len(name) > MAX_NAME_LENGTH:
            return f"Keep it under {MAX_NAME_LENGTH} characters."
        for habit in self.habits:
            if habit.name.lower() == name.lower():
                return f"Habit '{name}' already exists."
        color = len(self.habits) % len(HABIT_COLORS)
        self.habits.append(Habit(name, date, streak, color=color))
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
    """Logo, title, today's date and the light/dark switch."""

    def __init__(self, parent, app):
        super().__init__(parent, height=56, bg=app.t["bg"],
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

        # logo: three bars growing, "bit by bit"
        rounded_rect(self, 0, 6, 44, 50, 13, fill=t["accent"], outline="")
        for i, bar_height in enumerate((10, 18, 27)):
            x = 10 + i * 10
            rounded_rect(self, x, 40 - bar_height, x + 7, 40, 3,
                         fill=t["on_accent"], outline="")

        self.create_text(58, 19, text="Bit by Bit", anchor="w",
                         font=f["title"], fill=t["text"])
        today = date.today()
        self.create_text(58, 43, text=f"{today:%A, %B} {today.day}",
                         anchor="w", font=f["small"], fill=t["muted"])

        # theme switch: a circle that is half filled
        cx, cy = w - 20, 28
        self.create_oval(cx - 17, cy - 17, cx + 17, cy + 17, fill=t["card"],
                         outline=t["border"], tags="theme")
        self.create_oval(cx - 8, cy - 8, cx + 8, cy + 8, outline=t["text"],
                         width=2, tags="theme")
        self.create_arc(cx - 8, cy - 8, cx + 8, cy + 8, start=90, extent=180,
                        fill=t["text"], outline=t["text"], width=2,
                        tags="theme")


class StatsCard(tk.Canvas):
    """Today's progress bar and the best running streak."""

    def __init__(self, parent, app):
        super().__init__(parent, height=118, bg=app.t["bg"],
                         highlightthickness=0, bd=0)
        self.app = app
        self.bind("<Configure>", lambda e: self.draw())

    def draw(self):
        app, t, f = self.app, self.app.t, self.app.fonts
        tracker = app.tracker
        w, h = self.winfo_width(), self.winfo_height()
        self.delete("all")
        rounded_rect(self, 1, 1, w - 1, h - 1, 20, fill=t["card"],
                     outline=t["border"])

        total = len(tracker.habits)
        done = tracker.done_today_count()
        all_done = total > 0 and done == total

        self.create_text(24, 26, text="TODAY", anchor="w", font=f["label"],
                         fill=t["muted"])
        if total:
            self.create_text(24, 58, text=f"{done}", anchor="w",
                             font=f["big"], fill=t["text"])
            number_width = f["big"].measure(f"{done}")
            self.create_text(24 + number_width + 4, 64, text=f"of {total} done",
                             anchor="w", font=f["body"], fill=t["muted"])
        else:
            self.create_text(24, 58, text="Nothing yet", anchor="w",
                             font=f["heading"], fill=t["text"])

        # best current streak on the right
        top = tracker.top_streak()
        draw_flame(self, w - 62, 40, 13, lit=top > 0, theme=t)
        self.create_text(w - 40, 40, text=str(top), anchor="w",
                         font=f["stat"], fill=t["text"] if top else t["muted"])
        self.create_text(w - 46, 70, text="top streak", anchor="center",
                         font=f["tiny"], fill=t["muted"])

        # progress bar
        x1, x2, y = 24, w - 24, h - 24
        rounded_rect(self, x1, y - 4, x2, y + 4, 4, fill=t["track"], outline="")
        if total and done:
            fill_to = x1 + max(8, (x2 - x1) * done / total)
            rounded_rect(self, x1, y - 4, fill_to, y + 4, 4,
                         fill=t["success"] if all_done else t["accent"],
                         outline="")


class AddBar(tk.Canvas):
    """Text box plus an Add button."""

    PLACEHOLDER = "Add a new habit..."

    def __init__(self, parent, app):
        super().__init__(parent, height=58, bg=app.t["bg"],
                         highlightthickness=0, bd=0)
        self.app = app
        t = app.t
        self.showing_placeholder = True
        self.entry = tk.Entry(self, relief="flat", bd=0, highlightthickness=0,
                              bg=t["card"], fg=t["muted"],
                              insertbackground=t["text"], font=app.fonts["body_l"])
        self.entry.insert(0, self.PLACEHOLDER)
        self.entry.bind("<FocusIn>", self.on_focus_in)
        self.entry.bind("<FocusOut>", self.on_focus_out)
        self.entry.bind("<Return>", lambda e: self.submit())
        self.entry_window = self.create_window(22, 29, window=self.entry,
                                               anchor="w")
        self.bind("<Configure>", lambda e: self.draw())
        self.tag_bind("add", "<Button-1>", lambda e: self.submit())
        self.tag_bind("add", "<Enter>", lambda e: self.config(cursor="hand2"))
        self.tag_bind("add", "<Leave>", lambda e: self.config(cursor=""))

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
        text = "" if self.showing_placeholder else self.entry.get()
        added = self.app.add_habit(text)
        if added:
            self.entry.delete(0, "end")
        self.entry.focus_set()

    def draw(self):
        t = self.app.t
        w, h = self.winfo_width(), self.winfo_height()
        self.delete("shape")
        rounded_rect(self, 1, 1, w - 1, h - 1, 20, fill=t["card"],
                     outline=t["border"], tags="shape")
        rounded_rect(self, w - 98, 9, w - 9, h - 9, 14, fill=t["accent"],
                     outline="", tags=("shape", "add"))
        self.create_text(w - 53, h / 2, text="+  Add", font=self.app.fonts["button"],
                         fill=t["on_accent"], tags=("shape", "add"))
        self.itemconfigure(self.entry_window, width=max(50, w - 140))
        self.tag_lower("shape")


class HabitCard(tk.Canvas):
    """One habit: check circle, name, last 7 days and the streak."""

    HEIGHT = 96

    def __init__(self, parent, app, habit):
        super().__init__(parent, height=self.HEIGHT, bg=app.t["bg"],
                         highlightthickness=0, bd=0)
        self.app = app
        self.habit = habit
        self.hover = False
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Enter>", lambda e: self.set_hover(True))
        self.bind("<Leave>", lambda e: self.set_hover(False))
        for tag, action in (("check", lambda e: app.toggle_habit(habit)),
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
        accent = HABIT_COLORS[habit.color % len(HABIT_COLORS)]
        done = habit.done_today()
        self.delete("all")

        rounded_rect(self, 1, 1, w - 1, h - 1, 20,
                     fill=t["card_hover"] if self.hover else t["card"],
                     outline=accent if done else t["border"])

        # check circle (click to log today, click again to undo)
        cx, cy = 42, h / 2
        if done:
            self.create_oval(cx - 17, cy - 17, cx + 17, cy + 17, fill=accent,
                             outline=accent, tags="check")
            self.create_line(cx - 7, cy, cx - 2, cy + 6, cx + 8, cy - 6,
                             fill="white", width=3, capstyle="round",
                             joinstyle="round", tags="check")
        else:
            self.create_oval(cx - 17, cy - 17, cx + 17, cy + 17, fill=t["card"],
                             outline=accent, width=2, tags="check")

        # name
        streak = habit.current_streak()
        name_space = w - 72 - 112
        self.create_text(72, 32, text=fit_text(habit.name, f["heading"], name_space),
                         anchor="w", font=f["heading"], fill=t["text"])

        # last 7 days
        today = date.today()
        for i in range(7):
            day = today - timedelta(days=6 - i)
            x, y = 78 + i * 20, 63
            filled = day in habit.history
            self.create_oval(x - 6, y - 6, x + 6, y + 6,
                             fill=accent if filled else t["track"], outline="")
            if day == today:
                self.create_oval(x - 9, y - 9, x + 9, y + 9, outline=accent,
                                 width=1)
        self.create_text(78 + 7 * 20 + 2, 63, text=f"best {habit.best_streak}",
                         anchor="w", font=f["tiny"], fill=t["muted"])

        # streak
        sx = w - 58
        draw_flame(self, sx, 30, 11, lit=streak > 0, theme=t)
        self.create_text(sx, 55, text=str(streak), font=f["stat"],
                         fill=t["text"] if streak else t["muted"])
        self.create_text(sx, 77, text="day streak" if streak != 1 else "day",
                         font=f["tiny"], fill=t["muted"])

        # delete button, only while hovering
        if self.hover:
            dx, dy = w - 20, 20
            self.create_oval(dx - 10, dy - 10, dx + 10, dy + 10,
                             fill=t["track"], outline="", tags="delete")
            self.create_line(dx - 4, dy - 4, dx + 4, dy + 4, fill=t["danger"],
                             width=2, capstyle="round", tags="delete")
            self.create_line(dx - 4, dy + 4, dx + 4, dy - 4, fill=t["danger"],
                             width=2, capstyle="round", tags="delete")


class EmptyState(tk.Canvas):
    def __init__(self, parent, app):
        super().__init__(parent, height=230, bg=app.t["bg"],
                         highlightthickness=0, bd=0)
        self.app = app
        self.bind("<Configure>", lambda e: self.draw())

    def draw(self):
        t, f = self.app.t, self.app.fonts
        w = self.winfo_width()
        self.delete("all")
        cx = w / 2
        rounded_rect(self, cx - 36, 28, cx + 36, 100, 22, fill=t["card"],
                     outline=t["border"])
        for i, bar_height in enumerate((14, 26, 40)):
            x = cx - 20 + i * 15
            rounded_rect(self, x, 88 - bar_height, x + 10, 88, 4,
                         fill=t["accent"] if i == 2 else t["track"], outline="")
        self.create_text(cx, 132, text="No habits yet", font=f["heading"],
                         fill=t["text"])
        self.create_text(cx, 156, text="Type one above and press Enter.\n"
                         "Small steps add up, bit by bit.", justify="center",
                         anchor="n",
                         font=f["body"], fill=t["muted"])


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
        self.root.geometry("480x780")
        self.root.minsize(420, 560)

        families = set(tkfont.families())
        family = next((name for name in FONT_CHOICES if name in families),
                      "TkDefaultFont")
        self.fonts = {
            "title": tkfont.Font(family=family, size=22, weight="bold"),
            "heading": tkfont.Font(family=family, size=15, weight="bold"),
            "big": tkfont.Font(family=family, size=34, weight="bold"),
            "stat": tkfont.Font(family=family, size=20, weight="bold"),
            "body": tkfont.Font(family=family, size=12),
            "body_l": tkfont.Font(family=family, size=14),
            "button": tkfont.Font(family=family, size=13, weight="bold"),
            "small": tkfont.Font(family=family, size=12),
            "tiny": tkfont.Font(family=family, size=10),
            "label": tkfont.Font(family=family, size=10, weight="bold"),
        }

        self.toast_job = None
        self.shown_day = date.today()
        self.build()
        self.root.after(30000, self.check_new_day)

    @property
    def t(self):
        return THEMES[self.tracker.theme]

    # -- building the screen ------------------------------------------------

    def build(self):
        for child in self.root.winfo_children():
            child.destroy()
        t = self.t
        self.root.configure(bg=t["bg"])

        page = tk.Frame(self.root, bg=t["bg"])
        page.pack(fill="both", expand=True, padx=24, pady=(22, 14))

        self.header = Header(page, self)
        self.header.pack(fill="x")
        self.stats = StatsCard(page, self)
        self.stats.pack(fill="x", pady=(18, 12))
        self.add_bar = AddBar(page, self)
        self.add_bar.pack(fill="x", pady=(0, 18))

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
        if not self.tracker.habits:
            EmptyState(self.list.inner, self).pack(fill="x")
        for habit in self.tracker.habits:
            card = HabitCard(self.list.inner, self, habit)
            card.pack(fill="x", pady=(0, 12))
            self.cards[habit.name] = card
        self.stats.draw()

    def show_message(self, text, good=True):
        color = self.t["success"] if good else self.t["danger"]
        self.toast.config(text=text, fg=color)
        if self.toast_job:
            self.root.after_cancel(self.toast_job)
        self.toast_job = self.root.after(3000, lambda: self.toast.config(text=""))

    # -- actions ------------------------------------------------------------

    def add_habit(self, name):
        message = self.tracker.add_habit(name)
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
