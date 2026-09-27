"""
VoiceBox - Overlay Window (Professional White Edition + Screen Analyze)
The small box that appears at middle-top showing question + answer.
Now supports screen capture thumbnail + smooth fade.
"""
import tkinter as tk
import threading
import time
import os

class Overlay:
    def __init__(self, config):
        self.config = config
        self.root = None
        self.is_visible = False
        self.hide_timer = None
        self._thumb_img = None
        self._setup_root()

    def _setup_root(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.98)
        self.root.configure(bg="#f8fafc")
        self.root.geometry("0x0+0+0")
        self.root.withdraw()

        self.shadow = tk.Frame(self.root, bg="#e2e8f0", bd=0)
        self.shadow.pack(fill="both", expand=True, padx=1, pady=1)

        self.frame = tk.Frame(self.shadow, bg="#ffffff", highlightbackground="#e2e8f0", highlightthickness=1, bd=0)
        self.frame.pack(fill="both", expand=True, padx=0, pady=0)

        self.header = tk.Label(self.frame, text="● VoiceBox  •  Listening...", bg="#ffffff", fg="#64748b", font=("Segoe UI", 8, "bold"), anchor="w")
        self.header.pack(fill="x", padx=16, pady=(12, 2))

        # Thumbnail for screen analyze (hidden by default)
        self.thumb_holder = tk.Frame(self.frame, bg="#ffffff")
        self.thumb_label = tk.Label(self.thumb_holder, bg="#ffffff", bd=0)
        self.thumb_label.pack(side="left", padx=16, pady=(0,6))
        self.thumb_caption = tk.Label(self.thumb_holder, text="", bg="#ffffff", fg="#94a3b8", font=("Segoe UI", 7), anchor="w")
        self.thumb_caption.pack(side="left", pady=(0,6))

        self.q_label = tk.Label(self.frame, text="", bg="#ffffff", fg="#0f172a", font=("Segoe UI", 11, "bold"), wraplength=540, justify="left", anchor="w")
        self.q_label.pack(fill="x", padx=16, pady=(2, 6))

        self.div = tk.Frame(self.frame, bg="#f1f5f9", height=1)
        self.div.pack(fill="x", padx=16, pady=6)

        self.a_label = tk.Label(self.frame, text="", bg="#ffffff", fg="#334155", font=("Segoe UI", 10), wraplength=540, justify="left", anchor="w")
        self.a_label.pack(fill="x", padx=16, pady=(4, 12))

        self.footer = tk.Label(self.frame, text="Press ESC to hide  •  Click to copy answer", bg="#f8fafc", fg="#94a3b8", font=("Segoe UI", 7), anchor="w")
        self.footer.pack(fill="x", padx=16, pady=(0, 0), ipady=6)

        self.root.bind("<Escape>", lambda e: self.hide())
        self.root.bind("<Button-1>", lambda e: self.copy_answer())
        self.frame.bind("<Button-1>", lambda e: self.copy_answer())

    def _position(self):
        self.root.update_idletasks()
        w = 640
        h = self.frame.winfo_reqheight() + 4
        h = max(130, min(h, 560))
        sw = self.root.winfo_screenwidth()
        x = (sw - w) // 2
        y = 24
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _set_thumbnail(self, image_path):
        """Show small thumbnail of captured screen if path exists"""
        try:
            if image_path and os.path.exists(image_path):
                from PIL import Image, ImageTk
                img = Image.open(image_path)
                # Thumbnail 96x60, keep aspect
                img.thumbnail((96, 60), Image.LANCZOS)
                # Add subtle border
                self._thumb_img = ImageTk.PhotoImage(img)
                self.thumb_label.config(image=self._thumb_img)
                self.thumb_caption.config(text=f"Screen captured • {os.path.basename(image_path)} • {img.size[0]}×{img.size[1]}")
                self.thumb_holder.pack(fill="x", before=self.q_label)
            else:
                self.thumb_holder.pack_forget()
        except Exception as e:
            print(f"[Overlay thumb] {e}")
            self.thumb_holder.pack_forget()

    def _clear_thumbnail(self):
        try:
            self.thumb_holder.pack_forget()
        except:
            pass

    def show_listening(self, text="Listening..."):
        self._clear_thumbnail()
        self.header.config(text="● VoiceBox  •  Listening...  ●", fg="#b45309")
        self.q_label.config(text=text, fg="#92400e")
        self.a_label.config(text="Speak your question clearly after the hotkey...", fg="#64748b")
        self.div.pack_forget()
        self._show()

    def show_screen_listening(self, image_path=None, text="Screen captured — what about it?"):
        # Special listening after screen capture
        self._set_thumbnail(image_path)
        self.header.config(text="● VoiceBox  •  Screen captured  ●", fg="#0f172a")
        self.q_label.config(text=text, fg="#0f172a")
        self.a_label.config(text="Speak now — e.g., 'what does this say?' or 'summarize this page'", fg="#64748b")
        self.div.pack(fill="x", padx=16, pady=6)
        self._show()

    def show_question(self, question):
        self.header.config(text="● VoiceBox  •  Thinking...", fg="#475569")
        self.q_label.config(text=f'You: "{question}"', fg="#0f172a")
        self.a_label.config(text="Generating answer...", fg="#64748b")
        self.div.pack(fill="x", padx=16, pady=6)
        self._show()

    def show_screen_question(self, image_path, question):
        self._set_thumbnail(image_path)
        self.header.config(text="● VoiceBox  •  Analyzing screen...", fg="#334155")
        self.q_label.config(text=f'You (about screen): "{question}"', fg="#0f172a")
        self.a_label.config(text="Analyzing what you see...", fg="#64748b")
        self.div.pack(fill="x", padx=16, pady=6)
        self._show()

    def show_answer(self, question, answer):
        self.header.config(text="● VoiceBox  •  Answered", fg="#065f46")
        self.q_label.config(text=f'You: "{question}"', fg="#0f172a")
        display = answer if len(answer) < 1100 else answer[:1080] + "..."
        self.a_label.config(text=display, fg="#334155")
        self._position()
        duration = self.config.get("overlay_duration_seconds", 9)
        if self.hide_timer:
            self.root.after_cancel(self.hide_timer)
        self.hide_timer = self.root.after(int(duration * 1000), self.hide)
        self.footer.config(text="✓ Spoken out loud  •  Click to copy  •  ESC to hide", bg="#f8fafc")

    def show_screen_answer(self, image_path, question, answer):
        self._set_thumbnail(image_path)
        self.header.config(text="● VoiceBox  •  Screen analyzed", fg="#065f46")
        self.q_label.config(text=f'You (about screen): "{question}"', fg="#0f172a")
        display = answer if len(answer) < 1400 else answer[:1380] + "..."
        self.a_label.config(text=display, fg="#334155")
        self._position()
        duration = self.config.get("overlay_duration_seconds", 10)
        if self.hide_timer:
            self.root.after_cancel(self.hide_timer)
        self.hide_timer = self.root.after(int(duration * 1000), self.hide)
        self.footer.config(text="✓ Screen analyzed + spoken  •  Click to copy  •  ESC to hide", bg="#f8fafc")

    def show_error(self, question, error_msg):
        self.header.config(text="● VoiceBox  •  Notice", fg="#b45309")
        self.q_label.config(text=f'You: "{question}"' if question else "Notice", fg="#0f172a")
        self.a_label.config(text=error_msg, fg="#b45309")
        self._position()
        self.hide_timer = self.root.after(7000, self.hide)

    def _show(self):
        self._position()
        try:
            self.root.attributes("-alpha", 0.0)
        except:
            pass
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.is_visible = True
        def fade(step=0):
            alpha = min(0.98, step * 0.14)
            try:
                self.root.attributes("-alpha", alpha)
            except:
                pass
            if alpha < 0.97:
                self.root.after(18, lambda: fade(step+1))
        fade(1)

    def hide(self):
        if not self.root or not self.is_visible:
            return
        def fade_out(alpha=0.98):
            nxt = alpha - 0.18
            if nxt <= 0.15:
                try:
                    self.root.withdraw()
                    self._clear_thumbnail()
                except:
                    pass
                self.is_visible = False
                try:
                    self.root.attributes("-alpha", 0.98)
                except:
                    pass
                return
            try:
                self.root.attributes("-alpha", nxt)
            except:
                pass
            self.root.after(16, lambda: fade_out(nxt))
        fade_out()

    def copy_answer(self):
        try:
            txt = self.a_label.cget("text")
            self.root.clipboard_clear()
            self.root.clipboard_append(txt)
            self.footer.config(text="✓ Copied to clipboard!")
            self.root.after(1500, lambda: self.footer.config(text="Press ESC to hide  •  Click to copy answer"))
        except:
            pass

    def _ensure_thread(self):
        pass

    def run(self):
        self.root.mainloop()

    def run_in_thread(self):
        t = threading.Thread(target=self.run, daemon=True)
        t.start()
        time.sleep(0.35)
        return t
