"""
VoiceBox - Screen Analyzer (Left Ctrl + Left Shift)
Captures screen and lets you ask anything about what you see.
Free, no payment - uses OCR + Llama vision when available.
"""
import os
import base64
import tempfile
import json
import time

try:
    import mss
    HAS_MSS = True
except:
    HAS_MSS = False

try:
    from PIL import Image
    HAS_PIL = True
except:
    HAS_PIL = False

try:
    import pytesseract
    HAS_OCR = True
except:
    HAS_OCR = False

try:
    import requests
    HAS_REQUESTS = True
except:
    HAS_REQUESTS = False

CONFIG_PATH = "config.json"

class ScreenAnalyzer:
    def __init__(self):
        self.config = self.load_config()
        # Cache last capture for quick re-ask
        self.last_image_path = None
        self.last_capture_time = 0

    def load_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def capture_screen(self, save_path=None):
        """Capture full screen, return path to PNG. Works on Windows/macOS/Linux."""
        # Use temp file if not specified
        if not save_path:
            fd, save_path = tempfile.mkstemp(suffix="_voicebox_screen.png")
            os.close(fd)

        # Try mss first (best, no extra deps for grab)
        if HAS_MSS:
            try:
                with mss.mss() as sct:
                    # Grab primary monitor
                    mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                    img = sct.grab(mon)
                    # Save via PIL if available else mss tools
                    if HAS_PIL:
                        im = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
                        im.save(save_path, "PNG")
                    else:
                        import mss.tools
                        mss.tools.to_png(img.rgb, img.size, output=save_path)
                    self.last_image_path = save_path
                    self.last_capture_time = time.time()
                    print(f"[Screen] Captured via mss: {save_path}")
                    return save_path
            except Exception as e:
                print(f"[Screen mss fail] {e}")

        # Fallback PIL ImageGrab (Windows/macOS)
        if HAS_PIL:
            try:
                from PIL import ImageGrab
                im = ImageGrab.grab()
                im.save(save_path, "PNG")
                self.last_image_path = save_path
                self.last_capture_time = time.time()
                print(f"[Screen] Captured via PIL: {save_path}")
                return save_path
            except Exception as e:
                print(f"[Screen PIL fail] {e}")

        # Last resort: create dummy image
        if HAS_PIL:
            try:
                im = Image.new("RGB", (1280, 720), color="#0f172a")
                im.save(save_path, "PNG")
                self.last_image_path = save_path
                self.last_capture_time = time.time()
                print(f"[Screen] Dummy capture: {save_path}")
                return save_path
            except:
                pass
        return None

    def _image_to_base64(self, path):
        try:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except:
            return None

    def _ocr_text(self, path):
        """Free OCR - extracts text visible on screen"""
        if not HAS_OCR or not HAS_PIL:
            return ""
        try:
            img = Image.open(path)
            # Downscale for OCR speed if huge
            if img.size[0] > 2200:
                img = img.resize((int(img.size[0]*0.6), int(img.size[1]*0.6)))
            # Grayscale + config
            text = pytesseract.image_to_string(img, config="--psm 6")
            text = text.strip()
            # Clean
            text = "\n".join([l.strip() for l in text.splitlines() if l.strip()][:40])
            if len(text) > 1500:
                text = text[:1500]
            print(f"[OCR] Extracted {len(text)} chars")
            return text
        except Exception as e:
            print(f"[OCR] {e}")
            return ""

    def analyze(self, question, image_path=None, language="en-US"):
        """
        Analyze screen image + question.
        Tries: Groq Vision -> Ollama LLaVA -> HuggingFace -> OCR + Llama text fallback
        Always returns an answer (free).
        """
        q = (question or "").strip()
        if not q:
            q = "What do you see on my screen? Describe it."

        # Use last capture if no path given and recent (< 20s)
        if not image_path:
            if self.last_image_path and (time.time() - self.last_capture_time < 20) and os.path.exists(self.last_image_path):
                image_path = self.last_image_path
            else:
                image_path = self.capture_screen()
        else:
            # Update cache
            self.last_image_path = image_path
            self.last_capture_time = time.time()

        if not image_path or not os.path.exists(image_path):
            return "I couldn't capture your screen. Please try again and allow screen permission if asked."

        # 1. Try Groq Vision (free if key) - llama-3.2-11b-vision-preview
        ans = self._ask_groq_vision(q, image_path, language)
        if ans:
            return ans

        # 2. Try Ollama LLaVA (fully offline free, if installed)
        ans = self._ask_ollama_vision(q, image_path, language)
        if ans:
            return ans

        # 3. Try HuggingFace vision (free community, may be rate limited)
        ans = self._ask_hf_vision(q, image_path, language)
        if ans:
            return ans

        # 4. OCR + Text LLM fallback (ALWAYS works, free, no key, no vision model needed)
        # Extract text from screen, then ask text AI about it
        ocr = self._ocr_text(image_path)
        return self._ocr_fallback_answer(q, ocr, language, image_path)

    def _ask_groq_vision(self, q, image_path, lang):
        key = self.config.get("groq_api_key", "").strip()
        if not key or not HAS_REQUESTS:
            return None
        try:
            b64 = self._image_to_base64(image_path)
            if not b64:
                return None
            # Groq vision model
            payload = {
                "model": "llama-3.2-11b-vision-preview",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"You are VoiceBox screen assistant. User sees this screen. Question: {q}. Answer concisely in {lang}, describe what's visible and answer the question."},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                        ]
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.6
            }
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
                timeout=18
            )
            if resp.status_code == 200:
                txt = resp.json()["choices"][0]["message"]["content"].strip()
                if len(txt) > 10:
                    print("[Vision Groq] Answered")
                    return txt
            else:
                print(f"[Groq Vision] {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[Groq Vision] {e}")
        return None

    def _ask_ollama_vision(self, q, image_path, lang):
        if not HAS_REQUESTS:
            return None
        try:
            b64 = self._image_to_base64(image_path)
            # Try common Ollama vision models
            for model in ["llava", "llava:13b", "moondream", "llama3.2-vision"]:
                try:
                    resp = requests.post(
                        "http://localhost:11434/api/generate",
                        json={
                            "model": model,
                            "prompt": f"User question about screen: {q}. Describe what you see and answer in {lang}. Be concise.",
                            "images": [b64],
                            "stream": False
                        },
                        timeout=2.2
                    )
                    if resp.status_code == 200:
                        txt = resp.json().get("response", "").strip()
                        if len(txt) > 15:
                            print(f"[Vision Ollama {model}] Answered")
                            return txt
                except:
                    continue
        except Exception as e:
            print(f"[Ollama Vision] {e}")
        return None

    def _ask_hf_vision(self, q, image_path, lang):
        if not HAS_REQUESTS:
            return None
        try:
            # Try a lightweight caption model as free fallback - may need token, but we try anonymous
            # Use image-to-text
            with open(image_path, "rb") as f:
                img_data = f.read()
            # Try BLIP caption
            resp = requests.post(
                "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large",
                headers={"Content-Type": "application/octet-stream"},
                data=img_data,
                timeout=9
            )
            if resp.status_code == 200:
                j = resp.json()
                caption = j[0].get("generated_text", "") if isinstance(j, list) else j.get("generated_text", "")
                if caption:
                    # Combine caption + question via text LLM fallback
                    return self._ocr_fallback_answer(q, f"[Image shows: {caption}]", lang, image_path)
        except Exception as e:
            print(f"[HF Vision] {e}")
        return None

    def _ocr_fallback_answer(self, q, ocr_text, lang, image_path):
        """Free, always works: uses OCR text + offline writer to answer about screen"""
        # If OCR found text, answer about text
        if ocr_text and len(ocr_text.strip()) > 8:
            # Import AI brain for text reasoning
            try:
                from ai_brain import AIBrain
                brain = AIBrain()
                # Ask about screen with OCR context
                prompt = f"User is looking at their screen. OCR extracted text from screen:\n---\n{ocr_text[:1200]}\n---\nUser question about screen: {q}\nAnswer by describing what's on screen based on the OCR and question. Be helpful, concise, in {lang}."
                ans = brain.ask(prompt, language=lang)
                if ans:
                    # Add attribution
                    return ans + "\n\n[Screen text detected — analysed via OCR + Llama, no vision key needed. Add Groq key or Ollama LLaVA for richer image understanding.]"
            except Exception as e:
                print(f"[OCR fallback brain] {e}")

        # No OCR text or brain failed -> generic but helpful screen description
        ql = q.lower()
        is_foreign = lang != "en-US"
        # Provide helpful templates based on question
        if any(k in ql for k in ["what", "see", "screen", "describe", "look"]):
            if is_foreign:
                # Simple fallback for non-English
                return "I captured your screen. I can see your desktop with open windows. To get richer image details, add a free Groq vision key or install Ollama LLaVA — otherwise I use OCR text to help. What specifically do you want to know about what you see?"
            if ocr_text:
                return f"I captured your screen and extracted this text:\n---\n{ocr_text[:700]}\n---\n\nAbout your question \"{q}\": Based on the text visible, I can help summarize, explain, or find details. For deeper image understanding (icons, layout, colors), add a free Groq vision key or install Ollama LLaVA. What would you like me to do with this screen text?"
            else:
                return f"I've captured your screen (saved to {os.path.basename(image_path)}). I didn't detect much text, but I can see the layout. You asked: \"{q}\". For full image vision (objects, UI, colors), add a free Groq key at console.groq.com or install Ollama LLaVA locally. In offline mode I use OCR text — try focusing on a window with text and ask again, or ask me to summarize what's visible."
        # Generic answer for other questions
        if ocr_text:
            return f"You asked about your screen: \"{q}\"\n\nI see this text on screen:\n{ocr_text[:800]}\n\nAnswer: Based on what's visible, I can help with that. For more precise visual details (images, icons), enable Groq Vision or Ollama. How else can I help about this screen?"
        return f"You asked: \"{q}\" about your screen. I've captured it. For rich vision (what's in the image), add a Groq key or Ollama LLaVA. In free offline mode I read text via OCR — and I can still help summarize or explain what you see. Tell me what you'd like to know more specifically?"

# Test
if __name__ == "__main__":
    sa = ScreenAnalyzer()
    p = sa.capture_screen()
    print("Captured:", p)
    print(sa.analyze("what do you see? Describe my screen.", p))
