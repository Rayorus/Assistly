"""
Assistly - UI Scanner v2 (Accessibility API — Best Approach)
═══════════════════════════════════════════════════════════════
Uses Windows UI Automation (UIA) via pywinauto to read the entire UI
structure directly — no screenshots, no OCR, no image processing.

Features:
  • Fast: Caches Desktop instance, scans taskbar + window in parallel threads
  • Smart: Deduplicates by position AND name, filters invisible/tiny elements
  • Rich: Returns bounding rects (x, y, w, h) for precise highlighting
  • Live: Background watcher thread continuously polls the UI tree
  • Deep: Scans nested elements (depth=8) to catch address bars, menus, etc.
  • Typed: Every element has a semantic type (button, tab, textfield, link, etc.)
"""
import ctypes
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Lazy-loaded pywinauto Desktop (cached per-backend) ──────
_desktop_cache = {}
_desktop_lock = threading.Lock()


def _get_desktop():
    """Get or create a cached pywinauto Desktop(backend='uia')."""
    with _desktop_lock:
        if "uia" not in _desktop_cache:
            from pywinauto import Desktop
            _desktop_cache["uia"] = Desktop(backend="uia")
        return _desktop_cache["uia"]


# ══════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════

def scan_ui_elements(target_hwnd=None, include_taskbar=True, max_depth=4):
    """Scan all interactive UI elements on screen using Accessibility API.

    Args:
        target_hwnd:      Specific window handle to scan. If None, uses foreground.
        include_taskbar:  Whether to also scan the Windows taskbar.
        max_depth:        How deep to recurse into the UI tree (4 = fast, 8 = thorough).

    Returns:
        List of dicts:
        [{"id": int, "name": str, "x": int, "y": int, "w": int, "h": int,
          "type": str, "automationId": str, "isEnabled": bool, "value": str}]
    """
    results = []
    futures = {}

    with ThreadPoolExecutor(max_workers=3) as pool:
        if include_taskbar:
            futures["taskbar"] = pool.submit(_scan_taskbar)
        futures["desktop"] = pool.submit(_scan_desktop)
        futures["window"] = pool.submit(_scan_window, target_hwnd, max_depth)

        for key, future in futures.items():
            try:
                items = future.result(timeout=6)
                results.extend(items)
            except Exception as e:
                print(f"[SCAN] {key} timeout/error: {e}", flush=True)

    # Deduplicate by position (5px tolerance) and name
    results = _deduplicate(results)

    # Assign sequential IDs
    for i, el in enumerate(results):
        el["id"] = i

    return results


# ── Overlay HWND tracking — scanner uses this to skip our windows ──
_overlay_hwnds = set()
_overlay_hwnds_lock = threading.Lock()

def register_overlay_hwnd(hwnd):
    """Register an overlay window handle so the scanner skips it."""
    with _overlay_hwnds_lock:
        _overlay_hwnds.add(int(hwnd))

def unregister_overlay_hwnd(hwnd):
    with _overlay_hwnds_lock:
        _overlay_hwnds.discard(int(hwnd))


# ── Last known real app — survives overlay focus ──
_last_real_hwnd = None
_last_real_lock = threading.Lock()


def get_foreground_hwnd():
    """Get the foreground window that the user is actually using.
    Skips: Assistly windows, shell windows, tool windows, etc.
    Falls back to the last known real app if overlay is currently focused.
    """
    global _last_real_hwnd

    SKIP_CLASSES = {"Shell_TrayWnd", "Progman", "WorkerW", "Shell_SecondaryTrayWnd",
                    "NotifyIconOverflowWindow", "Windows.UI.Core.CoreWindow"}
    SKIP_TITLES = {"Assistly", "AI Cursor", "Program Manager"}

    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            with _last_real_lock:
                return _last_real_hwnd

        # Check if it's one of our registered overlay windows
        with _overlay_hwnds_lock:
            if int(hwnd) in _overlay_hwnds:
                # Overlay is focused — use last known real app
                with _last_real_lock:
                    if _last_real_hwnd:
                        return _last_real_hwnd
                # No cached app — walk Z-order
                return _walk_z_order(hwnd, SKIP_CLASSES, SKIP_TITLES)

        title = _get_window_title(hwnd)
        cls = _get_window_class(hwnd)

        # Check title/class skip list
        if title and cls not in SKIP_CLASSES and not any(s in title for s in SKIP_TITLES):
            # This is a real app — cache it
            with _last_real_lock:
                _last_real_hwnd = hwnd
            return hwnd

        # Foreground is a shell/overlay — walk Z-order to find real app
        real = _walk_z_order(hwnd, SKIP_CLASSES, SKIP_TITLES)
        if real:
            with _last_real_lock:
                _last_real_hwnd = real
            return real

        with _last_real_lock:
            return _last_real_hwnd
    except Exception as e:
        print(f"[SCAN] Hwnd err: {e}")
        return None


def _walk_z_order(start_hwnd, skip_classes, skip_titles):
    """Walk Z-order from start_hwnd downward to find the topmost REAL app window.
    This is much better than 'largest window' because it respects actual stacking."""
    import ctypes.wintypes
    GW_HWNDNEXT = 2

    hwnd = start_hwnd
    for _ in range(50):  # Safety limit
        hwnd = ctypes.windll.user32.GetWindow(hwnd, GW_HWNDNEXT)
        if not hwnd:
            break
        if not ctypes.windll.user32.IsWindowVisible(hwnd):
            continue

        # Skip our own overlay windows
        with _overlay_hwnds_lock:
            if int(hwnd) in _overlay_hwnds:
                continue

        title = _get_window_title(hwnd)
        if not title or len(title) < 2:
            continue

        cls = _get_window_class(hwnd)
        if cls in skip_classes:
            continue
        if any(s in title for s in skip_titles):
            continue

        # Check size — skip tiny windows
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w < 200 or h < 100:
            continue

        return hwnd

    # Fallback: find largest real window
    return _find_best_window(skip_classes, skip_titles)


def _find_best_window(skip_classes, skip_titles):
    """Enumerate all top-level windows and find the best app window."""
    import ctypes.wintypes

    best_hwnd = None
    results = []

    # Callback for EnumWindows
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

    def callback(hwnd, lparam):
        nonlocal results
        if not ctypes.windll.user32.IsWindowVisible(hwnd):
            return True

        # Skip our own overlay windows
        with _overlay_hwnds_lock:
            if int(hwnd) in _overlay_hwnds:
                return True

        title = _get_window_title(hwnd)
        if not title or len(title) < 2:
            return True

        cls = _get_window_class(hwnd)
        if cls in skip_classes:
            return True
        if any(s in title for s in skip_titles):
            return True

        # Get window rect to check size
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w < 200 or h < 100:  # Skip tiny windows
            return True

        results.append((hwnd, title, w * h))
        return True

    try:
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(callback), 0)
    except:
        pass

    if results:
        # Return the largest visible window (most likely the main app)
        results.sort(key=lambda x: -x[2])
        return results[0][0]
    return None


def _get_window_class(hwnd):
    """Get window class name from HWND."""
    try:
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
        return buf.value
    except:
        return ""


def get_element_at_cursor():
    """Get the UI element directly under the mouse cursor.
    Uses UIA's ElementFromPoint — instant, no scanning needed.
    """
    try:
        import comtypes.client
        uia = comtypes.client.CreateObject(
            "{ff48dba4-60ef-4201-aa87-54103eef594e}",
            interface=None
        )
        # IUIAutomation::ElementFromPoint
        pt = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        element = uia.ElementFromPoint(pt)
        if element:
            name = element.CurrentName or ""
            rect = element.CurrentBoundingRectangle
            return {
                "name": name,
                "x": (rect.left + rect.right) // 2,
                "y": (rect.top + rect.bottom) // 2,
                "w": rect.right - rect.left,
                "h": rect.bottom - rect.top,
                "type": _control_type_name(element.CurrentControlType),
                "automationId": element.CurrentAutomationId or "",
            }
    except Exception as e:
        print(f"[SCAN] ElementFromPoint err: {e}")
    return None


def find_element_by_name(elements, name, fuzzy=True):
    """Find an element by name from a pre-scanned list.

    Args:
        elements: List from scan_ui_elements()
        name:     Name to search for
        fuzzy:    If True, partial match is allowed

    Returns:
        The matching element dict, or None
    """
    name_lower = name.lower()
    best = None
    best_score = 0

    for el in elements:
        el_name = el.get("name", "").lower()
        if not el_name:
            continue

        if el_name == name_lower:
            return el  # Exact match — return immediately

        if fuzzy:
            # Score by how many words match
            words = [w for w in name_lower.split() if len(w) > 2]
            if words:
                matches = sum(1 for w in words if w in el_name)
                score = matches / len(words)
                if score > best_score:
                    best_score = score
                    best = el

    return best if best_score >= 0.5 else None


def format_elements(elements):
    """Format element list as structured text for the AI prompt.
    Includes bounding rect info for precise cursor placement.
    """
    if not elements:
        return ""

    lines = ["CLICKABLE ELEMENTS (exact pixel positions from Accessibility API):"]
    for el in elements:
        if el.get("type") == "info":
            lines.append(f"  [{el['name']}]")
        else:
            extra = ""
            if el.get("value"):
                extra = f' value="{el["value"][:30]}"'
            if el.get("automationId"):
                extra += f' autoId="{el["automationId"][:25]}"'
            lines.append(
                f'  [{el["id"]}] "{el["name"]}" '
                f'at x={el["x"]}, y={el["y"]} '
                f'size={el.get("w", 0)}x{el.get("h", 0)} '
                f'({el["type"]}){extra}'
            )
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
#  LIVE WATCHER — Background thread that continuously scans
# ══════════════════════════════════════════════════════════════

class UIWatcher:
    """Continuously scans UI elements in a background thread.
    Call start() to begin, stop() to end.
    Access latest elements via .elements property.
    
    Optimization: Taskbar is scanned every 5th cycle (it barely changes).
    Window elements are scanned every cycle.
    """
    def __init__(self, interval=1.0, on_update=None):
        self._interval = interval
        self._on_update = on_update  # callback(elements)
        self._elements = []
        self._taskbar_cache = []  # Taskbar elements (cached, refreshed rarely)
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._cycle = 0
        self._last_count = 0

    @property
    def elements(self):
        with self._lock:
            return list(self._elements)

    def start(self):
        if self._running:
            return
        self._running = True
        self._cycle = 0
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[WATCHER] Started continuous UI scanning", flush=True)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        self._thread = None
        print("[WATCHER] Stopped", flush=True)

    def _loop(self):
        while self._running:
            try:
                t0 = time.perf_counter()
                self._cycle += 1

                # Taskbar: scan every 5th cycle (it rarely changes)
                scan_taskbar = (self._cycle % 5 == 1) or not self._taskbar_cache

                # CRITICAL: Find the REAL foreground window (skip our overlay)
                target = get_foreground_hwnd()

                new_elements = scan_ui_elements(
                    target_hwnd=target,
                    include_taskbar=scan_taskbar,
                    max_depth=4  # Balanced: fast scans, still catches most elements
                )

                # If we skipped taskbar scan, merge cached taskbar with new window elements
                if not scan_taskbar and self._taskbar_cache:
                    new_elements = self._taskbar_cache + [
                        e for e in new_elements
                        if e.get("type") not in ("taskbar", "tray", "tray_overflow")
                    ]
                    # Re-assign IDs
                    for i, el in enumerate(new_elements):
                        el["id"] = i
                else:
                    # Cache taskbar elements
                    self._taskbar_cache = [
                        e for e in new_elements
                        if e.get("type") in ("taskbar", "tray", "tray_overflow")
                    ]

                elapsed = (time.perf_counter() - t0) * 1000

                with self._lock:
                    self._elements = new_elements

                if self._on_update:
                    self._on_update(new_elements)

                # Only log when count changes (reduce spam)
                if len(new_elements) != self._last_count:
                    print(f"[WATCHER] {len(new_elements)} elements ({elapsed:.0f}ms) {'[+taskbar]' if scan_taskbar else '[cached taskbar]'}", flush=True)
                    self._last_count = len(new_elements)

            except Exception as e:
                print(f"[WATCHER] Error: {e}", flush=True)

            time.sleep(self._interval)


# ══════════════════════════════════════════════════════════════
#  INTERNAL SCANNING
# ══════════════════════════════════════════════════════════════

def _get_window_title(hwnd):
    """Get window title from HWND using Win32 API."""
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _scan_taskbar():
    """Scan Windows taskbar: pinned apps, running apps, system tray, clock."""
    items = []
    try:
        desktop = _get_desktop()

        # Main taskbar
        taskbar = desktop.window(class_name="Shell_TrayWnd")
        if not taskbar.exists():
            return items

        # Buttons (Start, Search, etc.) + ListItems (pinned/running apps)
        for ctrl_type in ("Button", "ListItem"):
            try:
                children = taskbar.descendants(control_type=ctrl_type)
                for child in children:
                    el = _extract_element(child, "taskbar")
                    if el:
                        items.append(el)
            except:
                continue

        # System tray
        try:
            tray = taskbar.child_window(class_name="TrayNotifyWnd")
            if tray.exists():
                for child in tray.descendants(control_type="Button"):
                    el = _extract_element(child, "tray")
                    if el:
                        items.append(el)
        except:
            pass

        # Notification area (overflow)
        try:
            overflow = desktop.window(class_name="NotifyIconOverflowWindow")
            if overflow.exists() and overflow.is_visible():
                for child in overflow.descendants(control_type="Button"):
                    el = _extract_element(child, "tray_overflow")
                    if el:
                        items.append(el)
        except:
            pass

    except Exception as e:
        print(f"[SCAN] Taskbar error: {e}", flush=True)
    return items


def _scan_desktop():
    """Scan desktop icons (shortcuts, files on desktop).
    Desktop icons live in Progman -> SHELLDLL_DefView -> FolderView (SysListView32).
    The Accessibility API exposes them as ListItems.
    """
    items = []
    try:
        desktop = _get_desktop()

        # Try Progman first (standard desktop)
        progman = None
        try:
            progman = desktop.window(class_name="Progman")
            if not progman.exists():
                progman = None
        except:
            pass

        # If Progman doesn't have icons, try WorkerW (Windows 11 sometimes uses this)
        if not progman:
            try:
                progman = desktop.window(class_name="WorkerW")
            except:
                pass

        if not progman or not progman.exists():
            return items

        # Get all ListItems (desktop icons)
        try:
            list_items = progman.descendants(control_type="ListItem", depth=5)
            for item in list_items:
                try:
                    name = item.window_text()
                    if not name or len(name) < 2:
                        continue

                    rect = item.rectangle()
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top
                    if w < 5 or h < 5:
                        continue

                    cx = (rect.left + rect.right) // 2
                    cy = (rect.top + rect.bottom) // 2

                    if cx < 0 or cy < 0:
                        continue

                    items.append({
                        "name": name[:80],
                        "x": cx,
                        "y": cy,
                        "w": w,
                        "h": h,
                        "type": "desktop_icon",
                        "automationId": "",
                        "isEnabled": True,
                        "value": "",
                    })
                except:
                    continue
        except:
            pass

    except Exception as e:
        print(f"[SCAN] Desktop error: {e}", flush=True)
    return items


def _scan_window(target_hwnd=None, max_depth=8):
    """Scan the active window's entire UI tree for interactive elements."""
    items = []
    try:
        desktop = _get_desktop()

        # Use get_foreground_hwnd() to skip our overlay and find the real app
        hwnd = target_hwnd or get_foreground_hwnd() or ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return items

        try:
            win = desktop.window(handle=hwnd)
            if not win.exists():
                return items

            title = win.window_text()
            if not title:
                return items
            # Skip our own overlay windows
            if "Assistly" in title or "AI Cursor" in title:
                return items

            rect = win.rectangle()
            items.append({
                "name": f"Window: {title}",
                "x": (rect.left + rect.right) // 2,
                "y": rect.top + 15,
                "w": rect.width(),
                "h": rect.height(),
                "type": "info",
                "automationId": "",
                "isEnabled": True,
                "value": "",
            })

            # ── Scan all interactive control types ──
            # (type_name, max_count) — tight limits for SPEED
            control_types = [
                ("Button",      20),
                ("MenuItem",    15),
                ("TabItem",     12),
                ("Edit",        10),   # Address bars, search boxes, text fields
                ("Hyperlink",    8),   # Clickable links
                ("ComboBox",     6),   # Dropdowns
                ("ListItem",    12),   # List items
                ("TreeItem",     8),   # Tree nodes
                ("CheckBox",     6),   # Checkboxes
                ("RadioButton",  6),   # Radio buttons
                ("Slider",       3),   # Sliders
                ("SplitButton",  6),   # Split buttons (e.g. "Save ▼")
                ("DataItem",     6),   # Data grid items
            ]

            seen_positions = set()

            for ctrl_type, limit in control_types:
                try:
                    children = win.descendants(
                        control_type=ctrl_type,
                        depth=max_depth
                    )
                    count = 0
                    for child in children:
                        if count >= limit:
                            break
                        el = _extract_element(child, ctrl_type.lower(), seen_positions)
                        if el:
                            items.append(el)
                            count += 1
                except:
                    continue

        except Exception as e:
            print(f"[SCAN] Window scan err: {e}", flush=True)

    except Exception as e:
        print(f"[SCAN] Window error: {e}", flush=True)
    return items


def _extract_element(child, element_type, seen_positions=None):
    """Extract a single UI element's properties from a pywinauto wrapper.
    Returns None if the element is invalid/invisible/duplicate.
    """
    try:
        name = child.window_text()

        # Fallback to automation_id if no visible text
        if not name or len(name) < 2:
            try:
                name = child.element_info.name or child.element_info.automation_id
            except:
                pass

        if not name or len(name) < 2:
            return None

        rect = child.rectangle()
        w = rect.right - rect.left
        h = rect.bottom - rect.top

        # Skip tiny or off-screen elements
        if w < 5 or h < 5:
            return None

        cx = (rect.left + rect.right) // 2
        cy = (rect.top + rect.bottom) // 2

        if cx < 0 or cy < 0:
            return None

        # Dedup by position (5px tolerance grid)
        if seen_positions is not None:
            pos_key = (cx // 5, cy // 5)
            if pos_key in seen_positions:
                return None
            seen_positions.add(pos_key)

        # Semantic type mapping
        type_map = {
            "edit": "textfield",
            "combobox": "dropdown",
            "hyperlink": "link",
            "checkbox": "checkbox",
            "radiobutton": "radio",
            "slider": "slider",
            "splitbutton": "button",
            "toolbar": "toolbar",
            "dataitem": "data",
        }
        semantic_type = type_map.get(element_type, element_type)

        # Get value for text fields
        value = ""
        if element_type in ("edit", "textfield"):
            try:
                value = child.get_value() or ""
            except:
                pass

        # Check enabled state
        is_enabled = True
        try:
            is_enabled = child.is_enabled()
        except:
            pass

        # Get automation ID
        auto_id = ""
        try:
            auto_id = child.element_info.automation_id or ""
        except:
            pass

        return {
            "name": name[:80],
            "x": cx,
            "y": cy,
            "w": w,
            "h": h,
            "type": semantic_type,
            "automationId": auto_id[:30],
            "isEnabled": is_enabled,
            "value": value[:50] if value else "",
        }
    except:
        return None


def _deduplicate(elements):
    """Remove duplicate elements by position AND name similarity."""
    seen = {}
    deduped = []
    for el in elements:
        # Key: position grid (5px) + first 20 chars of name
        key = (el.get("x", 0) // 5, el.get("y", 0) // 5, el.get("name", "")[:20].lower())
        if key not in seen:
            seen[key] = True
            deduped.append(el)
    return deduped


def _control_type_name(type_id):
    """Convert UIA ControlTypeId to human-readable name."""
    names = {
        50000: "button", 50001: "calendar", 50002: "checkbox",
        50003: "combobox", 50004: "edit", 50005: "hyperlink",
        50006: "image", 50007: "listitem", 50008: "list",
        50009: "menu", 50010: "menubar", 50011: "menuitem",
        50012: "progressbar", 50013: "radiobutton", 50014: "scrollbar",
        50015: "slider", 50016: "spinner", 50017: "statusbar",
        50018: "tab", 50019: "tabitem", 50020: "text",
        50021: "toolbar", 50022: "tooltip", 50023: "tree",
        50024: "treeitem", 50025: "custom", 50026: "group",
        50027: "thumb", 50028: "datagrid", 50029: "dataitem",
        50030: "document", 50031: "splitbutton", 50032: "window",
        50033: "pane", 50034: "header", 50035: "headeritem",
        50036: "table", 50037: "titlebar", 50038: "separator",
    }
    return names.get(type_id, "unknown")


# ══════════════════════════════════════════════════════════════
#  CLI TEST — run `python ui_scanner.py` to see what's on screen
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    print("=" * 60)
    print("  Assistly UI Scanner v2 - Accessibility API Test")
    print("=" * 60)

    t0 = time.perf_counter()
    elements = scan_ui_elements()
    elapsed = (time.perf_counter() - t0) * 1000

    print(f"\nScanned {len(elements)} elements in {elapsed:.0f}ms\n")

    # Sanitize for console output
    for el in elements:
        el["name"] = el.get("name", "").encode("ascii", "replace").decode("ascii")

    print(format_elements(elements))
    print()

    # Show summary by type
    types = {}
    for el in elements:
        t = el.get("type", "unknown")
        types[t] = types.get(t, 0) + 1
    print("Summary by type:")
    for t, c in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")
