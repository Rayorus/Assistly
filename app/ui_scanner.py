"""
OverlayOS - UI Scanner.
Uses Windows UI Automation to get real element positions.
Gives pixel-perfect coordinates for taskbar, desktop icons, and active windows.
"""
import traceback


def scan_ui_elements():
    """Get positions of taskbar icons, desktop icons, and active window elements.
    Returns a list of {"name": ..., "x": ..., "y": ..., "type": ...}
    """
    elements = []
    try:
        elements += _scan_taskbar()
    except:
        pass
    try:
        elements += _scan_active_window()
    except:
        pass
    return elements


def _scan_taskbar():
    """Get taskbar button positions using pywinauto."""
    items = []
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")

        # Find taskbar
        taskbar = desktop.window(class_name="Shell_TrayWnd")
        if not taskbar.exists():
            return items

        # Get all buttons in the taskbar
        buttons = taskbar.descendants(control_type="Button")
        for btn in buttons:
            try:
                name = btn.window_text()
                if not name or len(name) < 2:
                    continue
                rect = btn.rectangle()
                cx = (rect.left + rect.right) // 2
                cy = (rect.top + rect.bottom) // 2
                items.append({
                    "name": name,
                    "x": cx, "y": cy,
                    "type": "taskbar"
                })
            except:
                continue

        # Also get system tray items
        try:
            tray = desktop.window(class_name="Shell_TrayWnd").child_window(class_name="TrayNotifyWnd")
            if tray.exists():
                tray_btns = tray.descendants(control_type="Button")
                for btn in tray_btns:
                    try:
                        name = btn.window_text()
                        if name and len(name) >= 2:
                            rect = btn.rectangle()
                            cx = (rect.left + rect.right) // 2
                            cy = (rect.top + rect.bottom) // 2
                            items.append({"name": name, "x": cx, "y": cy, "type": "tray"})
                    except:
                        continue
        except:
            pass

    except Exception as e:
        print(f"[SCAN] Taskbar error: {e}", flush=True)
    return items


def _scan_active_window():
    """Get elements of the currently active/foreground window."""
    items = []
    try:
        from pywinauto import Desktop
        import ctypes

        # Get foreground window
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return items

        desktop = Desktop(backend="uia")
        try:
            win = desktop.window(handle=hwnd)
            if not win.exists():
                return items

            title = win.window_text()
            items.append({"name": f"Window: {title}", "x": 0, "y": 0, "type": "info"})

            # Get top-level buttons and menu items (limit depth for speed)
            for ctrl_type in ["Button", "MenuItem", "TabItem"]:
                try:
                    children = win.descendants(control_type=ctrl_type, depth=3)
                    for child in children[:15]:  # Limit for speed
                        try:
                            name = child.window_text()
                            if not name or len(name) < 2:
                                continue
                            rect = child.rectangle()
                            cx = (rect.left + rect.right) // 2
                            cy = (rect.top + rect.bottom) // 2
                            items.append({
                                "name": name,
                                "x": cx, "y": cy,
                                "type": ctrl_type.lower()
                            })
                        except:
                            continue
                except:
                    continue

        except Exception as e:
            pass

    except Exception as e:
        print(f"[SCAN] Window error: {e}", flush=True)
    return items


def format_elements(elements):
    """Format element list as text for the AI prompt."""
    if not elements:
        return ""

    lines = ["CLICKABLE ELEMENTS (exact pixel positions):"]
    for el in elements:
        if el["type"] == "info":
            lines.append(f"  [{el['name']}]")
        else:
            lines.append(f"  - \"{el['name']}\" at x={el['x']}, y={el['y']} ({el['type']})")
    return "\n".join(lines)
