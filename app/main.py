"""
OverlayOS - Entry point.
Ctrl+Space toggles overlay. System tray icon.
"""
import sys
import os

# Force unbuffered output so we see prints immediately
sys.stdout.reconfigure(line_buffering=True)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt5.QtCore import Qt, QTimer
import keyboard

from overlay_window import OverlayController


def create_tray_icon():
    px = QPixmap(32, 32)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#3b82f6"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(2, 2, 28, 28)
    p.setPen(QColor("white"))
    p.setFont(QFont("Segoe UI", 14, QFont.Bold))
    p.drawText(px.rect(), Qt.AlignCenter, "A")
    p.end()
    return QIcon(px)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("OverlayOS")

    overlay = OverlayController()

    # System tray
    tray = QSystemTrayIcon(create_tray_icon(), app)
    menu = QMenu()
    show_act = QAction("Toggle Overlay (Ctrl+Space)")
    show_act.triggered.connect(overlay.toggle)
    menu.addAction(show_act)
    quit_act = QAction("Quit OverlayOS")
    quit_act.triggered.connect(app.quit)
    menu.addAction(quit_act)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda r: overlay.toggle() if r == QSystemTrayIcon.Trigger else None)
    tray.setToolTip("OverlayOS - Ctrl+Space to toggle")
    tray.show()

    # Global hotkey
    keyboard.add_hotkey('ctrl+space', lambda: QTimer.singleShot(0, overlay.toggle), suppress=True)

    overlay.show()
    print("=" * 40)
    print("  OverlayOS running!")
    print("  Ctrl+Space -> Toggle overlay")
    print("=" * 40)
    sys.stdout.flush()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
