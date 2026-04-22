"""
OverlayOS - AI Cursor v3: Always-visible, always-moving.
Small window that repositions via move() on every frame.
"""
import math
import sys
from PyQt5.QtWidgets import QWidget, QApplication, QLabel
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QRadialGradient, QPen, QBrush


DOT_SIZE = 140


class AICursor(QWidget):
    """Small always-on-top window with a glowing blue dot."""

    arrived = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._sx = 960   # screen x
        self._sy = 540   # screen y
        self._label = ""
        self._pulse = 0.0
        self._idle = True
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

        # Always reposition window
        self.move(self._sx - DOT_SIZE // 2, self._sy - DOT_SIZE // 2)

        if self.isVisible():
            self.update()

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
        print(f"[CURSOR] Visible at center ({self._sx}, {self._sy})")
        sys.stdout.flush()

    def move_to(self, x, y, label="", duration=900):
        """Animate cursor to screen (x, y)."""
        print(f"[CURSOR] Moving to ({x}, {y}) label='{label}'")
        sys.stdout.flush()

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

        cx = DOT_SIZE / 2
        cy = DOT_SIZE / 2
        ps = 1.0 + 0.12 * math.sin(self._pulse)
        pa = int(160 + 80 * math.sin(self._pulse))

        if self._idle:
            # Soft breathing glow
            r = 30 * ps
            g = QRadialGradient(cx, cy, r)
            g.setColorAt(0, QColor(59, 130, 246, 45))
            g.setColorAt(1, QColor(59, 130, 246, 0))
            p.setPen(Qt.NoPen); p.setBrush(QBrush(g))
            p.drawEllipse(int(cx-r), int(cy-r), int(r*2), int(r*2))

            # Ring
            rr = 14 * ps
            p.setPen(QPen(QColor(59,130,246, pa//2), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(int(cx-rr), int(cy-rr), int(rr*2), int(rr*2))

            # Core
            p.setPen(QPen(QColor(255,255,255,180), 1.5))
            p.setBrush(QColor(59,130,246,200))
            p.drawEllipse(int(cx-6), int(cy-6), 12, 12)
        else:
            # Active: bright glow
            for i in range(3):
                r = (28 + i*10) * ps
                a = max(10, 45 - i*15)
                g = QRadialGradient(cx, cy, r)
                g.setColorAt(0, QColor(59,130,246, a))
                g.setColorAt(1, QColor(59,130,246, 0))
                p.setPen(Qt.NoPen); p.setBrush(QBrush(g))
                p.drawEllipse(int(cx-r), int(cy-r), int(r*2), int(r*2))

            # Pulsing ring
            rr = 18 * ps
            p.setPen(QPen(QColor(59,130,246, pa), 2.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(int(cx-rr), int(cy-rr), int(rr*2), int(rr*2))

            # Core
            p.setPen(QPen(QColor(255,255,255,230), 2))
            p.setBrush(QColor(59,130,246,245))
            p.drawEllipse(int(cx-9), int(cy-9), 18, 18)

            # Highlight
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255,255,255,100))
            p.drawEllipse(int(cx-3), int(cy-4), 6, 5)

        p.end()
