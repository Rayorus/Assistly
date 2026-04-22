"""
OverlayOS - Split UI: Top Notch + Bottom-Right Convo Panel
Single-instance, all buttons functional.
"""
import sys as _sys
import os
import threading
import tempfile
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QLineEdit, QFrame, QGraphicsDropShadowEffect, QApplication
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QScreen

from ai_engine import AIEngine
from voice_engine import VoiceEngine
from ai_cursor import AICursor

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
QPushButton:hover {{ background:rgba(255,255,255,0.12); color:white; }}
QPushButton:pressed {{ background:rgba(255,255,255,0.18); }}"""

_DEFAULT_BTN = _btn_style()


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
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedHeight(48)

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        box = QFrame()
        box.setStyleSheet("QFrame{background:rgba(10,10,12,210);border-radius:24px;border:1px solid rgba(255,255,255,0.08);}")
        sh = QGraphicsDropShadowEffect(); sh.setBlurRadius(40); sh.setColor(QColor(0,0,0,150)); sh.setOffset(0,6)
        box.setGraphicsEffect(sh)

        h = QHBoxLayout(box)
        h.setContentsMargins(16, 6, 16, 6)
        h.setSpacing(10)

        self.dot = QLabel(); self.dot.setFixedSize(8,8)
        self.dot.setStyleSheet(f"background:{W40};border-radius:4px;border:none;")
        h.addWidget(self.dot)

        t = QLabel("AI Cursor"); t.setFont(QFont(FONT,11,QFont.Black))
        t.setStyleSheet(f"color:{W90};border:none;"); h.addWidget(t)

        self.status = QLabel("Ready"); self.status.setFont(QFont(FONT,9))
        self.status.setStyleSheet(f"color:{W40};border:none;"); h.addWidget(self.status)

        sep = QFrame(); sep.setFixedSize(1,20)
        sep.setStyleSheet("background:rgba(255,255,255,0.1);border:none;")
        h.addSpacing(6); h.addWidget(sep); h.addSpacing(6)

        # MIC
        self.mic_btn = self._btn("\U0001f3a4"); self.mic_btn.setToolTip("Mic: Record voice")
        self.mic_btn.clicked.connect(self._on_mic); h.addWidget(self.mic_btn)
        # EYE
        self.eye_btn = self._btn("\U0001f441"); self.eye_btn.setToolTip("Eye: Capture screen")
        self.eye_btn.clicked.connect(self.eye_clicked.emit); h.addWidget(self.eye_btn)
        # SETTINGS
        self.set_btn = self._btn("\u2699"); self.set_btn.setToolTip("Settings")
        self.set_btn.clicked.connect(self.settings_clicked.emit); h.addWidget(self.set_btn)
        # CLOSE
        cb = self._btn("\u2715"); cb.setToolTip("Hide overlay")
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

    def __init__(self):
        super().__init__()
        self._expanded = True  # Start expanded
        self._setup()
        self._build()

    def _setup(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._screen = QApplication.primaryScreen().geometry()
        self._reposition(True)  # Start expanded

    def _reposition(self, expanded):
        w, h = (360, 440) if expanded else (360, 56)
        self.setFixedSize(w, h)
        self.move(self._screen.width()-w-16, self._screen.height()-h-50)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0,0,0,0)

        self.panel = QFrame(); self.panel.setObjectName("cp")
        self.panel.setStyleSheet("QFrame#cp{background:rgba(10,10,12,220);border-radius:16px;border:1px solid rgba(255,255,255,0.06);}")
        sh = QGraphicsDropShadowEffect(); sh.setBlurRadius(40); sh.setColor(QColor(0,0,0,140)); sh.setOffset(0,8)
        self.panel.setGraphicsEffect(sh)

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
        self.scroll.setWidget(self.chat_w); self.scroll.setVisible(True)  # Visible from start
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
        self.input_row.setVisible(True); lay.addWidget(self.input_row)  # Visible from start

        root.addWidget(self.panel)

    def _build_settings(self):
        f = QFrame()
        f.setStyleSheet(f"QFrame{{background:rgba(0,0,0,0.3);border-radius:10px;border:1px solid rgba(255,255,255,0.05);}}QLabel{{color:{W70};font-size:11px;border:none;background:transparent;}}QLineEdit{{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.08);border-radius:6px;color:white;padding:4px 8px;font-size:11px;}}QLineEdit:focus{{border-color:{ACCENT};}}")
        fl = QVBoxLayout(f); fl.setContentsMargins(10,8,10,8); fl.setSpacing(6)
        fl.addWidget(QLabel("Settings"))
        r1 = QHBoxLayout(); r1.addWidget(QLabel("Groq Key"))
        self.api_input = QLineEdit(); self.api_input.setPlaceholderText("gsk_...")
        self.api_input.setEchoMode(QLineEdit.Password); self.api_input.setFixedWidth(160)
        r1.addWidget(self.api_input); fl.addLayout(r1)
        r2 = QHBoxLayout(); r2.addWidget(QLabel("Voice Out"))
        self.voice_btn = QPushButton("ON"); self.voice_btn.setFixedSize(44,22)
        self.voice_btn.setStyleSheet(f"QPushButton{{background:{GREEN};color:white;border-radius:6px;font-size:10px;font-weight:bold;border:none;}}")
        r2.addWidget(self.voice_btn); fl.addLayout(r2)
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
    step_triggered = pyqtSignal()


# ══════════════════════════════════════════════════════════
#  CONTROLLER - Ties it all together
# ══════════════════════════════════════════════════════════
class OverlayController:
    def __init__(self):
        self.ai = AIEngine()
        self.voice = VoiceEngine()
        self.voice_out = True
        self.eye_on = False
        self._screenshot_path = os.path.join(tempfile.gettempdir(), "overlayos_screen.png")

        self.notch = NotchBar()
        self.convo = ConvoPanel()
        self.cursor = AICursor()

        # Thread-safe bridge for AI responses
        self._bridge = _ResponseBridge()
        self._bridge.response_ready.connect(self._on_response)
        self._bridge.step_triggered.connect(self._on_step_triggered)

        self.active_sequence = None
        self._click_cooldown = False

        try:
            from pynput import mouse
            self.mouse_listener = mouse.Listener(on_click=self._on_mouse_click)
            self.mouse_listener.start()
        except ImportError:
            print("[WARN] pynput not installed, auto-sequence disabled.", flush=True)

        # Tell AI engine the screen dimensions
        screen = QApplication.primaryScreen().geometry()
        self.ai.set_screen_size(screen.width(), screen.height())

        if self.ai.api_key and not self.ai.api_key.startswith("sk-your"):
            self.convo.api_input.setText(self.ai.api_key)

        # Keep windows always-on-top even when other apps take focus
        self._raise_timer = QTimer()
        self._raise_timer.timeout.connect(self._force_on_top)
        self._raise_timer.start(2000)  # Every 2 seconds

        self._connect()

    def _connect(self):
        self.notch.mic_toggled.connect(self._on_mic)
        self.notch.eye_clicked.connect(self._on_eye)
        self.notch.settings_clicked.connect(self.convo.toggle_settings)
        self.notch.close_clicked.connect(self.hide)

        self.voice.transcript_ready.connect(self._on_transcript)
        self.voice.interim_update.connect(self.convo.show_interim)
        self.voice.listening_started.connect(lambda: self.notch.set_status("Listening...", GREEN))
        self.voice.listening_stopped.connect(self._on_listen_stop)
        self.voice.error_occurred.connect(lambda e: self.convo.add_message(f"Error: {e}", False))

        self.convo.send_requested.connect(self._on_text_send)
        self.convo.api_input.editingFinished.connect(self._save_api_key)
        self.convo.voice_btn.clicked.connect(self._toggle_voice_out)

    # ── MIC ──────────────────────────────────────────────
    def _on_mic(self, on):
        if on:
            self.voice.start_listening()
            self.convo.auto_expand()
        else:
            self.voice.stop_listening()
            self.convo.hide_interim()

    def _on_listen_stop(self):
        self.notch.mic_on = False
        self.notch.mic_btn.setStyleSheet(_DEFAULT_BTN)
        self.notch.set_status("Ready", W40)
        self.convo.hide_interim()

    def _on_transcript(self, text):
        self.convo.hide_interim()
        self.convo.add_message(text, True)
        self._process(text)

    # ── EYE ──────────────────────────────────────────────
    def _on_eye(self):
        self.eye_on = not self.eye_on
        self.notch.set_eye_active(self.eye_on)
        if self.eye_on:
            self._capture_screen()
            self.convo.add_message("[Screen shared - AI can see your screen]", False)
            self.notch.set_status("Screen shared", ACCENT)
        else:
            self.notch.set_status("Ready", W40)
            self.convo.add_message("[Screen sharing stopped]", False)

    def _capture_screen(self):
        """Hide overlay, capture clean screen, restore overlay."""
        try:
            # Hide all overlay windows so AI sees the real screen
            was_notch = self.notch.isVisible()
            was_convo = self.convo.isVisible()
            was_cursor = self.cursor.isVisible()

            self.notch.hide()
            self.convo.hide()
            self.cursor.hide()
            QApplication.processEvents()  # Force repaint

            # Small delay for Windows to finish hiding
            import time
            time.sleep(0.08)

            screen = QApplication.primaryScreen()
            if screen:
                pixmap = screen.grabWindow(0)
                pixmap.save(self._screenshot_path, "PNG")

            # Restore overlay windows
            if was_notch:
                self.notch.show()
                self.notch.position_on_screen()
            if was_convo:
                self.convo.show()
            if was_cursor:
                self.cursor.show()
            QApplication.processEvents()
            self._force_on_top()

        except Exception as e:
            # Make sure overlay comes back even on error
            self.notch.show()
            self.convo.show()
            self.cursor.show()
            print(f"[ERR] Screenshot: {e}", flush=True)

    # ── SEQUENCE ─────────────────────────────────────────
    def _on_mouse_click(self, x, y, button, pressed):
        if pressed and self.active_sequence and not self._click_cooldown:
            # Check if user clicked near the cursor guide
            self._click_cooldown = True
            # We wait 1 second for UI to update, then trigger next step
            threading.Thread(target=self._wait_and_trigger, daemon=True).start()

    def _wait_and_trigger(self):
        import time
        time.sleep(1.0)
        self._bridge.step_triggered.emit()

    def _on_step_triggered(self):
        if self.active_sequence:
            self._click_cooldown = False
            self.convo.add_message("[Auto-advancing...]", False)
            self._process(f"User just clicked. Analyze screen and provide next step for: {self.active_sequence}")

    # ── TEXT SEND ────────────────────────────────────────
    def _on_text_send(self, text):
        self.active_sequence = text  # Start a new sequence
        self.convo.add_message(text, True)
        self._process(text)

    # ── PROCESS ──────────────────────────────────────────
    def _process(self, text):
        self.notch.set_status("Processing...", "#facc15")
        # ALWAYS capture screen so AI can see what's happening
        self._capture_screen()
        screenshot = self._screenshot_path

        def run():
            try:
                result = self.ai.get_response(text, screenshot)
            except Exception as e:
                result = {"message": f"Error: {e}", "guide": None}
            # SIGNAL (thread-safe!) instead of QTimer.singleShot
            self._bridge.response_ready.emit(result)

        threading.Thread(target=run, daemon=True).start()

    # ── RESPONSE (runs on main thread via signal) ────────
    def _on_response(self, result):
        print(f"[OK] Response received on main thread!", flush=True)

        if isinstance(result, str):
            result = {"message": result, "guide": None}

        msg = result.get("message", "")
        guide = result.get("guide", None)

        self.convo.add_message(msg, False)

        if guide and "x" in guide and "y" in guide:
            x, y = guide["x"], guide["y"]
            label = guide.get("label", "Here")
            print(f"[OK] Cursor -> ({x}, {y}) '{label}'", flush=True)
            self.cursor.move_to(x, y, label)
        else:
            self.cursor.hide_all()

        status = result.get("status", "complete")
        if status == "complete":
            self.active_sequence = None
            print("[OK] Sequence complete.", flush=True)
        else:
            print("[OK] Sequence in progress, waiting for click...", flush=True)

        if self.voice_out and msg:
            self.voice.speak(msg)

        if guide and "x" in guide and "y" in guide:
            self.notch.set_status("Guiding...", ACCENT)
            QTimer.singleShot(8000, self.cursor.go_idle)
        else:
            self.cursor.go_idle()
            listening = self.notch.mic_on
            self.notch.set_status(
                "Listening..." if listening else ("Screen shared" if self.eye_on else "Ready"),
                GREEN if listening else (ACCENT if self.eye_on else W40)
            )

        if self.voice_out:
            self.voice.speak(msg)

    # ── SETTINGS ─────────────────────────────────────────
    def _save_api_key(self):
        key = self.convo.api_input.text().strip()
        if key:
            self.ai.set_api_key(key)
            try:
                import pathlib, re
                env = pathlib.Path(__file__).parent / ".env"
                content = env.read_text()
                content = re.sub(r'GROQ_API_KEY=.*', f'GROQ_API_KEY={key}', content)
                env.write_text(content)
            except: pass
            self.convo.add_message("API key saved!", False)

    def _toggle_voice_out(self):
        self.voice_out = not self.voice_out
        if self.voice_out:
            self.convo.voice_btn.setText("ON")
            self.convo.voice_btn.setStyleSheet(f"QPushButton{{background:{GREEN};color:white;border-radius:6px;font-size:10px;font-weight:bold;border:none;}}")
        else:
            self.convo.voice_btn.setText("OFF")
            self.convo.voice_btn.setStyleSheet(f"QPushButton{{background:rgba(255,255,255,0.1);color:{W40};border-radius:6px;font-size:10px;font-weight:bold;border:none;}}")

    # ── ALWAYS ON TOP (Win32 API) ──────────────────────────
    def _force_on_top(self):
        """Use Win32 API to force all overlay windows to stay on top."""
        if not self.notch.isVisible():
            return
        try:
            import ctypes
            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE

            for widget in [self.notch, self.convo, self.cursor]:
                if widget.isVisible():
                    hwnd = int(widget.winId())
                    ctypes.windll.user32.SetWindowPos(
                        hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags
                    )
        except:
            # Fallback: just raise
            for w in [self.notch, self.convo, self.cursor]:
                if w.isVisible():
                    w.raise_()

    # ── SHOW / HIDE / TOGGLE ─────────────────────────────
    def show(self):
        self.notch.show()
        self.notch.position_on_screen()
        self.convo.show()
        self.cursor.show_at_center()
        self._force_on_top()

    def hide(self):
        self.notch.hide()
        self.convo.hide()
        self.cursor.hide_all()

    def toggle(self):
        if self.notch.isVisible():
            self.hide()
        else:
            self.show()
