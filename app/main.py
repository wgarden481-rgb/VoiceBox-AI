"""
VoiceBox AI - Main Background App (Smooth + Screen Analyze Edition)
Built by: Claude Sonnet 4.6 → GPT-5.2 High → Claude Final
Features:
- Runs in background / system tray
- Hotkey 1: Left CTRL + Left ALT -> Voice Q&A (middle-top box, spoken)
- Hotkey 2: Left CTRL + Left SHIFT -> Analyze Screen (capture + ask anything about what you see)
- Intro wizard, overlay fade, Gmail, history, etc.
Run: python main.py
"""
import json
import os
import sys
import time
import threading
import webbrowser
from pathlib import Path

try:
    from pynput import keyboard as pynput_keyboard
    HAS_PYNPUT = True
except:
    HAS_PYNPUT = False
    print("[Init] pynput not available, using keyboard fallback")

try:
    import keyboard as kb_lib
    HAS_KB = True
except:
    HAS_KB = False

from voice_engine import VoiceEngine
from ai_brain import AIBrain
from overlay import Overlay
import gmail_integration
try:
    from screen_analyzer import ScreenAnalyzer
    HAS_SCREEN = True
except:
    HAS_SCREEN = False
    print("[Init] screen_analyzer not available")

CONFIG_PATH = "config.json"
HISTORY_PATH = "history.json"

class VoiceBoxApp:
    def __init__(self):
        print("="*60)
        print(" VoiceBox AI - Starting (v3.3 Smooth + Screen)")
        print(" Claude Sonnet 4.6 → GPT-5.2 High → Claude Final")
        print("="*60)
        self.config = self.load_config()
        self.voice = VoiceEngine()
        self.brain = AIBrain()
        self.screen_analyzer = ScreenAnalyzer() if HAS_SCREEN else None
        self.overlay = None
        self.tray_icon = None
        self.is_listening = False
        self.is_screen_analyzing = False
        self.hotkey_pressed = False
        self.hotkey_screen_pressed = False

        self.left_ctrl_pressed = False
        self.left_alt_pressed = False
        self.left_shift_pressed = False

        self.setup_overlay()
        self.setup_tray()
        self.setup_hotkey()

        # Internet required for AI to work
        try:
            import requests
            requests.get("https://8.8.8.8", timeout=3)
        except:
            try:
                requests.get("https://www.google.com", timeout=3)
            except:
                print("[Net] No internet - AI will require internet to answer")
                # Show overlay warning after a moment
                def warn_no_net():
                    if self.overlay:
                        self.overlay.show_error("Internet required", "🌐 VoiceBox needs internet for AI to work (Groq Llama, Wikipedia, neural voices). Please connect to the internet.")
                    try:
                        self.voice.speak("Internet required for AI to work. Please connect to the internet.")
                    except: pass
                threading.Timer(2.0, warn_no_net).start()

        if not self.config.get("intro_completed", False):
            print("[Intro] First run detected - showing intro wizard...")
            threading.Timer(0.8, self.show_intro_wizard).start()

    def load_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"intro_completed": False, "language": "en-US", "overlay_duration_seconds": 9}

    def save_config(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    def setup_overlay(self):
        self.overlay = Overlay(self.config)

    def setup_tray(self):
        try:
            from pystray import Icon, Menu, MenuItem
            from PIL import Image, ImageDraw
            def create_image():
                img = Image.new('RGBA', (64, 64), (0,0,0,0))
                d = ImageDraw.Draw(img)
                d.ellipse([8,8,56,56], fill="#0f172a")
                d.ellipse([22,22,42,42], fill="white")
                d.text((22, 18), "V", fill="#0f172a")
                return img
            menu = Menu(
                MenuItem('Test: Ask Anything', lambda: self.test_overlay()),
                MenuItem('Test: Analyze Screen', lambda: self.test_screen_analyze()),
                MenuItem('Settings (Intro)', lambda: self.show_intro_wizard()),
                MenuItem('Test Voice', lambda: threading.Thread(target=lambda: self.voice.test_voice(), daemon=True).start()),
                MenuItem('Gmail: ' + gmail_integration.get_status()[1][:28], self.on_gmail_click),
                MenuItem('History', lambda: self.show_history()),
                Menu.SEPARATOR,
                MenuItem('Quit VoiceBox', lambda: self.quit_app())
            )
            self.tray_icon = Icon("VoiceBox", create_image(), "VoiceBox • Ctrl+Alt=Ask | Ctrl+Shift=Analyze Screen", menu)
        except Exception as e:
            print(f"[Tray] Could not create tray: {e}")
            self.tray_icon = None

    def on_gmail_click(self):
        status, msg = gmail_integration.get_status()
        if status == "not_configured":
            self.overlay.show_error("", "Gmail not configured. See gmail_integration.py for 5-min setup.")
            self.voice.speak("Gmail is not configured yet.")
        elif status == "not_connected":
            self.voice.speak("Opening browser to connect Gmail.")
            threading.Thread(target=self._connect_gmail_flow, daemon=True).start()
        else:
            summary = gmail_integration.get_unread_summary()
            self.overlay.show_answer("Check my email", summary)
            self.voice.speak(summary)

    def _connect_gmail_flow(self):
        ok, msg = gmail_integration.connect_gmail()
        def update():
            if ok:
                self.overlay.show_answer("Connect Gmail", msg)
                self.voice.speak("Gmail connected successfully.")
            else:
                self.overlay.show_error("Connect Gmail", msg)
                self.voice.speak("Gmail connection failed.")
        if self.overlay and self.overlay.root:
            self.overlay.root.after(0, update)

    def show_history(self):
        try:
            if os.path.exists(HISTORY_PATH):
                webbrowser.open(HISTORY_PATH)
                self.voice.speak(f"You have history.")
            else:
                self.overlay.show_answer("History", "No history yet. Ask me something first!")
        except Exception as e:
            print(e)

    def test_overlay(self):
        def do():
            self.overlay.show_question("who is the tallest man ever")
            time.sleep(1)
            self.overlay.show_answer("who is the tallest man ever", "Robert Wadlow was the tallest man ever at 8 feet 11.1 inches (2.72 meters).")
            self.voice.speak("Robert Wadlow was the tallest man ever at 8 feet 11.1 inches.")
        threading.Thread(target=do, daemon=True).start()

    def test_screen_analyze(self):
        # Simulate screen analyze
        if not self.screen_analyzer:
            self.overlay.show_error("", "Screen analyzer not available. Install mss and Pillow: pip install -r requirements.txt")
            return
        threading.Thread(target=self._analyze_screen_flow, kwargs={"test_mode": True}, daemon=True).start()

    # ---------- Hotkey Logic ----------
    def setup_hotkey(self):
        if HAS_PYNPUT:
            def on_press(key):
                try:
                    if key == pynput_keyboard.Key.ctrl_l:
                        self.left_ctrl_pressed = True
                    elif key == pynput_keyboard.Key.alt_l:
                        self.left_alt_pressed = True
                    elif key == pynput_keyboard.Key.shift_l:
                        self.left_shift_pressed = True

                    # Combo 1: Ctrl + Alt -> Voice Q&A
                    if self.left_ctrl_pressed and self.left_alt_pressed and not self.left_shift_pressed:
                        if not self.hotkey_pressed:
                            self.hotkey_pressed = True
                            print("[Hotkey] LEFT CTRL + LEFT ALT pressed! (Ask)")
                            self.trigger_listen()
                    # Combo 2: Ctrl + Shift -> Analyze Screen
                    if self.left_ctrl_pressed and self.left_shift_pressed and not self.left_alt_pressed:
                        if not self.hotkey_screen_pressed:
                            self.hotkey_screen_pressed = True
                            print("[Hotkey] LEFT CTRL + LEFT SHIFT pressed! (Analyze Screen)")
                            self.trigger_screen_analyze()
                except Exception as e:
                    print(f"[Hotkey press err] {e}")

            def on_release(key):
                try:
                    if key == pynput_keyboard.Key.ctrl_l:
                        self.left_ctrl_pressed = False
                        self.hotkey_pressed = False
                        self.hotkey_screen_pressed = False
                    elif key == pynput_keyboard.Key.alt_l:
                        self.left_alt_pressed = False
                        self.hotkey_pressed = False
                    elif key == pynput_keyboard.Key.shift_l:
                        self.left_shift_pressed = False
                        self.hotkey_screen_pressed = False
                except:
                    pass

            self.listener = pynput_keyboard.Listener(on_press=on_press, on_release=on_release)
            self.listener.daemon = True
            self.listener.start()
            print("[Hotkey] Listening for LEFT CTRL+ALT (Ask) and LEFT CTRL+SHIFT (Analyze Screen) via pynput")
        elif HAS_KB:
            try:
                kb_lib.add_hotkey('left ctrl+left alt', self.trigger_listen, suppress=False)
                kb_lib.add_hotkey('left ctrl+left shift', self.trigger_screen_analyze, suppress=False)
                print("[Hotkey] Listening via keyboard lib (ctrl+alt & ctrl+shift)")
            except Exception as e:
                print(f"[Hotkey] Failed: {e}")
        else:
            print("[Hotkey] No hotkey library - press ENTER to simulate")
            threading.Thread(target=self._console_fallback, daemon=True).start()

    def _console_fallback(self):
        while True:
            cmd = input("Type 'ask' for Ctrl+Alt or 'screen' for Ctrl+Shift: ").strip().lower()
            if cmd == "screen":
                self.trigger_screen_analyze()
            else:
                self.trigger_listen()

    def trigger_listen(self):
        if self.is_listening or self.is_screen_analyzing:
            print("[Trigger] Busy, ignore ask")
            return
        self.is_listening = True
        threading.Thread(target=self._listen_and_answer, daemon=True).start()

    def trigger_screen_analyze(self):
        if self.is_screen_analyzing or self.is_listening:
            print("[Trigger] Busy, ignore screen")
            return
        self.is_screen_analyzing = True
        threading.Thread(target=self._analyze_screen_flow, daemon=True).start()

    def _listen_and_answer(self):
        try:
            def show_listening():
                self.overlay.show_listening("Listening... speak now!")
            self.overlay.root.after(0, show_listening)

            question, err = self.voice.listen(timeout=7, phrase_limit=9, language=self.config.get("language", "en-US"))

            if err == "timeout":
                self.overlay.root.after(0, lambda: self.overlay.show_error("", "I didn't hear anything. Press Left CTRL + Left ALT and try again."))
                self.voice.speak("I didn't hear anything. Please try again.")
                return
            if err == "not_understood":
                self.overlay.root.after(0, lambda: self.overlay.show_error(question or "", "Sorry, I couldn't understand. Please speak clearer."))
                self.voice.speak("Sorry, I didn't catch that. Could you repeat?")
                return
            if err and "mic_error" in err:
                self.overlay.root.after(0, lambda: self.overlay.show_error("", "No microphone found. Please check your mic."))
                self.voice.speak("No microphone found.")
                return
            if not question:
                self.overlay.root.after(0, lambda: self.overlay.show_error("", f"Error: {err}"))
                return

            print(f"[Q Ask] {question}")
            self.overlay.root.after(0, lambda: self.overlay.show_question(question))

            ql = question.lower()
            if any(k in ql for k in ["check my email", "read my email", "unread email", "gmail"]):
                answer = gmail_integration.get_unread_summary()
            elif "send email" in ql:
                answer = "To send email, say: Send email to [name] subject [subject] body [message]."
            else:
                answer = self.brain.ask(question, language=self.config.get("language", "en-US"))

            print(f"[A Ask] {answer[:120]}")
            self.save_history(question, answer)
            self.overlay.root.after(0, lambda: self.overlay.show_answer(question, answer))
            self.voice.speak(answer)

        except Exception as e:
            print(f"[ListenAndAnswer] Error: {e}")
            import traceback; traceback.print_exc()
            try:
                self.overlay.root.after(0, lambda: self.overlay.show_error("", f"Unexpected error: {e}"))
            except:
                pass
        finally:
            self.is_listening = False

    def _analyze_screen_flow(self, test_mode=False):
        """Left Ctrl + Left Shift flow: capture screen -> ask about it -> analyze -> answer"""
        image_path = None
        try:
            # 1. Capture screen immediately (so we get what user saw when pressing hotkey)
            def show_capturing():
                self.overlay.show_listening("Capturing screen...")
            self.overlay.root.after(0, show_capturing)

            if self.screen_analyzer:
                image_path = self.screen_analyzer.capture_screen()
            else:
                self.overlay.root.after(0, lambda: self.overlay.show_error("", "Screen capture not available. Install: pip install mss Pillow"))
                self.voice.speak("Screen capture not available. Please install dependencies.")
                return

            if not image_path or not os.path.exists(image_path):
                self.overlay.root.after(0, lambda: self.overlay.show_error("", "Failed to capture screen. Try again."))
                return

            # Brief flash feedback
            print(f"[Screen] Captured: {image_path}")

            # 2. Show captured + prompt for question
            def show_prompt():
                self.overlay.show_screen_listening(image_path, "Screen captured — what about it?")
            self.overlay.root.after(0, show_prompt)
            # Small chime via voice
            if not test_mode:
                self.voice.speak("Screen captured. What would you like to know about what you see?")

            # 3. Listen for question about screen (longer timeout, allow thinking)
            if test_mode:
                question = "what do you see on my screen? Describe it."
                err = None
            else:
                question, err = self.voice.listen(timeout=8, phrase_limit=12, language=self.config.get("language", "en-US"))

            if err == "timeout":
                # If no question, default to describe
                question = "what do you see on my screen? Describe it in detail."
                err = None
            if err == "not_understood":
                self.overlay.root.after(0, lambda: self.overlay.show_error(question or "", "Sorry, didn't catch your screen question. Try again: press Ctrl+Shift and say 'what does this say?'"))
                self.voice.speak("Sorry, I didn't catch that. Press left control and left shift again and say what you want to know.")
                return
            if err and "mic_error" in err:
                self.overlay.root.after(0, lambda: self.overlay.show_error("", "No microphone found."))
                return
            if not question or err:
                question = "describe what you see on my screen"

            print(f"[Q Screen] {question}")
            self.overlay.root.after(0, lambda: self.overlay.show_screen_question(image_path, question))

            # 4. Analyze with vision/OCR
            # Use screen_analyzer.analyze which handles Groq Vision / Ollama / OCR fallback free
            answer = self.screen_analyzer.analyze(question, image_path, language=self.config.get("language", "en-US"))

            print(f"[A Screen] {answer[:140]}")
            # Save to history with screen tag
            self.save_history(f"[Screen] {question}", answer)
            self.overlay.root.after(0, lambda: self.overlay.show_screen_answer(image_path, question, answer))
            self.voice.speak(answer)

        except Exception as e:
            print(f"[ScreenFlow] Error: {e}")
            import traceback; traceback.print_exc()
            try:
                self.overlay.root.after(0, lambda: self.overlay.show_error("", f"Screen analyze error: {e}"))
            except:
                pass
        finally:
            self.is_screen_analyzing = False
            # Clean temp file after 30s? Keep for cache
            # image_path cleanup handled by temp, but we keep last for quick re-ask

    def save_history(self, q, a):
        try:
            hist = []
            if os.path.exists(HISTORY_PATH):
                with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                    hist = json.load(f)
            hist.append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "question": q, "answer": a, "lang": self.config.get("language")})
            hist = hist[-200:]
            with open(HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(hist, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[History] {e}")

    def show_intro_wizard(self):
        """Step-by-step tour - shows the most important things after download"""
        def wizard_thread():
            win = tk.Toplevel(self.overlay.root)
            win.title("VoiceBox - Setup Tour")
            win.geometry("640x620+{}+{}".format(
                (win.winfo_screenwidth()-640)//2,
                (win.winfo_screenheight()-620)//2
            ))
            win.configure(bg="#ffffff")
            win.attributes("-topmost", True)
            win.grab_set()
            win.resizable(False, False)

            # State
            step = {"idx": 0}
            selected_lang = tk.StringVar(value=self.config.get("language", "en-US"))
            selected_voice = tk.StringVar(value=self.config.get("voice_id", "en-US-AriaNeural"))
            groq_var = tk.StringVar(value=self.config.get("groq_api_key", ""))

            langs = [("English (US)", "en-US"), ("English (UK)", "en-GB"),("Spanish", "es-ES"), ("French", "fr-FR"), ("German", "de-DE"),("Japanese", "ja-JP"), ("Hindi", "hi-IN"), ("Arabic", "ar-SA"), ("Portuguese", "pt-BR")]
            voices = self.voice.list_voices()
            voice_ids = [v["id"] for v in voices]
            if selected_voice.get() not in voice_ids and voice_ids:
                selected_voice.set(voice_ids[0])

            # Top progress
            top = tk.Frame(win, bg="#ffffff", height=56)
            top.pack(fill="x", padx=0, pady=0)
            tk.Label(top, text="VoiceBox Setup Tour", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=22, pady=(14,0))
            prog_frame = tk.Frame(top, bg="#ffffff")
            prog_frame.pack(fill="x", padx=22, pady=(6,10))
            prog_labels = []
            steps_meta = ["Welcome","Language","Voice","Hotkeys","Permissions","AI Free","Gmail","Ready"]
            for i, name in enumerate(steps_meta):
                lbl = tk.Label(prog_frame, text=f"{i+1}", bg="#f1f5f9" if i!=0 else "#0f172a", fg="#64748b" if i!=0 else "white", font=("Segoe UI", 8, "bold"), width=3, height=1, bd=0, relief="flat")
                lbl.pack(side="left", padx=(0 if i==0 else 6, 0))
                prog_labels.append(lbl)
                if i < len(steps_meta)-1:
                    tk.Frame(prog_frame, bg="#e2e8f0", width=12, height=2).pack(side="left", padx=4, pady=4)
            step_title = tk.Label(top, text="", bg="#ffffff", fg="#64748b", font=("Segoe UI", 9))
            step_title.pack(anchor="w", padx=22)
            ttk_sep = tk.Frame(win, bg="#e2e8f0", height=1)
            ttk_sep.pack(fill="x")

            # Content area
            content = tk.Frame(win, bg="#ffffff")
            content.pack(fill="both", expand=True, padx=24, pady=16)
            
            # Keep refs for dynamic widgets
            lang_label = {"widget": None}
            voice_menu = {"widget": None}

            def clear_content():
                for w in content.winfo_children():
                    w.destroy()

            def update_progress():
                for i, lbl in enumerate(prog_labels):
                    if i == step["idx"]:
                        lbl.config(bg="#0f172a", fg="white")
                    elif i < step["idx"]:
                        lbl.config(bg="#10b981", fg="white")
                    else:
                        lbl.config(bg="#f1f5f9", fg="#64748b")
                step_title.config(text=f"Step {step['idx']+1} of {len(steps_meta)} — {steps_meta[step['idx']]}")

            def render():
                clear_content()
                update_progress()
                idx = step["idx"]
                # Step 0 Welcome
                if idx == 0:
                    tk.Label(content, text="Welcome to VoiceBox", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 18, "bold")).pack(anchor="w")
                    tk.Label(content, text="Your calm, professional voice assistant for Windows.\nRuns quietly in the background — you press, speak, and it answers.", bg="#ffffff", fg="#64748b", font=("Segoe UI", 9), justify="left").pack(anchor="w", pady=(8,14))
                    tk.Label(content, text="In this tour you’ll see the most important things:\nlanguage, voice, hotkeys, permissions, free AI, and Gmail.\nIt takes 60 seconds — then you’re ready.", bg="#f8fafc", fg="#334155", font=("Segoe UI", 9), justify="left", padx=12, pady=10, bd=1, relief="solid", highlightbackground="#e2e8f0").pack(fill="x", pady=(0,14))
                    tk.Label(content, text="What happens after the tour:", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 9, "bold")).pack(anchor="w")
                    tk.Label(content, text="• App tucks into the tray (0.1% CPU)\n• Left Ctrl + Left Alt → Ask anything\n• Left Ctrl + Left Shift → Analyze your screen", bg="#ffffff", fg="#334155", font=("Segoe UI", 9), justify="left").pack(anchor="w", pady=4)
                    tk.Label(content, text="No demos on the website — everything important is here, step-by-step.", bg="#ffffff", fg="#94a3b8", font=("Segoe UI", 8, "italic")).pack(anchor="w", pady=(10,0))
                # Step 1 Language
                elif idx == 1:
                    tk.Label(content, text="Choose your language", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 14, "bold")).pack(anchor="w")
                    tk.Label(content, text="VoiceBox will listen and answer in this language.", bg="#ffffff", fg="#64748b", font=("Segoe UI", 9)).pack(anchor="w", pady=(4,12))
                    row = tk.Frame(content, bg="#ffffff")
                    row.pack(fill="x", pady=6)
                    tk.Label(row, text="Language:", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 9, "bold")).pack(side="left")
                    cb = tk.OptionMenu(row, selected_lang, *[c for _,c in langs])
                    cb.config(bg="#f8fafc", fg="#0f172a", highlightthickness=1, highlightbackground="#e2e8f0", bd=1, width=22, anchor="w")
                    cb.pack(side="left", padx=10)
                    # Preview name
                    def get_name(code): return next((n for n,c in langs if c==code), code)
                    name_lbl = tk.Label(content, text=f"Selected: {get_name(selected_lang.get())}", bg="#f1f5f9", fg="#334155", font=("Segoe UI", 9), padx=10, pady=6)
                    name_lbl.pack(fill="x", pady=8)
                    def on_lang(*a):
                        code = selected_lang.get()
                        name = get_name(code)
                        name_lbl.config(text=f"Selected: {name} — I’ll speak and listen in {name}")
                        self.voice.set_language(code, name)
                        self.config["language"] = code
                        self.config["language_name"] = name
                        self.save_config()
                    selected_lang.trace_add("write", on_lang)
                    tk.Label(content, text="You can change this anytime in config.json or by re-opening this tour from the tray.", bg="#ffffff", fg="#94a3b8", font=("Segoe UI", 8)).pack(anchor="w", pady=(12,0))
                # Step 2 Voice
                elif idx == 2:
                    tk.Label(content, text="Pick a nicer, cleaner voice", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 14, "bold")).pack(anchor="w")
                    tk.Label(content, text="Neural voices (Aria, Jenny, Guy) sound much more natural. Try them:", bg="#ffffff", fg="#64748b", font=("Segoe UI", 9)).pack(anchor="w", pady=(4,12))
                    row = tk.Frame(content, bg="#ffffff")
                    row.pack(fill="x", pady=6)
                    tk.Label(row, text="Voice:", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 9, "bold")).pack(side="left")
                    vm = tk.OptionMenu(row, selected_voice, *voice_ids)
                    vm.config(bg="#f8fafc", fg="#0f172a", highlightthickness=1, highlightbackground="#e2e8f0", bd=1, width=32, anchor="w")
                    vm.pack(side="left", padx=10)
                    def voice_name(vid):
                        for v in voices:
                            if v["id"]==vid: return v["name"]
                        return vid
                    info = tk.Label(content, text=voice_name(selected_voice.get()), bg="#f1f5f9", fg="#334155", font=("Segoe UI", 8), wraplength=540, justify="left", padx=10, pady=6)
                    info.pack(fill="x", pady=6)
                    btn = tk.Button(content, text="▶  Test this voice", bg="#0f172a", fg="white", bd=0, padx=14, pady=8, font=("Segoe UI", 9, "bold"),
                                 command=lambda: threading.Thread(target=lambda: self.voice.test_voice(selected_voice.get()), daemon=True).start())
                    btn.pack(anchor="w", pady=6)
                    def on_voice(*a):
                        vid = selected_voice.get()
                        info.config(text=voice_name(vid))
                        self.voice.set_voice(vid)
                        self.config["voice_id"] = vid
                        self.config["voice_name"] = voice_name(vid)
                        self.save_config()
                    selected_voice.trace_add("write", on_voice)
                    tk.Label(content, text="Tip: Aria and Jenny are the cleanest for English. Elvira for Spanish, Denise for French.", bg="#ffffff", fg="#94a3b8", font=("Segoe UI", 8)).pack(anchor="w", pady=(10,0))
                # Step 3 Hotkeys
                elif idx == 3:
                    tk.Label(content, text="Two hotkeys — everything you need", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 14, "bold")).pack(anchor="w")
                    tk.Label(content, text="Only the left side — right Ctrl/Alt/Shift are ignored, so you won’t trigger by accident.", bg="#ffffff", fg="#64748b", font=("Segoe UI", 9)).pack(anchor="w", pady=(4,12))
                    # Card 1
                    c1 = tk.Frame(content, bg="#0f172a", bd=0, highlightbackground="#0f172a")
                    c1.pack(fill="x", pady=6)
                    tk.Label(c1, text="  Left  CTRL  +  Left  ALT      →   Ask anything", bg="#0f172a", fg="white", font=("Consolas", 10, "bold"), anchor="w").pack(fill="x", padx=12, pady=8)
                    tk.Label(c1, text="Hold both, speak:  “Who is the tallest man ever?”  →  top card + spoken answer", bg="#0f172a", fg="#cbd5e1", font=("Segoe UI", 8)).pack(fill="x", padx=12, pady=(0,8))
                    c2 = tk.Frame(content, bg="#ffffff", bd=1, relief="solid", highlightbackground="#e2e8f0", highlightcolor="#e2e8f0")
                    c2.config(highlightbackground="#e2e8f0")
                    c2.pack(fill="x", pady=6)
                    tk.Label(c2, text="  Left  CTRL  +  Left  SHIFT   →   Analyze your screen", bg="#ffffff", fg="#0f172a", font=("Consolas", 10, "bold"), anchor="w").pack(fill="x", padx=12, pady=8)
                    tk.Label(c2, text="Hold both → screen captured → speak:  “What does this say?”  →  analysed + spoken", bg="#ffffff", fg="#64748b", font=("Segoe UI", 8)).pack(fill="x", padx=12, pady=(0,8))
                    tk.Label(content, text="Try it after the tour — the overlay appears at the middle-top, calm white, with thumbnail for screen.", bg="#ffffff", fg="#94a3b8", font=("Segoe UI", 8)).pack(anchor="w", pady=(10,0))
                # Step 4 Permissions — interactive (asks like a real installer)
                elif idx == 4:
                    tk.Label(content, text="Permissions — we’ll ask, you choose", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 14, "bold")).pack(anchor="w")
                    tk.Label(content, text="Click Allow to grant. We only use each when you press the hotkey.", bg="#ffffff", fg="#64748b", font=("Segoe UI", 9)).pack(anchor="w", pady=(4,12))

                    # Microphone row with Allow button
                    def ask_mic():
                        try:
                            # This triggers Windows mic permission dialog on first use
                            import speech_recognition as sr
                            r = sr.Recognizer()
                            with sr.Microphone() as source:
                                r.adjust_for_ambient_noise(source, duration=0.5)
                            status_mic.config(text="✓ Microphone: Allowed — we can hear you after Ctrl+Alt", bg="#ecfdf5", fg="#065f46")
                            self.voice.speak_blocking("Microphone access granted!")
                        except Exception as e:
                            status_mic.config(text=f"✗ Microphone: {e}. Check Settings → Privacy → Microphone → Allow apps", bg="#fef2f2", fg="#991b1b")
                            from tkinter import messagebox as mb
                            mb.showinfo("Microphone", "VoiceBox wants to access your microphone — to hear your question after you press Left Ctrl + Left Alt.\n\nIf blocked, open Settings → Privacy & security → Microphone → Let apps access your microphone → On, then click Allow again.")

                    def ask_screen():
                        try:
                            if self.screen_analyzer:
                                # Trigger screen capture - Windows may ask for permission on first capture
                                img = self.screen_analyzer.capture()
                                status_screen.config(text="✓ Screen capture: Allowed — we can see your screen after Ctrl+Shift", bg="#ecfdf5", fg="#065f46")
                                self.voice.speak_blocking("Screen capture access granted!")
                                # Show thumbnail
                                try:
                                    from PIL import ImageTk
                                    import io
                                    thumb = img.copy()
                                    thumb.thumbnail((320,180))
                                    bio = io.BytesIO()
                                    thumb.save(bio, format="PNG")
                                    bio.seek(0)
                                    from PIL import Image
                                    tk_img = ImageTk.PhotoImage(thumb)
                                    lbl = tk.Label(content, image=tk_img, bg="#ffffff", bd=1, relief="solid")
                                    lbl.image = tk_img
                                    lbl.pack(pady=6)
                                except: pass
                            else:
                                status_screen.config(text="Screen analyzer not available (install mss)", bg="#fffbeb", fg="#92400e")
                        except Exception as e:
                            status_screen.config(text=f"✗ Screen: {e}", bg="#fef2f2", fg="#991b1b")
                            from tkinter import messagebox as mb
                            mb.showinfo("Screen capture", "VoiceBox wants to capture your screen — only when you press Left Ctrl + Left Shift to ask about what you see.\n\nIf blocked, allow screen capture in Windows Settings.")

                    # Mic card
                    f1 = tk.Frame(content, bg="#f8fafc", bd=1, relief="solid", highlightbackground="#e2e8f0")
                    f1.pack(fill="x", pady=4)
                    r1 = tk.Frame(f1, bg="#f8fafc")
                    r1.pack(fill="x", padx=10, pady=6)
                    tk.Label(r1, text="🎤  Microphone", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 9, "bold")).pack(side="left")
                    tk.Button(r1, text="Allow Microphone", bg="#0f172a", fg="white", bd=0, padx=10, pady=4, font=("Segoe UI", 8, "bold"), command=lambda: threading.Thread(target=ask_mic, daemon=True).start()).pack(side="right")
                    status_mic = tk.Label(f1, text="Not yet requested — click Allow to let VoiceBox listen after the hotkey", bg="#f8fafc", fg="#64748b", font=("Segoe UI", 8), wraplength=500, justify="left")
                    status_mic.pack(anchor="w", padx=10, pady=(0,6))

                    # Screen card
                    f2 = tk.Frame(content, bg="#f8fafc", bd=1, relief="solid", highlightbackground="#e2e8f0")
                    f2.pack(fill="x", pady=4)
                    r2 = tk.Frame(f2, bg="#f8fafc")
                    r2.pack(fill="x", padx=10, pady=6)
                    tk.Label(r2, text="🖥️  Screen capture", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 9, "bold")).pack(side="left")
                    tk.Button(r2, text="Allow Screen Capture", bg="#0f172a", fg="white", bd=0, padx=10, pady=4, font=("Segoe UI", 8, "bold"), command=lambda: threading.Thread(target=ask_screen, daemon=True).start()).pack(side="right")
                    status_screen = tk.Label(f2, text="Not yet requested — click Allow, we capture only when you press Ctrl+Shift", bg="#f8fafc", fg="#64748b", font=("Segoe UI", 8), wraplength=500, justify="left")
                    status_screen.pack(anchor="w", padx=10, pady=(0,6))

                    # Admin / background info (no button needed, already granted via UAC)
                    for title, desc in [("🔒  Administrator","Already granted via ‘Allow changes?’ when you ran the installer — needed once for hotkeys/background."),("⚡  Background","Stays in tray at 0.1% CPU, instant when you need it.")]:
                        f = tk.Frame(content, bg="#f8fafc", bd=1, relief="solid", highlightbackground="#e2e8f0")
                        f.pack(fill="x", pady=4)
                        tk.Label(f, text=title, bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(6,0))
                        tk.Label(f, text=desc, bg="#f8fafc", fg="#64748b", font=("Segoe UI", 8), wraplength=520, justify="left").pack(anchor="w", padx=10, pady=(2,6))
                    tk.Label(content, text="Tip: you can change these anytime in Windows Settings → Privacy & security.", bg="#ffffff", fg="#94a3b8", font=("Segoe UI", 7)).pack(anchor="w", pady=(6,0))
                # Step 5 AI Free
                elif idx == 5:
                    tk.Label(content, text="AI — free forever, yours to make", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 14, "bold")).pack(anchor="w")
                    tk.Label(content, text="No subscription. Works even offline.", bg="#ffffff", fg="#64748b", font=("Segoe UI", 9)).pack(anchor="w", pady=(4,12))
                    tk.Label(content, text="🌐 Internet required for AI to work.\n1) Best quality (free, needs internet): Groq Llama 3.1 — get a free key at console.groq.com (30 sec) and paste below.\n2) Fully offline fallback: install Ollama → ‘ollama run llama3.1’ (still needs internet for model download, then works offline).\n3) No key, needs internet: Wikipedia + DuckDuckGo for factual answers.", bg="#f8fafc", fg="#334155", font=("Segoe UI", 8), justify="left", padx=10, pady=8).pack(fill="x", pady=6)
                    row = tk.Frame(content, bg="#ffffff")
                    row.pack(fill="x", pady=8)
                    tk.Label(row, text="Groq API key (optional):", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 9, "bold")).pack(side="left")
                    ent = tk.Entry(row, textvariable=groq_var, bg="#f8fafc", fg="#0f172a", bd=1, relief="solid", highlightbackground="#e2e8f0", width=32)
                    ent.pack(side="left", padx=8)
                    def save_groq(*a):
                        self.config["groq_api_key"] = groq_var.get().strip()
                        self.save_config()
                    groq_var.trace_add("write", save_groq)
                    tk.Label(content, text="Leave empty to use offline mode — still answers and writes. Add a key for richer Llama replies.", bg="#ffffff", fg="#94a3b8", font=("Segoe UI", 8)).pack(anchor="w", pady=4)
                    tk.Label(content, text="Try after tour: “write me a paragraph about AI” → it writes like a real AI.", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 8, "italic")).pack(anchor="w", pady=(8,0))
                # Step 6 Gmail
                elif idx == 6:
                    tk.Label(content, text="Gmail — optional, secure", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 14, "bold")).pack(anchor="w")
                    tk.Label(content, text='Say “check my email” and it summarises your inbox.', bg="#ffffff", fg="#64748b", font=("Segoe UI", 9)).pack(anchor="w", pady=(4,12))
                    tk.Label(content, text="How to enable (5 min):\n1. console.cloud.google.com → Create project “VoiceBox”\n2. Enable Gmail API → Create OAuth Desktop Client → Download JSON\n3. Save as app/gmail_client.json → restart app → tray → Gmail → Connect\n4. Say: “check my email” or “send email to…”", bg="#f8fafc", fg="#334155", font=("Segoe UI", 8), justify="left", padx=10, pady=8).pack(fill="x", pady=6)
                    status, msg = gmail_integration.get_status()
                    col = "#ecfdf5" if status=="connected" else "#fffbeb" if status=="not_connected" else "#f8fafc"
                    fgcol = "#065f46" if status=="connected" else "#92400e" if status=="not_connected" else "#64748b"
                    st = tk.Label(content, text=f"Status: {msg}", bg=col, fg=fgcol, font=("Segoe UI", 8), padx=10, pady=6)
                    st.pack(fill="x", pady=6)
                    if status == "not_connected":
                        tk.Button(content, text="Connect Gmail now (opens browser)", bg="#0f172a", fg="white", bd=0, padx=12, pady=6, font=("Segoe UI", 8, "bold"),
                                  command=lambda: threading.Thread(target=self._connect_gmail_flow, daemon=True).start()).pack(anchor="w", pady=4)
                    tk.Label(content, text="Token stays on your PC (gmail_token.json), revoke anytime at myaccount.google.com/permissions.", bg="#ffffff", fg="#94a3b8", font=("Segoe UI", 7)).pack(anchor="w", pady=(8,0))
                    tk.Label(content, text="You can skip this — Ask and Screen Analyze work without Gmail.", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=4)
                # Step 7 Ready
                elif idx == 7:
                    tk.Label(content, text="You’re ready!", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 18, "bold")).pack(anchor="w")
                    tk.Label(content, text="VoiceBox will now live in the system tray — quiet, 0.1% CPU, ready instantly.", bg="#ffffff", fg="#64748b", font=("Segoe UI", 9)).pack(anchor="w", pady=(4,12))
                    ok = tk.Frame(content, bg="#ecfdf5", bd=1, relief="solid", highlightbackground="#a7f3d0")
                    ok.pack(fill="x", pady=4)
                    tk.Label(ok, text="Try it now:", bg="#ecfdf5", fg="#065f46", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(6,0))
                    tk.Label(ok, text="• Press Left Ctrl + Left Alt → say “Who is the tallest man ever?”\n• Press Left Ctrl + Left Shift → say “What does this say?” (about your screen)", bg="#ecfdf5", fg="#065f46", font=("Segoe UI", 9), justify="left").pack(anchor="w", padx=10, pady=(2,6))
                    tk.Label(content, text="Need help? Tray right-click → Settings (this tour), Test Voice, Gmail, History, Quit.", bg="#ffffff", fg="#64748b", font=("Segoe UI", 8)).pack(anchor="w", pady=(10,0))
                    tk.Label(content, text="Tip: If a hotkey doesn’t work, run as Administrator once.", bg="#fffbeb", fg="#92400e", font=("Segoe UI", 8), padx=10, pady=6).pack(fill="x", pady=8)

            # Navigation
            nav = tk.Frame(win, bg="#ffffff")
            nav.pack(fill="x", padx=16, pady=(0,16), side="bottom")
            back_btn = tk.Button(nav, text="← Back", bg="#f1f5f9", fg="#0f172a", bd=1, padx=14, pady=8, font=("Segoe UI", 9), state="disabled")
            next_btn = tk.Button(nav, text="Next →", bg="#0f172a", fg="white", bd=0, padx=18, pady=8, font=("Segoe UI", 9, "bold"))
            skip_btn = tk.Button(nav, text="Skip tour", bg="#ffffff", fg="#94a3b8", bd=0, padx=10, pady=8, font=("Segoe UI", 8))
            # Order
            back_btn.pack(side="left")
            skip_btn.pack(side="left", padx=8)
            next_btn.pack(side="right")

            def refresh_nav():
                back_btn.config(state="normal" if step["idx"]>0 else "disabled")
                if step["idx"] == len(steps_meta)-1:
                    next_btn.config(text="✓ Complete & Start", bg="#10b981")
                else:
                    next_btn.config(text="Next →", bg="#0f172a")

            def go_next():
                if step["idx"] < len(steps_meta)-1:
                    step["idx"] += 1
                    render()
                    refresh_nav()
                else:
                    # Finish
                    self.config["intro_completed"] = True
                    self.save_config()
                    self.voice.speak_blocking(f"Perfect! VoiceBox is ready in {self.config.get('language_name','English')}. Press left control and left alt to ask, or left control and left shift to analyze your screen.")
                    win.destroy()
                    self.overlay.root.after(500, lambda: self.overlay.show_answer("Setup complete", "VoiceBox running. Left CTRL+ALT = Ask  •  Left CTRL+SHIFT = Analyze Screen"))

            def go_back():
                if step["idx"] > 0:
                    step["idx"] -= 1
                    render()
                    refresh_nav()

            def skip():
                win.destroy()

            back_btn.config(command=go_back)
            next_btn.config(command=go_next)
            skip_btn.config(command=skip)

            render()
            refresh_nav()

        self.overlay.root.after(0, wizard_thread)

    def quit_app(self):
        print("[Quit] Shutting down...")
        try:
            if self.tray_icon:
                self.tray_icon.stop()
        except:
            pass
        try:
            if self.overlay and self.overlay.root:
                self.overlay.root.quit()
        except:
            pass
        os._exit(0)

    def start(self):
        if self.tray_icon:
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
            print("[Tray] Running - Right-click for menu")
        print("[Ready] VoiceBox running.")
        print("[Ready] LEFT CTRL+ALT = Ask anything  |  LEFT CTRL+SHIFT = Analyze Screen")
        print("[Tip] If hotkey doesn't work, run as Administrator once.")
        self.overlay.run()

if __name__ == "__main__":
    import tkinter as tk
    app = VoiceBoxApp()
    app.start()
