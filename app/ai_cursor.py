"""
Assistly - AI Cursor v5: Multiple cursor themes + reliable movement.
Uses Qt move() for positioning — controller's _force_topmost handles z-order.
Themes: default dot, sword, minecraft block, fire, skull, nyan rainbow.
"""
import math
import sys
from PyQt5.QtWidgets import QWidget, QApplication, QLabel
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPointF
from PyQt5.QtGui import (
    QPainter, QColor, QRadialGradient, QPen, QBrush,
    QPolygonF, QLinearGradient, QFont
)

DOT_SIZE = 140

# ── Available cursor themes ─────────────────────────────────
CURSOR_THEMES = [
    {"id": "default",   "name": "Default Dot",     "emoji": "🔵"},
    {"id": "sword",     "name": "Diamond Sword",    "emoji": "⚔️"},
    {"id": "minecraft", "name": "Minecraft Block",  "emoji": "🟫"},
    {"id": "fire",      "name": "Fire Cursor",      "emoji": "🔥"},
    {"id": "skull",     "name": "Skull Cursor",     "emoji": "💀"},
    {"id": "nyan",      "name": "Nyan Rainbow",     "emoji": "🌈"},
]


class AICursor(QWidget):
    """Small always-on-top window with themed cursor visuals.
    Movement uses Qt move(). Z-order is enforced by the controller."""

    arrived = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._sx = 960
        self._sy = 540
        self._label = ""
        self._pulse = 0.0
        self._idle = True
        self._theme = "default"
        # Animation state
        self._anim_active = False
        self._anim_sx = 0.0
        self._anim_sy = 0.0
        self._anim_ex = 0.0
        self._anim_ey = 0.0
        self._anim_t = 0
        self._anim_dur = 900

        self._init_window()
        self._init_tooltip()
        self._start_timer()

    def _init_window(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowDoesNotAcceptFocus |
            Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(DOT_SIZE, DOT_SIZE)

    def _init_tooltip(self):
        self._tip = QLabel()
        self._tip.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Tool | Qt.WindowDoesNotAcceptFocus |
            Qt.WindowTransparentForInput
        )
        self._tip.setAttribute(Qt.WA_TranslucentBackground)
        self._tip.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._tip.setAttribute(Qt.WA_ShowWithoutActivating)
        self._tip.setStyleSheet("""
            QLabel {
                background: rgba(0, 0, 0, 210);
                color: #e0e0ff;
                font-family: 'Segoe UI';
                font-size: 12px;
                font-weight: bold;
                padding: 7px 16px;
                border-radius: 12px;
                border: 1px solid rgba(59, 130, 246, 100);
            }
        """)
        self._tip.hide()

    def _start_timer(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # ~60fps

    def _tick(self):
        self._pulse = (self._pulse + 0.04) % (2 * math.pi)

        if self._anim_active:
            self._anim_t += 16
            t = min(self._anim_t / self._anim_dur, 1.0)

            # Ease in-out cubic
            if t < 0.5:
                ease = 4 * t * t * t
            else:
                ease = 1 - pow(-2 * t + 2, 3) / 2

            self._sx = int(self._anim_sx + (self._anim_ex - self._anim_sx) * ease)
            self._sy = int(self._anim_sy + (self._anim_ey - self._anim_sy) * ease)

            if t >= 1.0:
                self._anim_active = False
                self._update_tooltip()
                self.arrived.emit()

        # Reposition using Qt move — reliable for all windows
        new_x = self._sx - DOT_SIZE // 2
        new_y = self._sy - DOT_SIZE // 2
        self.move(new_x, new_y)

        if self.isVisible():
            self.update()

    # ── Theme API ───────────────────────────────────────
    def set_theme(self, theme_id):
        """Change cursor visual theme."""
        self._theme = theme_id
        print(f"[CURSOR] Theme changed to: {theme_id}", flush=True)
        self.update()

    def get_theme(self):
        return self._theme

    @staticmethod
    def get_available_themes():
        return CURSOR_THEMES

    # ── Public API ───────────────────────────────────────
    def show_at_center(self):
        screen = QApplication.primaryScreen().geometry()
        self._sx = screen.width() // 2
        self._sy = screen.height() // 2
        self._idle = True
        self._label = ""
        self._tip.hide()
        self.move(self._sx - DOT_SIZE // 2, self._sy - DOT_SIZE // 2)
        self.show()
        self.raise_()
        print(f"[CURSOR] Visible at center ({self._sx}, {self._sy})", flush=True)

    def move_to(self, x, y, label="", duration=900):
        """Animate cursor to screen (x, y)."""
        print(f"[CURSOR] Moving to ({x}, {y}) label='{label}'", flush=True)

        self._idle = False
        self._label = label
        self._anim_active = True
        self._anim_sx = float(self._sx)
        self._anim_sy = float(self._sy)
        self._anim_ex = float(x)
        self._anim_ey = float(y)
        self._anim_t = 0
        self._anim_dur = duration

        self._tip.hide()
        self.show()
        self.raise_()

    def _update_tooltip(self):
        if self._label:
            self._tip.setText(f"  {self._label}  ")
            self._tip.adjustSize()
            tx = self._sx + 30
            ty = self._sy + 25
            screen = QApplication.primaryScreen().geometry()
            if tx + self._tip.width() > screen.width() - 10:
                tx = self._sx - self._tip.width() - 20
            if ty + self._tip.height() > screen.height() - 10:
                ty = self._sy - self._tip.height() - 20
            self._tip.move(tx, ty)
            self._tip.show()
            self._tip.raise_()

    def go_idle(self):
        self._idle = True
        self._label = ""
        self._tip.hide()

    def hide_all(self):
        self.hide()
        self._tip.hide()

    # ── Paint ────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        theme = self._theme
        if theme == "sword":
            self._paint_sword(p)
        elif theme == "minecraft":
            self._paint_minecraft(p)
        elif theme == "fire":
            self._paint_fire(p)
        elif theme == "skull":
            self._paint_skull(p)
        elif theme == "nyan":
            self._paint_nyan(p)
        else:
            self._paint_default(p)

        p.end()

    # ── Theme: Default Dot ───────────────────────────────
    def _paint_default(self, p):
        cx = DOT_SIZE / 2
        cy = DOT_SIZE / 2
        ps = 1.0 + 0.12 * math.sin(self._pulse)
        pa = int(160 + 80 * math.sin(self._pulse))

        if self._idle:
            r = 30 * ps
            g = QRadialGradient(cx, cy, r)
            g.setColorAt(0, QColor(59, 130, 246, 45))
            g.setColorAt(1, QColor(59, 130, 246, 0))
            p.setPen(Qt.NoPen); p.setBrush(QBrush(g))
            p.drawEllipse(int(cx-r), int(cy-r), int(r*2), int(r*2))
            rr = 14 * ps
            p.setPen(QPen(QColor(59,130,246, pa//2), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(int(cx-rr), int(cy-rr), int(rr*2), int(rr*2))
            p.setPen(QPen(QColor(255,255,255,180), 1.5))
            p.setBrush(QColor(59,130,246,200))
            p.drawEllipse(int(cx-6), int(cy-6), 12, 12)
        else:
            for i in range(3):
                r = (28 + i*10) * ps
                a = max(10, 45 - i*15)
                g = QRadialGradient(cx, cy, r)
                g.setColorAt(0, QColor(59,130,246, a))
                g.setColorAt(1, QColor(59,130,246, 0))
                p.setPen(Qt.NoPen); p.setBrush(QBrush(g))
                p.drawEllipse(int(cx-r), int(cy-r), int(r*2), int(r*2))
            rr = 18 * ps
            p.setPen(QPen(QColor(59,130,246, pa), 2.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(int(cx-rr), int(cy-rr), int(rr*2), int(rr*2))
            p.setPen(QPen(QColor(255,255,255,230), 2))
            p.setBrush(QColor(59,130,246,245))
            p.drawEllipse(int(cx-9), int(cy-9), 18, 18)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255,255,255,100))
            p.drawEllipse(int(cx-3), int(cy-4), 6, 5)

    # ── Theme: Diamond Sword ─────────────────────────────
    def _paint_sword(self, p):
        cx, cy = DOT_SIZE / 2, DOT_SIZE / 2
        bob = 2 * math.sin(self._pulse)
        pa = int(180 + 60 * math.sin(self._pulse))

        # Glow behind sword
        g = QRadialGradient(cx, cy, 35)
        g.setColorAt(0, QColor(100, 200, 255, 40))
        g.setColorAt(1, QColor(100, 200, 255, 0))
        p.setPen(Qt.NoPen); p.setBrush(QBrush(g))
        p.drawEllipse(int(cx-35), int(cy-35), 70, 70)

        p.save()
        p.translate(cx, cy + bob)
        p.rotate(-45)

        # Blade
        blade = QLinearGradient(-3, -30, 3, -30)
        blade.setColorAt(0, QColor(120, 220, 255, pa))
        blade.setColorAt(0.5, QColor(200, 240, 255, pa))
        blade.setColorAt(1, QColor(80, 180, 240, pa))
        p.setPen(QPen(QColor(60, 160, 220, 200), 1))
        p.setBrush(QBrush(blade))
        pts = QPolygonF([QPointF(0, -32), QPointF(-4, -8), QPointF(0, -4), QPointF(4, -8)])
        p.drawPolygon(pts)

        # Guard
        p.setPen(QPen(QColor(80, 80, 80), 1))
        p.setBrush(QColor(160, 130, 60))
        p.drawRect(-10, -4, 20, 4)

        # Handle
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(100, 70, 40))
        p.drawRect(-2, 0, 4, 14)

        # Pommel
        p.setBrush(QColor(60, 180, 220))
        p.drawEllipse(-3, 13, 6, 6)

        p.restore()

    # ── Theme: Minecraft Block ───────────────────────────
    def _paint_minecraft(self, p):
        cx, cy = DOT_SIZE / 2, DOT_SIZE / 2
        bob = 1.5 * math.sin(self._pulse)
        sz = 24

        # Shadow
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawRect(int(cx - sz/2 + 2), int(cy - sz/2 + 2 + bob), sz, sz)

        # Dirt block body
        p.setBrush(QColor(139, 90, 43))
        p.setPen(QPen(QColor(80, 50, 20), 2))
        p.drawRect(int(cx - sz/2), int(cy - sz/2 + bob), sz, sz)

        # Grass top
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(80, 180, 60))
        p.drawRect(int(cx - sz/2), int(cy - sz/2 + bob), sz, 7)

        # Pixel details on dirt
        p.setBrush(QColor(160, 110, 60, 120))
        for dx, dy in [(3, 10), (8, 14), (15, 11), (5, 18), (17, 17)]:
            p.drawRect(int(cx - sz/2 + dx), int(cy - sz/2 + dy + bob), 3, 3)

        # Pixel details on grass
        p.setBrush(QColor(60, 140, 40, 150))
        for dx in [2, 8, 14, 19]:
            p.drawRect(int(cx - sz/2 + dx), int(cy - sz/2 + 1 + bob), 2, 2)

        # Glow ring
        pa = int(80 + 40 * math.sin(self._pulse))
        p.setPen(QPen(QColor(80, 180, 60, pa), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawRect(int(cx - sz/2 - 4), int(cy - sz/2 - 4 + bob), sz + 8, sz + 8)

    # ── Theme: Fire Cursor ───────────────────────────────
    def _paint_fire(self, p):
        cx, cy = DOT_SIZE / 2, DOT_SIZE / 2
        ps = 1.0 + 0.15 * math.sin(self._pulse)
        flicker = 3 * math.sin(self._pulse * 2.3)

        # Outer glow
        g = QRadialGradient(cx, cy, 35 * ps)
        g.setColorAt(0, QColor(255, 100, 0, 50))
        g.setColorAt(1, QColor(255, 50, 0, 0))
        p.setPen(Qt.NoPen); p.setBrush(QBrush(g))
        p.drawEllipse(int(cx-35*ps), int(cy-35*ps), int(70*ps), int(70*ps))

        # Draw emoji
        font = QFont("Segoe UI Emoji", 28)
        p.setFont(font)
        p.setPen(QColor(255, 255, 255, 255))
        p.drawText(int(cx - 18 + flicker * 0.3), int(cy + 12 - abs(flicker)), "🔥")

    # ── Theme: Skull Cursor ──────────────────────────────
    def _paint_skull(self, p):
        cx, cy = DOT_SIZE / 2, DOT_SIZE / 2
        bob = 2 * math.sin(self._pulse)
        pa = int(140 + 80 * math.sin(self._pulse))

        # Purple glow
        g = QRadialGradient(cx, cy + bob, 30)
        g.setColorAt(0, QColor(160, 60, 220, 50))
        g.setColorAt(1, QColor(160, 60, 220, 0))
        p.setPen(Qt.NoPen); p.setBrush(QBrush(g))
        p.drawEllipse(int(cx-30), int(cy-30+bob), 60, 60)

        # Draw emoji
        font = QFont("Segoe UI Emoji", 28)
        p.setFont(font)
        p.setPen(QColor(255, 255, 255, pa))
        p.drawText(int(cx - 18), int(cy + 12 + bob), "💀")

    # ── Theme: Nyan Rainbow ──────────────────────────────
    def _paint_nyan(self, p):
        cx, cy = DOT_SIZE / 2, DOT_SIZE / 2
        bob = 2 * math.sin(self._pulse * 1.5)
        phase = self._pulse

        # Rainbow trail
        colors = [
            QColor(255, 0, 0, 120),
            QColor(255, 165, 0, 120),
            QColor(255, 255, 0, 120),
            QColor(0, 200, 0, 120),
            QColor(0, 100, 255, 120),
            QColor(140, 0, 255, 120),
        ]
        trail_w = 30
        stripe_h = 3
        for i, c in enumerate(colors):
            y_off = int(cy - len(colors) * stripe_h / 2 + i * stripe_h + bob)
            wave = int(2 * math.sin(phase + i * 0.5))
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawRect(int(cx - trail_w), y_off + wave, trail_w, stripe_h)

        # Star sparkles
        pa = int(180 + 60 * math.sin(phase * 3))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 200, pa))
        for angle_off in [0, 2.1, 4.2]:
            sx = cx + 20 * math.cos(phase + angle_off)
            sy = cy + 15 * math.sin(phase * 1.5 + angle_off) + bob
            p.drawEllipse(int(sx - 2), int(sy - 2), 4, 4)

        # Cat emoji
        font = QFont("Segoe UI Emoji", 24)
        p.setFont(font)
        p.setPen(QColor(255, 255, 255, 255))
        p.drawText(int(cx - 4), int(cy + 10 + bob), "🐱")
