"""
OverlayOS - Groq AI Engine with UI Automation.
Screenshot for visual context + exact element positions from Windows API.
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
from ui_scanner import scan_ui_elements, format_elements

load_dotenv()

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

SYSTEM_PROMPT = """You are OverlayOS, an expert AI guide that sees the user's screen and knows every software.

Screen: {w}x{h} pixels. You have a screenshot AND a list of actual clickable elements with exact positions.

{elements}

YOUR JOB:
1. Look at the screenshot to understand what's happening on screen
2. Check the CLICKABLE ELEMENTS list for exact positions
3. If the element the user needs is in the list, USE THOSE EXACT coordinates
4. If it's not in the list, estimate from the screenshot

JSON only:
{{"message": "what to do", "guide": {{"x": 500, "y": 1060, "label": "Click here"}}, "status": "in_progress"}}

- x,y = pixel position. guide=null if no pointing needed.
- status = "in_progress" if there are more steps after this, "complete" if the goal is fully achieved.

RULES:
1. PREFER coordinates from the CLICKABLE ELEMENTS list - they are pixel-perfect
2. Match element names flexibly (e.g. "Chrome" matches "Google Chrome - New Tab")
3. For taskbar: ALWAYS use list coordinates, never estimate
4. Describe what the user should do clearly
5. For multi-step tasks (like 'download an app' or 'color grade'), guide ONE step at a time. Return status: "in_progress". The system will wait for the user to complete the step, then automatically give you the new screen and ask for the next step. Only return "complete" when the final goal is achieved.
6. Be confident - never say "try" or "I think"
7. 1-2 sentences. JSON only."""


class AIEngine:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "")
        self.vision_model = os.getenv("VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
        self.text_model = os.getenv("TEXT_MODEL", "llama-3.3-70b-versatile")
        self.client = None
        self.history = []
        self._screen_w = 1920
        self._screen_h = 1080
        self._init_client()

    def _init_client(self):
        if self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key, base_url=GROQ_BASE_URL)
                print(f"[AI] Groq ready | {self.vision_model}", flush=True)
            except Exception as e:
                print(f"[AI] Init error: {e}", flush=True)
                self.client = None

    def set_api_key(self, key):
        self.api_key = key
        os.environ["GROQ_API_KEY"] = key
        self._init_client()

    def set_screen_size(self, w, h):
        self._screen_w = w
        self._screen_h = h

    def get_response(self, user_input, screenshot_path=None):
        try:
            self.history.append({"role": "user", "content": user_input})
            if len(self.history) > 8:
                self.history = self.history[-8:]

            if self.client:
                result = self._call(user_input, screenshot_path)
            else:
                result = {"message": "Add your Groq API key in Settings!", "guide": None}

            self.history.append({"role": "assistant", "content": result["message"]})
            print(f"[AI] => {result['message'][:60]}... guide={result.get('guide')}", flush=True)
            return result
        except Exception as e:
            traceback.print_exc()
            return {"message": f"Error: {str(e)[:80]}", "guide": None}

    def _call(self, user_input, screenshot_path):
        try:
            has_img = screenshot_path and os.path.exists(screenshot_path)
            model = self.vision_model if has_img else self.text_model

            # Scan real UI element positions
            elements = scan_ui_elements()
            elements_text = format_elements(elements)
            if elements_text:
                print(f"[SCAN] Found {len(elements)} elements", flush=True)

            prompt = SYSTEM_PROMPT.format(
                w=self._screen_w, h=self._screen_h,
                elements=elements_text or "No elements detected."
            )
            messages = [{"role": "system", "content": prompt}]

            for msg in self.history[-4:]:
                if isinstance(msg.get("content"), str):
                    messages.append({"role": msg["role"], "content": msg["content"]})

            if has_img:
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
            resp = self.client.chat.completions.create(
                model=model, messages=messages,
                max_tokens=200, temperature=0.2,
            )
            raw = resp.choices[0].message.content.strip()
            print(f"[AI] Raw: {raw[:150]}", flush=True)

            parsed = self._parse(raw)

            # Post-process: snap to nearest real element if close
            if parsed["guide"] and elements:
                parsed["guide"] = self._snap_to_element(parsed["guide"], elements)

            return parsed

        except Exception as e:
            print(f"[AI] Error: {e}", flush=True)
            return {"message": f"Error: {str(e)[:100]}", "guide": None}

    def _snap_to_element(self, guide, elements):
        """If AI coordinate is near a real element, snap to its exact position."""
        ax, ay = guide["x"], guide["y"]
        label = guide["label"]

        best_dist = 999999
        best_el = None

        for el in elements:
            if el["type"] == "info":
                continue
            ex, ey = el["x"], el["y"]
            dist = ((ax - ex) ** 2 + (ay - ey) ** 2) ** 0.5

            # Check if label matches element name
            name_lower = el["name"].lower()
            label_lower = label.lower()
            name_match = any(word in name_lower for word in label_lower.split() if len(word) > 2)

            if name_match and dist < 200:
                # Strong match: name matches and within 200px
                if dist < best_dist:
                    best_dist = dist
                    best_el = el
            elif dist < 60:
                # Weak match: just close proximity
                if dist < best_dist:
                    best_dist = dist
                    best_el = el

        if best_el:
            print(f"[SNAP] {guide['label']} ({ax},{ay}) -> {best_el['name']} ({best_el['x']},{best_el['y']})", flush=True)
            return {"x": best_el["x"], "y": best_el["y"], "label": guide["label"]}

        return guide

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
            if "```" in clean:
                m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', clean, re.DOTALL)
                if m: clean = m.group(1).strip()
            m = re.search(r'\{.*\}', clean, re.DOTALL)
            if m: clean = m.group(0)

            data = json.loads(clean)
            msg = str(data.get("message", raw))
            guide = data.get("guide", None)
            status = data.get("status", "complete")

            if guide and isinstance(guide, dict):
                x = float(guide.get("x", guide.get("x_pct", 0)))
                y = float(guide.get("y", guide.get("y_pct", 0)))
                if x <= 1.0:
                    x = x * self._screen_w
                if y <= 1.0:
                    y = y * self._screen_h
                x = max(5, min(int(x), self._screen_w - 5))
                y = max(5, min(int(y), self._screen_h - 5))
                guide = {"x": x, "y": y, "label": str(guide.get("label", "Here"))}
            else:
                guide = None

            return {"message": msg, "guide": guide, "status": status}
        except Exception as e:
            print(f"[AI] Parse err: {e}", flush=True)
            return {"message": raw, "guide": None, "status": "complete"}

    def clear_history(self):
        self.history.clear()
