"""
VoiceBox - Voice Engine (Nicer & Cleaner Edition)
Handles Speech-to-Text (STT) and Text-to-Speech (TTS)
- Now with Edge TTS (neural, natural) + gTTS + pyttsx3 fallback
- Cleaner pre-processing, nicer prosody, free.
"""
import json
import threading
import re
import os
import tempfile

CONFIG_PATH = "config.json"

# Try imports
try:
    import pyttsx3
    HAS_PYTTSX3 = True
except:
    HAS_PYTTSX3 = False

try:
    import speech_recognition as sr
    HAS_SR = True
except:
    HAS_SR = False

# Edge TTS for natural voice (free, no key, Microsoft neural)
try:
    import edge_tts
    import asyncio
    HAS_EDGE = True
except:
    HAS_EDGE = False

# gTTS fallback
try:
    from gtts import gTTS
    HAS_GTTS = True
except:
    HAS_GTTS = False

# For playback of mp3
try:
    import pygame
    HAS_PYGAME = True
except:
    HAS_PYGAME = False

class VoiceEngine:
    def __init__(self):
        self.config = self.load_config()
        self.engine = None
        self.init_tts()
        if HAS_SR:
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.75
        else:
            self.recognizer = None
        # Preferred TTS mode: "auto" -> edge -> gtts -> pyttsx3
        self.tts_mode = self.config.get("tts_mode", "auto")
        # Cleaner defaults
        self.config.setdefault("voice_rate", 175)  # slightly slower = cleaner
        self.config.setdefault("voice_volume", 0.92)

    def load_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"language": "en-US", "voice_id": "default", "voice_rate": 175, "voice_volume": 0.92, "tts_mode": "auto", "edge_voice": "en-US-AriaNeural"}

    def save_config(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    def init_tts(self):
        if not HAS_PYTTSX3:
            self.engine = None
            return
        try:
            self.engine = pyttsx3.init()
            voices = self.engine.getProperty('voices')
            target_id = self.config.get("voice_id", "default")
            if target_id != "default" and voices:
                for v in voices:
                    if v.id == target_id:
                        self.engine.setProperty('voice', v.id)
                        break
            # Cleaner prosody
            self.engine.setProperty('rate', int(self.config.get("voice_rate", 175)))
            self.engine.setProperty('volume', float(self.config.get("voice_volume", 0.92)))
        except Exception as e:
            print(f"[VoiceEngine] pyttsx3 init failed: {e}")
            self.engine = None

    def list_voices(self):
        """Return list of available voices for picker UI - now includes Edge neural voices"""
        # Start with system voices
        system_voices = []
        try:
            if not self.engine and HAS_PYTTSX3:
                self.init_tts()
            voices = self.engine.getProperty('voices') if self.engine else []
            for v in voices:
                system_voices.append({
                    "id": v.id,
                    "name": v.name + " (System)",
                    "lang": "en-US",
                    "engine": "pyttsx3",
                    "quality": "standard"
                })
        except:
            pass

        # Edge neural voices (nicer, cleaner) - curated free list
        edge_voices = [
            {"id": "en-US-AriaNeural", "name": "Aria — English US Female (Neural, Cleaner)", "lang": "en-US", "engine": "edge", "quality": "neural"},
            {"id": "en-US-JennyNeural", "name": "Jenny — English US Female (Neural, Warm)", "lang": "en-US", "engine": "edge", "quality": "neural"},
            {"id": "en-US-GuyNeural", "name": "Guy — English US Male (Neural, Clean)", "lang": "en-US", "engine": "edge", "quality": "neural"},
            {"id": "en-GB-SoniaNeural", "name": "Sonia — English UK Female (Neural)", "lang": "en-GB", "engine": "edge", "quality": "neural"},
            {"id": "en-GB-RyanNeural", "name": "Ryan — English UK Male (Neural)", "lang": "en-GB", "engine": "edge", "quality": "neural"},
            {"id": "es-ES-ElviraNeural", "name": "Elvira — Spanish Female (Neural)", "lang": "es-ES", "engine": "edge", "quality": "neural"},
            {"id": "fr-FR-DeniseNeural", "name": "Denise — French Female (Neural)", "lang": "fr-FR", "engine": "edge", "quality": "neural"},
            {"id": "de-DE-KatjaNeural", "name": "Katja — German Female (Neural)", "lang": "de-DE", "engine": "edge", "quality": "neural"},
            {"id": "ja-JP-NanamiNeural", "name": "Nanami — Japanese Female (Neural)", "lang": "ja-JP", "engine": "edge", "quality": "neural"},
            {"id": "hi-IN-SwaraNeural", "name": "Swara — Hindi Female (Neural)", "lang": "hi-IN", "engine": "edge", "quality": "neural"},
            {"id": "ar-SA-ZariyahNeural", "name": "Zariyah — Arabic Female (Neural)", "lang": "ar-SA", "engine": "edge", "quality": "neural"},
            {"id": "pt-BR-FranciscaNeural", "name": "Francisca — Portuguese BR Female (Neural)", "lang": "pt-BR", "engine": "edge", "quality": "neural"},
        ]

        # Combine: neural first (nicer), then system
        combined = edge_voices + system_voices

        if not combined:
            combined = [
                {"id": "en-US-AriaNeural", "name": "Aria — English US Female (Neural, Cleaner)", "lang": "en-US", "engine": "edge", "quality": "neural"},
                {"id": "default", "name": "Microsoft David - English (US) (System)", "lang": "en-US", "engine": "pyttsx3", "quality": "standard"},
            ]
        return combined

    def set_voice(self, voice_id):
        self.config["voice_id"] = voice_id
        # Detect engine
        if voice_id.endswith("Neural"):
            self.config["edge_voice"] = voice_id
            self.config["tts_mode"] = "edge"
        else:
            # System voice
            if self.engine:
                try:
                    self.engine.setProperty('voice', voice_id)
                except:
                    pass
        self.save_config()

    def set_language(self, lang_code, lang_name):
        self.config["language"] = lang_code
        self.config["language_name"] = lang_name
        # Auto-pick matching neural voice if not manually set
        if "edge_voice" not in self.config or self.config.get("edge_voice","").startswith("en-"):
            mapping = {
                "en-US": "en-US-AriaNeural",
                "en-GB": "en-GB-SoniaNeural",
                "es-ES": "es-ES-ElviraNeural",
                "fr-FR": "fr-FR-DeniseNeural",
                "de-DE": "de-DE-KatjaNeural",
                "ja-JP": "ja-JP-NanamiNeural",
                "hi-IN": "hi-IN-SwaraNeural",
                "ar-SA": "ar-SA-ZariyahNeural",
                "pt-BR": "pt-BR-FranciscaNeural",
            }
            if lang_code in mapping:
                self.config["edge_voice"] = mapping[lang_code]
        self.save_config()

    def _clean_text_for_speech(self, text):
        """Make speech nicer & cleaner: remove markdown, add pauses, normalize"""
        if not text:
            return ""
        # Remove markdown
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        text = re.sub(r'`(.*?)`', r'\1', text)
        text = re.sub(r'#+ ', '', text)
        # Replace URLs
        text = re.sub(r'https?://\S+', ' ', text)
        # Clean multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        # Add slight pause after sentences for cleaner prosody (edge handles SSML, but text punctuation helps)
        # Ensure sentences end with proper pause
        text = text.replace(' .', '.')
        # Limit very long text for TTS (first 800 chars for speech, full remains in overlay)
        if len(text) > 850:
            # Cut at sentence boundary
            cut = text[:820]
            last_dot = cut.rfind('. ')
            if last_dot > 400:
                text = cut[:last_dot+1] + " And more details are shown on screen."
            else:
                text = cut + "..."
        return text

    def speak(self, text, lang=None):
        """Speak text out loud - nicer & cleaner pipeline: Edge Neural -> gTTS -> pyttsx3"""
        if not text:
            return
        clean = self._clean_text_for_speech(text)
        if not clean:
            return

        def _speak():
            # 1. Try Edge TTS (nicest, free, neural, no key)
            if HAS_EDGE and self.config.get("tts_mode", "auto") in ["auto", "edge"]:
                try:
                    voice = self.config.get("edge_voice", "en-US-AriaNeural")
                    # Use language to pick voice if needed
                    lang_code = lang or self.config.get("language", "en-US")
                    # Map lang to voice if mismatch
                    if lang_code and not voice.startswith(lang_code.split('-')[0]):
                        # Keep selected voice but it's okay - edge can speak any language with accent
                        pass
                    # Edge TTS async
                    async def _edge_speak():
                        # Use +5% rate for cleaner, slightly slower than default, and soft pitch
                        communicate = edge_tts.Communicate(clean, voice, rate="+0%", volume="+8%")
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                            tmp_path = tmp.name
                        await communicate.save(tmp_path)
                        return tmp_path

                    # Run asyncio
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        mp3_path = loop.run_until_complete(_edge_speak())
                        loop.close()
                    except RuntimeError:
                        # If loop already running
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            mp3_path = pool.submit(asyncio.run, _edge_speak()).result()

                    # Play mp3
                    self._play_mp3(mp3_path)
                    try:
                        os.unlink(mp3_path)
                    except:
                        pass
                    print(f"[TTS] Edge Neural spoke ({voice}): {clean[:60]}...")
                    return
                except Exception as e:
                    print(f"[TTS Edge failed, falling back] {e}")

            # 2. Try gTTS (clean Google voice, free)
            if HAS_GTTS and self.config.get("tts_mode", "auto") in ["auto", "gtts", "edge"]:
                try:
                    lang_code = (lang or self.config.get("language", "en-US")).split('-')[0].lower()
                    # gTTS language map
                    if lang_code not in ['en','es','fr','de','ja','hi','ar','pt']:
                        lang_code = 'en'
                    tts = gTTS(text=clean, lang=lang_code, slow=False)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                        tmp_path = tmp.name
                    tts.save(tmp_path)
                    self._play_mp3(tmp_path)
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass
                    print(f"[TTS] gTTS spoke ({lang_code}): {clean[:60]}...")
                    return
                except Exception as e:
                    print(f"[TTS gTTS failed] {e}")

            # 3. Fallback pyttsx3 (offline, reliable)
            try:
                if self.engine:
                    # Cleaner settings: slower, softer
                    self.engine.setProperty('rate', 168)
                    self.engine.setProperty('volume', 0.92)
                    self.engine.say(clean)
                    self.engine.runAndWait()
                    print(f"[TTS] pyttsx3 spoke: {clean[:60]}...")
                else:
                    print(f"[TTS Fallback] Would speak: {clean[:80]}...")
            except RuntimeError:
                try:
                    if HAS_PYTTSX3:
                        self.engine = pyttsx3.init()
                        self.engine.setProperty('rate', 168)
                        self.engine.say(clean)
                        self.engine.runAndWait()
                except Exception as e:
                    print(f"[TTS] Final fallback failed: {e}")
            except Exception as e:
                print(f"[TTS] Error: {e}")

        t = threading.Thread(target=_speak, daemon=True)
        t.start()
        return t

    def _play_mp3(self, path):
        """Play mp3 file - try pygame, then playsound, then os start"""
        # Try pygame
        if HAS_PYGAME:
            try:
                pygame.mixer.init()
                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    import time
                    time.sleep(0.1)
                pygame.mixer.quit()
                return
            except Exception as e:
                print(f"[Play pygame fail] {e}")
                try:
                    pygame.mixer.quit()
                except:
                    pass
        # Try playsound
        try:
            from playsound import playsound
            playsound(path)
            return
        except:
            pass
        # Try system player
        try:
            if os.name == 'nt':
                os.system(f'start /min wmplayer "{path}" >nul 2>&1')
                import time
                time.sleep(len(self._clean_text_for_speech(path)) * 0.06 + 2)
            else:
                os.system(f'mpg123 "{path}" 2>/dev/null || ffplay -nodisp -autoexit "{path}" 2>/dev/null || aplay "{path}" 2>/dev/null')
        except Exception as e:
            print(f"[Play system fail] {e}")

    def speak_blocking(self, text):
        t = self.speak(text)
        if t:
            t.join(timeout=25)

    def listen(self, timeout=7, phrase_limit=10, language=None):
        """
        Listen via microphone and return transcribed text.
        language: BCP-47 like en-US, es-ES, etc.
        """
        if not HAS_SR or not self.recognizer:
            return None, "mic_error: SpeechRecognition not installed. pip install -r requirements.txt"
        lang = language or self.config.get("language", "en-US")
        try:
            with sr.Microphone() as source:
                print(f"[STT] Listening ({lang})... speak now!")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.7)
                try:
                    audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
                except sr.WaitTimeoutError:
                    return None, "timeout"

                print("[STT] Recognizing...")
                try:
                    text = self.recognizer.recognize_google(audio, language=lang)
                    print(f"[STT] Heard: {text}")
                    return text, None
                except sr.UnknownValueError:
                    return None, "not_understood"
                except sr.RequestError as e:
                    try:
                        text = self.recognizer.recognize_sphinx(audio)
                        return text, None
                    except:
                        return None, f"api_error: {e}"
        except OSError as e:
            return None, f"mic_error: No microphone found. {e}"
        except Exception as e:
            return None, f"error: {e}"

    def test_voice(self, voice_id=None, text=None):
        lang = self.config.get("language_name", "English")
        # Nicer test sentence
        text = text or f"Hello! This is your new cleaner voice speaking in {lang}. I sound much more natural now, with softer tone and clearer pronunciation. How does this sound?"
        old_id = self.config.get("voice_id")
        if voice_id and voice_id != old_id:
            self.set_voice(voice_id)
        self.speak_blocking(text)

if __name__ == "__main__":
    ve = VoiceEngine()
    print("Voices:", [v["name"] for v in ve.list_voices()][:5])
    ve.test_voice(text="Hello! I am your VoiceBox assistant with a much nicer, cleaner neural voice. I can now help you write essays, stories, and anything you need using free Llama AI and Wikipedia.")
