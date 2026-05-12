"""
Assistly - Split UI: Top Notch + Bottom-Right Convo Panel
Multi-step flow: user clicks "Done → Next" after each step.
UI elements scanned while overlay is hidden for accuracy.
"""
import sys as _sys
import ctypes
import os
import threading
import tempfile
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QLineEdit, QFrame, QGraphicsDropShadowEffect, QApplication,
    QComboBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QScreen

from ai_engine import AIEngine
from voice_engine import VoiceEngine
from ai_cursor import AICursor, CURSOR_THEMES
from ui_scanner import scan_ui_elements, get_foreground_hwnd, UIWatcher, find_element_by_name, register_overlay_hwnd

FONT = "Segoe UI"
ACCENT = "#3b82f6"
GREEN = "#22c55e"
RED = "#ef4444"
W90 = "rgba(255,255,255,0.9)"
W70 = "rgba(255,255,255,0.7)"
W40 = "rgba(255,255,255,0.4)"

# ─── Reusable button style ───────────────────────────────
def _btn_style(bg="rgba(255,255,255,0.06)", border="rgba(255,255,255,0.08)", color=W70, radius=16):
    return f"""QPushButton {{ background:{bg}; border:1px solid {border}; border-radius:{radius}px; color:{color}; }}
QPushButton:hover {{ background:rgba(255,255,255,0.15); color:white; border-color:rgba(255,255,255,0.15); }}
QPushButton:pressed {{ background:rgba(255,255,255,0.22); }}"""

_DEFAULT_BTN = _btn_style()


# ══════════════════════════════════════════════════════════
#  SETTINGS POPUP - Drops down from notch bar
# ══════════════════════════════════════════════════════════

# Style for unselected theme button
_THEME_BTN = (
    "QPushButton{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);"
    "border-radius:8px;color:rgba(255,255,255,0.7);font-size:11px;text-align:left;padding:4px 8px;}"
    "QPushButton:hover{background:rgba(255,255,255,0.12);color:white;}"
)
# Style for selected theme button
_THEME_BTN_ACTIVE = (
    f"QPushButton{{background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.4);"
    f"border-radius:8px;color:white;font-size:11px;text-align:left;padding:4px 8px;}}"
)

class SettingsPopup(QWidget):
    """Floating settings panel anchored below the notch bar.
    Uses clickable buttons for cursor themes (no dropdown needed)."""
    cursor_theme_changed = pyqtSignal(str)
    voice_toggled = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._voice_on = True
        self._selected_theme = "default"
        self._theme_btns = {}
        self._setup()
        self._build()

    def _setup(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Tool | Qt.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle("Assistly Settings")
        self.setFixedSize(280, 290)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        box = QFrame()
        box.setStyleSheet(
            f"QFrame{{background:rgba(10,10,12,230);border-radius:14px;"
            f"border:1px solid rgba(255,255,255,0.08);}}"
            f"QLabel{{color:{W70};font-size:11px;border:none;background:transparent;}}"
        )

        fl = QVBoxLayout(box)
        fl.setContentsMargins(14, 10, 14, 10); fl.setSpacing(6)

        title = QLabel("Settings")
        title.setFont(QFont(FONT, 11, QFont.Bold))
        title.setStyleSheet(f"color:{W90};border:none;")
        fl.addWidget(title)

        # ── Cursor theme buttons ────────────────────────
        cl = QLabel("Cursor Style")
        cl.setStyleSheet(f"color:{W40};font-size:10px;border:none;margin-top:2px;")
        fl.addWidget(cl)

        # Two-column grid of theme buttons
        from PyQt5.QtWidgets import QGridLayout
        grid = QGridLayout(); grid.setSpacing(4)
        for i, theme in enumerate(CURSOR_THEMES):
            btn = QPushButton(f" {theme['emoji']}  {theme['name']}")
            btn.setFixedHeight(28)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFont(QFont(FONT, 10))
            if theme['id'] == "default":
                btn.setStyleSheet(_THEME_BTN_ACTIVE)
            else:
                btn.setStyleSheet(_THEME_BTN)
            btn.clicked.connect(lambda checked, tid=theme['id']: self._on_theme_click(tid))
            self._theme_btns[theme['id']] = btn
            grid.addWidget(btn, i // 2, i % 2)
        fl.addLayout(grid)

        # ── Voice output toggle ─────────────────────────
        r2 = QHBoxLayout(); r2.setSpacing(8)
        r2.addWidget(QLabel("Voice Out"))
        self.voice_btn = QPushButton("ON")
        self.voice_btn.setFixedSize(44, 22)
        self.voice_btn.setCursor(Qt.PointingHandCursor)
        self.voice_btn.setStyleSheet(
            f"QPushButton{{background:{GREEN};color:white;border-radius:6px;"
            f"font-size:10px;font-weight:bold;border:none;}}"
        )
        self.voice_btn.clicked.connect(self._on_voice_toggle)
        r2.addWidget(self.voice_btn)
        r2.addStretch()
        fl.addLayout(r2)

        root.addWidget(box)

    def _on_theme_click(self, theme_id):
        """Select a cursor theme."""
        self._selected_theme = theme_id
        # Update button styles
        for tid, btn in self._theme_btns.items():
            if tid == theme_id:
                btn.setStyleSheet(_THEME_BTN_ACTIVE)
            else:
                btn.setStyleSheet(_THEME_BTN)
        self.cursor_theme_changed.emit(theme_id)

    def _on_voice_toggle(self):
        self._voice_on = not self._voice_on
        self.voice_toggled.emit(self._voice_on)
        if self._voice_on:
            self.voice_btn.setText("ON")
            self.voice_btn.setStyleSheet(
                f"QPushButton{{background:{GREEN};color:white;border-radius:6px;"
                f"font-size:10px;font-weight:bold;border:none;}}"
            )
        else:
            self.voice_btn.setText("OFF")
            self.voice_btn.setStyleSheet(
                f"QPushButton{{background:rgba(255,255,255,0.1);color:{W40};border-radius:6px;"
                f"font-size:10px;font-weight:bold;border:none;}}"
            )

    def position_below_notch(self):
        """Position this popup centered below the notch bar."""
        s = QApplication.primaryScreen().geometry()
        x = (s.width() - self.width()) // 2
        self.move(x, 65)

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.position_below_notch()
            self.show()
            self.raise_()


# ══════════════════════════════════════════════════════════
#  NOTCH BAR - Top Center
# ══════════════════════════════════════════════════════════
class NotchBar(QWidget):
    mic_toggled = pyqtSignal(bool)
    eye_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()
    close_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.mic_on = False
        self._setup()
        self._build()

    def _setup(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.X11BypassWindowManagerHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle("Assistly Notch")
        self.setFixedHeight(48)

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        box = QFrame()
        # Use stylesheet shadow instead of QGraphicsDropShadowEffect
        # QGraphicsDropShadowEffect causes ghost/duplicate rendering artifacts on hover
        box.setStyleSheet("QFrame{background:rgba(10,10,12,210);border-radius:24px;border:1px solid rgba(255,255,255,0.08);}")

        h = QHBoxLayout(box)
        h.setContentsMargins(16, 6, 16, 6)
        h.setSpacing(10)

        self.dot = QLabel(); self.dot.setFixedSize(8,8)
        self.dot.setStyleSheet(f"background:{W40};border-radius:4px;border:none;")
        h.addWidget(self.dot)

        t = QLabel("Assistly"); t.setFont(QFont(FONT,11,QFont.Black))
        t.setStyleSheet(f"color:{W90};border:none;"); h.addWidget(t)

        self.status = QLabel("Ready"); self.status.setFont(QFont(FONT,9))
        self.status.setStyleSheet(f"color:{W40};border:none;"); h.addWidget(self.status)

        sep = QFrame(); sep.setFixedSize(1,20)
        sep.setStyleSheet("background:rgba(255,255,255,0.1);border:none;")
        h.addSpacing(6); h.addWidget(sep); h.addSpacing(6)

        # MIC — NO tooltip to prevent duplicate button on hover
        self.mic_btn = self._btn("\U0001f3a4")
        self.mic_btn.clicked.connect(self._on_mic); h.addWidget(self.mic_btn)
        # EYE — NO tooltip
        self.eye_btn = self._btn("\U0001f441")
        self.eye_btn.clicked.connect(self.eye_clicked.emit); h.addWidget(self.eye_btn)
        # SETTINGS — NO tooltip
        self.set_btn = self._btn("\u2699")
        self.set_btn.clicked.connect(self.settings_clicked.emit); h.addWidget(self.set_btn)
        # CLOSE — NO tooltip
        cb = self._btn("\u2715")
        cb.clicked.connect(self.close_clicked.emit); h.addWidget(cb)

        root.addStretch(); root.addWidget(box); root.addStretch()

    def _btn(self, icon):
        b = QPushButton(icon); b.setFixedSize(32,32); b.setCursor(Qt.PointingHandCursor)
        b.setFont(QFont(FONT,12)); b.setStyleSheet(_DEFAULT_BTN); return b

    def _on_mic(self):
        self.mic_on = not self.mic_on
        if self.mic_on:
            self.mic_btn.setStyleSheet(_btn_style("rgba(34,197,94,0.2)","rgba(34,197,94,0.3)",GREEN))
        else:
            self.mic_btn.setStyleSheet(_DEFAULT_BTN)
        self.mic_toggled.emit(self.mic_on)

    def set_eye_active(self, on):
        if on:
            self.eye_btn.setStyleSheet(_btn_style("rgba(59,130,246,0.2)","rgba(59,130,246,0.3)",ACCENT))
        else:
            self.eye_btn.setStyleSheet(_DEFAULT_BTN)

    def set_status(self, text, color):
        self.status.setText(text)
        self.dot.setStyleSheet(f"background:{color};border-radius:4px;border:none;")

    def position_on_screen(self):
        s = QApplication.primaryScreen().geometry()
        self.setFixedWidth(400)
        self.move((s.width()-400)//2, 10)


# ══════════════════════════════════════════════════════════
#  CONVO PANEL - Bottom Right
# ══════════════════════════════════════════════════════════
class ConvoPanel(QWidget):
    send_requested = pyqtSignal(str)
    next_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._expanded = True
        self._setup()
        self._build()

    def _setup(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.X11BypassWindowManagerHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        # Prevent hover from creating duplicate overlay buttons
        self.setMouseTracking(False)
        self.setWindowTitle("Assistly Panel")
        self._screen = QApplication.primaryScreen().geometry()
        self._reposition(True)

    def _reposition(self, expanded):
        w, h = (360, 440) if expanded else (360, 56)
        self.setFixedSize(w, h)
        self.move(self._screen.width()-w-16, self._screen.height()-h-50)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0,0,0,0)

        self.panel = QFrame(); self.panel.setObjectName("cp")
        self.panel.setStyleSheet("QFrame#cp{background:rgba(10,10,12,220);border-radius:16px;border:1px solid rgba(255,255,255,0.06);}")

        lay = QVBoxLayout(self.panel)
        lay.setContentsMargins(14,10,14,10); lay.setSpacing(6)

        # Header
        hdr = QHBoxLayout(); hdr.setSpacing(8)
        ic = QLabel("\U0001f4ac"); ic.setFont(QFont(FONT,12)); ic.setStyleSheet("border:none;")
        hdr.addWidget(ic)
        self.hdr_lbl = QLabel("Conversation"); self.hdr_lbl.setFont(QFont(FONT,11,QFont.Bold))
        self.hdr_lbl.setStyleSheet(f"color:{W90};border:none;"); hdr.addWidget(self.hdr_lbl)
        hdr.addStretch()
        self.exp_btn = QPushButton("\u25B2"); self.exp_btn.setFixedSize(26,26)
        self.exp_btn.setCursor(Qt.PointingHandCursor); self.exp_btn.setFont(QFont(FONT,9))
        self.exp_btn.setStyleSheet(f"QPushButton{{background:rgba(255,255,255,0.06);border-radius:13px;color:{W40};border:1px solid rgba(255,255,255,0.08);}}QPushButton:hover{{background:rgba(255,255,255,0.12);color:white;}}")
        self.exp_btn.clicked.connect(self.toggle_expand); hdr.addWidget(self.exp_btn)
        lay.addLayout(hdr)

        # Chat scroll
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}QWidget{background:transparent;}QScrollBar:vertical{width:3px;background:transparent;}QScrollBar::handle:vertical{background:rgba(255,255,255,0.1);border-radius:1px;}QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}")
        self.chat_w = QWidget(); self.chat_lay = QVBoxLayout(self.chat_w)
        self.chat_lay.setContentsMargins(0,0,0,0); self.chat_lay.setSpacing(6)
        self.chat_lay.addStretch()
        self.scroll.setWidget(self.chat_w); self.scroll.setVisible(True)
        lay.addWidget(self.scroll, 1)

        # Interim
        self.interim = QLabel(""); self.interim.setWordWrap(True); self.interim.setFont(QFont(FONT,10))
        self.interim.setStyleSheet(f"color:{GREEN};font-style:italic;border:none;padding:2px 0;")
        self.interim.setVisible(False); lay.addWidget(self.interim)

        # Settings
        self.settings_frame = self._build_settings(); self.settings_frame.setVisible(False)
        lay.addWidget(self.settings_frame)

        # Input row
        self.input_row = QWidget()
        ir = QHBoxLayout(self.input_row); ir.setContentsMargins(0,0,0,0); ir.setSpacing(6)
        self.text_input = QLineEdit(); self.text_input.setPlaceholderText("Type a message...")
        self.text_input.setFixedHeight(34); self.text_input.setFont(QFont(FONT,10))
        self.text_input.setStyleSheet(f"QLineEdit{{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.08);border-radius:10px;color:white;padding:0 12px;}}QLineEdit:focus{{border-color:rgba(59,130,246,0.4);}}")
        self.text_input.returnPressed.connect(self._on_send); ir.addWidget(self.text_input)
        sb = QPushButton("\u27A4"); sb.setFixedSize(34,34); sb.setCursor(Qt.PointingHandCursor)
        sb.setStyleSheet(f"QPushButton{{background:{ACCENT};color:white;border-radius:10px;font-size:14px;border:none;}}QPushButton:hover{{background:#2563eb;}}")
        sb.clicked.connect(self._on_send); ir.addWidget(sb)
        self.input_row.setVisible(True); lay.addWidget(self.input_row)

        root.addWidget(self.panel)

    def _build_settings(self):
        """Minimal settings in convo panel — main settings are in the notch popup."""
        f = QFrame()
        f.setStyleSheet(f"QFrame{{background:rgba(0,0,0,0.3);border-radius:10px;border:1px solid rgba(255,255,255,0.05);}}QLabel{{color:{W70};font-size:11px;border:none;background:transparent;}}")
        fl = QVBoxLayout(f); fl.setContentsMargins(10,8,10,8); fl.setSpacing(6)
        fl.addWidget(QLabel("Use ⚙ in top bar for settings"))
        # Hidden API input (still exists for programmatic use but not shown)
        self.api_input = QLineEdit(); self.api_input.setVisible(False)
        return f

    def toggle_expand(self):
        self._expanded = not self._expanded
        self.scroll.setVisible(self._expanded)
        self.input_row.setVisible(self._expanded)
        if not self._expanded:
            self.settings_frame.setVisible(False)
        self.exp_btn.setText("\u25BC" if self._expanded else "\u25B2")
        self._reposition(self._expanded)
        self.raise_()

    def toggle_settings(self):
        if not self._expanded: self.toggle_expand()
        self.settings_frame.setVisible(not self.settings_frame.isVisible())

    def auto_expand(self):
        if not self._expanded: self.toggle_expand()

    def add_message(self, text, is_user):
        self.auto_expand()
        bub = QFrame(); bub.setStyleSheet("background:transparent;border:none;")
        bl = QHBoxLayout(bub); bl.setContentsMargins(0,1,0,1)
        lbl = QLabel(text); lbl.setWordWrap(True); lbl.setFont(QFont(FONT,10)); lbl.setMaximumWidth(250)
        if is_user:
            lbl.setStyleSheet(f"background:rgba(99,102,241,0.15);border:1px solid rgba(99,102,241,0.2);color:{W90};border-radius:12px;padding:6px 10px;")
            bl.addStretch(); bl.addWidget(lbl)
        else:
            lbl.setStyleSheet(f"background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.06);color:rgba(255,255,255,0.85);border-radius:12px;padding:6px 10px;")
            bl.addWidget(lbl); bl.addStretch()
        self.chat_lay.insertWidget(self.chat_lay.count()-1, bub)
        QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))

    def show_interim(self, text):
        self.auto_expand()
        self.interim.setText(f"\U0001f7e2 {text}")
        self.interim.setVisible(True)

    def hide_interim(self):
        self.interim.setVisible(False)

    def _on_send(self):
        t = self.text_input.text().strip()
        if t:
            self.text_input.clear()
            self.send_requested.emit(t)


# ══════════════════════════════════════════════════════════
#  BRIDGE - Thread-safe signal emitter
# ══════════════════════════════════════════════════════════
from PyQt5.QtCore import QObject

class _ResponseBridge(QObject):
    """Emits a signal on the main thread when AI response is ready."""
    response_ready = pyqtSignal(object)


# ══════════════════════════════════════════════════════════
#  CONTROLLER - Multi-step flow with user-driven "Next"
# ══════════════════════════════════════════════════════════
class OverlayController:
    def __init__(self):
        self.ai = AIEngine()
        self.voice = VoiceEngine()
        self.voice_out = True
        self.eye_on = True  # Always-on screen awareness (like Copilot)
        self._screenshot_path = os.path.join(tempfile.gettempdir(), "assistly_screen.png")
        self._current_goal = None
        self._cached_elements = []  # Always-fresh from background watcher

        self.notch = NotchBar()
        self.convo = ConvoPanel()
        self.cursor = AICursor()
        self.settings_popup = SettingsPopup()

        # Live UI watcher — ALWAYS running, fast interval
        self._watcher = UIWatcher(interval=1.5, on_update=self._on_watcher_update)

        # Thread-safe bridge for AI responses
        self._bridge = _ResponseBridge()
        self._bridge.response_ready.connect(self._on_response)

        # Tell AI engine the screen dimensions
        screen = QApplication.primaryScreen().geometry()
        self.ai.set_screen_size(screen.width(), screen.height())

        # API key is loaded from .env automatically, no need to display it

        self._connect()

    def _connect(self):
        self.notch.mic_toggled.connect(self._on_mic)
        self.notch.eye_clicked.connect(self._on_eye)
        self.notch.settings_clicked.connect(self.settings_popup.toggle_visibility)
        self.notch.close_clicked.connect(self.hide)

        self.voice.transcript_ready.connect(self._on_transcript)
        self.voice.interim_update.connect(self.convo.show_interim)
        self.voice.listening_started.connect(lambda: self.notch.set_status("Listening...", GREEN))
        self.voice.listening_stopped.connect(self._on_listen_stop)
        self.voice.error_occurred.connect(lambda e: self.convo.add_message(f"Error: {e}", False))

        self.convo.send_requested.connect(self._on_text_send)

        # Settings popup signals
        self.settings_popup.cursor_theme_changed.connect(self._on_cursor_theme)
        self.settings_popup.voice_toggled.connect(self._on_voice_toggled)

    # ── MIC ──────────────────────────────────────────────
    def _on_mic(self, on):
        if on:
            self.voice.start_listening()
            self.convo.auto_expand()
        else:
            self.voice.stop_listening()
            self.convo.hide_interim()

    def _on_listen_stop(self):
        # We don't turn off the mic visually because it's continuous
        # wait, if it errors or turns off, we reset UI.
        self.notch.mic_on = False
        self.notch.mic_btn.setStyleSheet(_DEFAULT_BTN)
        self.notch.set_status("Ready", W40)
        self.convo.hide_interim()

    def _on_transcript(self, text):
        self.convo.hide_interim()
        self.convo.add_message(text, True)
        self._current_goal = text
        self._process(text)

        # RE-START LISTENING automatically if mic was toggled on!
        if self.notch.mic_on:
            QTimer.singleShot(500, self.voice.start_listening)

    # ── EYE ──────────────────────────────────────────────
    def _on_eye(self):
        """Toggle screenshot-enhanced mode (eye button).
        Screen awareness (Accessibility API) is ALWAYS on.
        Eye button adds optional screenshot for visual questions."""
        self.eye_on = not self.eye_on
        self.notch.set_eye_active(self.eye_on)
        if self.eye_on:
            self.convo.add_message("[Screenshot mode ON]", False)
        else:
            self.convo.add_message("[Screenshot mode OFF — using Accessibility API only]", False)

    def _on_watcher_update(self, elements):
        """Called by background watcher when new elements are available."""
        self._cached_elements = elements

    def _take_screenshot_if_needed(self):
        """Only take screenshot if eye_on (enhanced mode). No hide/show blink."""
        if not self.eye_on:
            return None
        try:
            screen = QApplication.primaryScreen()
            if screen:
                pixmap = screen.grabWindow(0)
                pixmap.save(self._screenshot_path, "PNG")
                return self._screenshot_path
        except Exception as e:
            print(f"[ERR] Screenshot: {e}", flush=True)
        return None

    # ── TEXT SEND ────────────────────────────────────────
    def _on_text_send(self, text):
        self._current_goal = text
        self.convo.add_message(text, True)
        self._process(text)

    # ── NEXT STEP ────────────────────────────────────────
    def _on_next_step(self):
        if not self._current_goal:
            return
        self.convo.add_message("[Agent progressing...]", True)
        continuation = f"I completed the previous step. Look at the new screenshot and give me the NEXT step to achieve: {self._current_goal}"
        self._process(continuation)

    # ── PROCESS ──────────────────────────────────────────
    def _process(self, text):
        self.notch.set_status("Processing...", "#facc15")

        # Use cached elements from background watcher (NO blink, NO hide/show)
        elements = self._cached_elements or []
        # Only take screenshot if enhanced mode (eye button) is on
        screenshot = self._take_screenshot_if_needed()

        print(f"[FAST] Processing with {len(elements)} cached elements, screenshot={'YES' if screenshot else 'NO'}", flush=True)

        def run():
            try:
                result = self.ai.get_response(text, screenshot, elements)
            except Exception as e:
                result = {"message": f"Error: {e}", "guide": None, "agent_action": None, "status": "complete"}
            self._bridge.response_ready.emit(result)

        threading.Thread(target=run, daemon=True).start()

    # ── RESPONSE (runs on main thread via signal) ────────
    def _on_response(self, result):
        if isinstance(result, str):
            result = {"message": result, "guide": None, "agent_action": None, "status": "complete"}

        msg = result.get("message", "")
        guide = result.get("guide", None)
        agent_action = result.get("agent_action", None)
        status = result.get("status", "complete")

        self.convo.add_message(msg, False)

        if status == "in_progress" and not agent_action:
            self.notch.set_status("Waiting for your action...", GREEN)
        else:
            if not agent_action:
                self._current_goal = None
                self.notch.set_status("Listening...", GREEN) if self.notch.mic_on else self.notch.set_status("Ready", W40)

        # Move cursor if guide provided
        if guide and "x" in guide and "y" in guide:
            x, y = guide["x"], guide["y"]
            label = guide.get("label", "Here")
            print(f"[OK] Cursor -> ({x}, {y}) '{label}'", flush=True)
            self.cursor.move_to(x, y, label)
            
            # NOTE: Only the AI overlay cursor moves — NOT the user's real mouse!
            # pyautogui.moveTo is only used in agent_action (autonomous mode)
        else:
            self.cursor.go_idle()

        # Handle autonomous agent action
        if agent_action:
            import pyautogui
            action_type = agent_action.get("type")
            try:
                if action_type == "click":
                    ax = int(agent_action.get("x", 0))
                    ay = int(agent_action.get("y", 0))
                    pyautogui.click(ax, ay)
                elif action_type == "hover":
                    ax = int(agent_action.get("x", 0))
                    ay = int(agent_action.get("y", 0))
                    pyautogui.moveTo(ax, ay, duration=0.2)
                elif action_type == "type":
                    txt = agent_action.get("text", "")
                    print(f"[AGENT] Typing '{txt}'", flush=True)
                    pyautogui.write(txt, interval=0.01)
                    pyautogui.press('enter')
            except Exception as e:
                print(f"[AGENT] Action failed: {e}", flush=True)

            if status == "in_progress":
                self.notch.set_status("Agent working...", "#facc15")
                # Auto-loop without waiting for user
                QTimer.singleShot(1500, self._on_next_step)

        if self.voice_out and msg:
            self.voice.speak(msg)

    # ── SETTINGS ─────────────────────────────────────────
    def _on_cursor_theme(self, theme_id):
        self.cursor.set_theme(theme_id)
        # Find theme name for display
        for t in CURSOR_THEMES:
            if t['id'] == theme_id:
                self.convo.add_message(f"Cursor style: {t['name']}", False)
                break

    def _on_voice_toggled(self, on):
        self.voice_out = on

    # ── KEEP ON TOP ──────────────────────────────────────
    def _force_topmost(self):
        """Periodically enforce overlay windows stay on top of ALL apps.
        Uses Win32 SetWindowPos with HWND_TOPMOST for reliable z-order."""
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOACTIVATE = 0x0010
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE

        # Must use c_void_p for HWND on 64-bit Windows — plain int -1 gets truncated
        import ctypes.wintypes
        _swp = ctypes.windll.user32.SetWindowPos
        _swp.argtypes = [
            ctypes.wintypes.HWND,  # hWnd
            ctypes.wintypes.HWND,  # hWndInsertAfter
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,  # x,y,cx,cy
            ctypes.wintypes.UINT   # uFlags
        ]
        _swp.restype = ctypes.wintypes.BOOL
        HWND_TOPMOST = ctypes.wintypes.HWND(-1 & 0xFFFFFFFFFFFFFFFF)

        for widget in [self.notch, self.convo, self.cursor, self.cursor._tip, self.settings_popup]:
            try:
                if widget.isVisible():
                    hwnd = ctypes.wintypes.HWND(int(widget.winId()))
                    _swp(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
            except Exception:
                pass

    # ── SHOW / HIDE / TOGGLE ─────────────────────────────
    def _register_overlay_windows(self):
        """Register all overlay HWNDs with the scanner so it skips them."""
        for widget in [self.notch, self.convo, self.cursor, self.cursor._tip, self.settings_popup]:
            try:
                hwnd = int(widget.winId())
                if hwnd:
                    register_overlay_hwnd(hwnd)
            except Exception:
                pass

    def show(self):
        self.notch.show()
        self.notch.position_on_screen()
        self.convo.show()
        self.cursor.show_at_center()

        # Register overlay windows so scanner skips them
        self._register_overlay_windows()

        # Force on top immediately
        self._force_topmost()

        # Keep forcing on top every 300ms so we stay above fullscreen/focused apps
        self._topmost_timer = QTimer()
        self._topmost_timer.timeout.connect(self._force_topmost)
        self._topmost_timer.start(300)

        # Auto-start background UI scanning (always-on, like Copilot)
        self._watcher.start()
        self.notch.set_eye_active(True)
        self.notch.set_status("Screen aware", ACCENT)

    def hide(self):
        if hasattr(self, '_topmost_timer'):
            self._topmost_timer.stop()
        self.notch.hide()
        self.convo.hide()
        self.cursor.hide_all()
        self.settings_popup.hide()
        self._watcher.stop()

    def toggle(self):
        if self.notch.isVisible():
            self.hide()
        else:
            self.show()
