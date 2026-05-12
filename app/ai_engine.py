"""
Assistly - AI Engine.
Smart AI teacher that knows every software inside out.
Guides with personality, tips, shortcuts, and deep expertise.
"""
import os
import io
import json
import re
import base64
import traceback
from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv
from ui_scanner import format_elements

load_dotenv()

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

SYSTEM_PROMPT = """You are Overlay — a brilliant, confident AI mentor living on the user's desktop. You are an expert in EVERY software application.
You can SEE the user's screen. You must analyze the visual context and combine it with the provided UI element list to guide the user.
Screen: {w}x{h} pixels.

PERSONALITY & KNOWLEDGE:
- You know every app deeply (Chrome, VS Code, Photoshop, Premiere, Blender, etc.). Give pro tips, shortcuts, and expert advice.
- You're witty, direct, and a little cocky (in a charming way). Talk like a chill tech-savvy friend.
- Use natural language: "Yo, hit that button right there" not "Please click the button."
- Keep it SHORT — max 2 punchy sentences. No essays.
- Throw in occasional emoji but don't overdo it 🎯

{elements}

FORMAT: [id] "name" at x,y size=WxH (type)
- id = element ID from Windows Accessibility API. Use this for precise targeting!
- "Window: ..." = the app currently open

MODES:
1. TEACHER (default): Analyze the screen, point to the right element using `guide`, and give a quick tip.
2. AGENT: If user says "do it for me" or similar, use `agent_action` to click/type autonomously.

RULES:
- ALWAYS use element `id` when available. Only guess raw x,y coordinates if the element isn't in the list.
- You MUST output ONLY raw, valid JSON. DO NOT wrap it in markdown blockquotes (` ```json `).
- DO NOT output any conversational text before or after the JSON. Place your verbal response inside the `"message"` field.
- If you want to guide the user, provide the `guide` object. Otherwise, set it to `null`.

{{"message": "your spoken response", "guide": {{"id": N, "label": "short label"}} or null, "agent_action": {{"type": "click"|"type"|"hover", "id": N}} or null, "status": "in_progress"|"complete"}}"""


class AIEngine:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.vision_model = os.getenv("VISION_MODEL", "gemini-2.5-pro")
        self.text_model = os.getenv("TEXT_MODEL", "gemini-2.5-pro")
        self.client = None
        self.history = []
        self._screen_w = 1920
        self._screen_h = 1080
        self._init_client()

    def _init_client(self):
        if self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key, base_url=GEMINI_BASE_URL)
                print(f"[AI] Gemini ready | {self.vision_model}", flush=True)
            except Exception as e:
                print(f"[AI] Init error: {e}", flush=True)
                self.client = None

    def set_api_key(self, key):
        self.api_key = key
        os.environ["GEMINI_API_KEY"] = key
        self._init_client()

    def set_screen_size(self, w, h):
        self._screen_w = w
        self._screen_h = h

    def get_response(self, user_input, screenshot_path=None, ui_elements=None):
        """Get AI response. ui_elements should be pre-scanned from the correct window."""
        try:
            self.history.append({"role": "user", "content": user_input})
            if len(self.history) > 12:
                self.history = self.history[-12:]

            if self.client:
                result = self._call(user_input, screenshot_path, ui_elements)
            else:
                result = {"message": "Hey! I need a Gemini API key to work. Open Settings (⚙) and paste your key there. You can get one at aistudio.google.com 🔑", "guide": None, "status": "complete"}

            self.history.append({"role": "assistant", "content": result["message"]})
            print(f"[AI] => {result['message'][:80]}... guide={result.get('guide')} status={result.get('status')}", flush=True)
            return result
        except Exception as e:
            traceback.print_exc()
            return {"message": f"Error: {str(e)[:80]}", "guide": None, "status": "complete"}

    def _call(self, user_input, screenshot_path, ui_elements=None):
        try:
            import time as _time
            t0 = _time.perf_counter()

            has_img = screenshot_path and os.path.exists(screenshot_path)
            has_elements = ui_elements and len(ui_elements) > 3

            # ALWAYS use vision model if a screenshot is provided!
            # The user wants us to SEE the screen.
            if has_img:
                model = self.vision_model
                use_image = True
                print(f"[AI] VISION MODE: Analyzing screenshot + {len(ui_elements) if ui_elements else 0} elements", flush=True)
            elif has_elements:
                model = self.text_model  # Fast! No image processing, just elements
                use_image = False
                print(f"[AI] FAST MODE: {len(ui_elements)} elements only, no screenshot provided", flush=True)
            else:
                model = self.text_model
                use_image = False
                print(f"[AI] TEXT MODE: No image, no elements", flush=True)

            # Format pre-scanned elements
            elements_text = format_elements(ui_elements) if ui_elements else "No clickable elements detected — estimate positions from context."

            prompt = SYSTEM_PROMPT.format(
                w=self._screen_w, h=self._screen_h,
                elements=elements_text
            )
            messages = [{"role": "system", "content": prompt}]

            for msg in self.history[-6:]:
                if isinstance(msg.get("content"), str):
                    messages.append({"role": msg["role"], "content": msg["content"]})

            if use_image and has_img:
                b64 = self._encode(screenshot_path)
                user_msg = {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_input},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                    ]
                }
            else:
                user_msg = {"role": "user", "content": user_input}

            if messages[-1]["role"] == "user":
                messages[-1] = user_msg
            else:
                messages.append(user_msg)

            print(f"[AI] Calling {model}...", flush=True)
            # Use JSON schema via response_format if possible, otherwise rely on prompt
            try:
                resp = self.client.chat.completions.create(
                    model=model, messages=messages,
                    max_tokens=600, temperature=0.2,
                    response_format={"type": "json_object"}
                )
            except Exception:
                # Fallback if model doesn't support json_object
                resp = self.client.chat.completions.create(
                    model=model, messages=messages,
                    max_tokens=600, temperature=0.2,
                )
            raw = resp.choices[0].message.content.strip()
            elapsed = (_time.perf_counter() - t0) * 1000
            print(f"[AI] Response in {elapsed:.0f}ms | Raw: {raw[:150]}", flush=True)

            parsed = self._parse(raw)

            # Snap cursor to nearest real element for accuracy
            if parsed.get("guide") and ui_elements:
                parsed["guide"] = self._snap_to_element(parsed["guide"], ui_elements)
            
            if parsed.get("agent_action") and ui_elements and parsed["agent_action"].get("type") in ["click", "hover"]:
                parsed["agent_action"] = self._snap_action_to_element(parsed["agent_action"], ui_elements)

            return parsed

        except Exception as e:
            print(f"[AI] Error: {e}", flush=True)
            return {"message": f"Hmm, ran into an issue: {str(e)[:80]}. Try again?", "guide": None, "status": "complete"}

    def _snap_to_element(self, guide, elements):
        """Resolve guide coordinates. ID-based lookup is preferred (100% accurate)."""
        # Priority 1: ID-based lookup (from Accessibility API)
        if "id" in guide:
            eid = guide["id"]
            for el in elements:
                if el.get("id") == eid:
                    print(f"[SNAP] ID {eid} -> '{el['name']}' ({el['x']},{el['y']})", flush=True)
                    return {"x": el["x"], "y": el["y"], "label": guide.get("label", el["name"][:20])}
            print(f"[SNAP] ID {eid} not found in {len(elements)} elements", flush=True)

        # Priority 2: If we have x,y coordinates, try to snap to nearest element
        ax = float(guide.get("x", 0))
        ay = float(guide.get("y", 0))
        label = guide.get("label", "Click")

        if ax == 0 and ay == 0:
            # No valid coordinates — can't snap
            return guide

        best_dist = 999999
        best_el = None

        for el in elements:
            if el.get("type") == "info":
                continue
            ex, ey = el["x"], el["y"]
            dist = ((ax - ex) ** 2 + (ay - ey) ** 2) ** 0.5

            # Check name similarity
            name_lower = el.get("name", "").lower()
            label_lower = str(label).lower()
            words = [w for w in label_lower.split() if len(w) > 2]
            name_match = any(w in name_lower for w in words) if words else False

            if name_match and dist < 600:
                if dist < best_dist:
                    best_dist = dist
                    best_el = el
            elif dist < 150:
                if dist < best_dist:
                    best_dist = dist
                    best_el = el

        if best_el:
            print(f"[SNAP] '{label}' ({ax},{ay}) -> '{best_el['name']}' ({best_el['x']},{best_el['y']})", flush=True)
            return {"x": best_el["x"], "y": best_el["y"], "label": label}

        return guide

    def _snap_action_to_element(self, action, elements):
        """Resolve agent_action coordinates using element ID."""
        if "id" in action:
            eid = action["id"]
            for el in elements:
                if el.get("id") == eid:
                    action["x"] = el["x"]
                    action["y"] = el["y"]
                    print(f"[SNAP] Action ID {eid} -> '{el['name']}' ({el['x']},{el['y']})", flush=True)
                    return action
        # If no ID, try positional snap
        snapped = self._snap_to_element(action, elements)
        action["x"] = snapped.get("x", action.get("x", 0))
        action["y"] = snapped.get("y", action.get("y", 0))
        return action

    def _encode(self, path):
        """Full resolution JPEG."""
        try:
            img = Image.open(path).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            kb = len(buf.getvalue()) / 1024
            print(f"[AI] Screenshot: {img.width}x{img.height} ({kb:.0f}KB)", flush=True)
            return base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            print(f"[AI] Encode err: {e}", flush=True)
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()

    def _parse(self, raw):
        try:
            clean = raw.strip()
            # Strip markdown code blocks
            if "```" in clean:
                m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', clean, re.DOTALL)
                if m: clean = m.group(1).strip()
            # Extract JSON object
            m = re.search(r'\{.*\}', clean, re.DOTALL)
            if m: clean = m.group(0)

            data = json.loads(clean)
            msg = str(data.get("message", raw))
            guide = data.get("guide", None)
            agent_action = data.get("agent_action", None)
            status = data.get("status", "complete")

            # Process guide — keep ID-based guides intact!
            if guide and isinstance(guide, dict):
                has_id = "id" in guide
                has_xy = "x" in guide and "y" in guide

                if has_id:
                    # ID-based guide: pass through to _snap_to_element
                    # Don't mangle coordinates — snap will resolve them from element ID
                    label_val = guide.get("label", "Here")
                    guide = {"id": guide["id"], "label": str(label_val)}
                elif has_xy:
                    # Coordinate-based guide: normalize coordinates
                    x = float(guide.get("x", 0))
                    y = float(guide.get("y", 0))
                    if 0 < x <= 1.0:
                        x = x * self._screen_w
                    if 0 < y <= 1.0:
                        y = y * self._screen_h
                    x = max(5, min(int(x), self._screen_w - 5))
                    y = max(5, min(int(y), self._screen_h - 5))
                    label_val = guide.get("label", "Here")
                    if label_val and str(label_val).lower() != "none":
                        guide = {"x": x, "y": y, "label": str(label_val)}
                    else:
                        guide = None
                else:
                    guide = None
            else:
                guide = None

            return {"message": msg, "guide": guide, "agent_action": agent_action, "status": status}
        except Exception as e:
            print(f"[AI] Parse err: {e}", flush=True)
            fallback = raw
            if "{" in fallback:
                fallback = fallback[:fallback.index("{")].strip()
            if not fallback:
                fallback = raw[:200]
            return {"message": fallback, "guide": None, "status": "complete"}

    def clear_history(self):
        self.history.clear()
