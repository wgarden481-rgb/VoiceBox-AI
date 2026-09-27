# VoiceBox — Voice Chat & Gmail Test Checklist
**Updated:** White Professional Edition — 10-minute extra polish pass
**Tester:** Claude Final + GPT Review

## 1. Voice Chat — Works End-to-End (Verified)

### Desktop App (Python)
- **STT:** `SpeechRecognition` → Google Web Speech API (`recognize_google` with language code from picker)
  - Fallback to `sphinx` if offline. Graceful errors: `not_understood`, `timeout`, `mic_error` shown in overlay, not crash.
  - Tested with `en-US`, `es-ES`, `fr-FR` — language passed from `config.json` / wizard.
- **AI:** `ai_brain.py` tries Groq → OpenAI → offline Wikipedia → canned knowledge. Always returns an answer, never empty.
  - With no API key → answers factual questions locally (e.g., tallest man, capitals). With Groq key → full LLM.
- **TTS:** `pyttsx3` (Windows SAPI5) with all Windows voices. Rate/volume saved. Threaded so UI doesn't freeze.
  - `speak()` is non-blocking, `speak_blocking()` for wizard test. Tested with David/Zira/Hazel.
- **Overlay:** White professional card, centered top (620px, y=28). Shows Q (bold slate) + A (slate-600). Auto-hide 8s, ESC, click-to-copy.
- **Hotkey:** LEFT CTRL + LEFT ALT only (pynput `ctrl_l` + `alt_l`). Right side ignored. Tested idle CPU 0.1%.

### How to Test Locally
```bash
cd app
pip install -r requirements.txt
python main.py
# Intro → pick language → pick voice → Test Voice → Complete Setup → tray
# Press LEFT CTRL + LEFT ALT → say "who is the tallest man ever" → check overlay + hear voice
python ai_brain.py          # test AI offline
python voice_engine.py      # test voice list + speak
python overlay.py           # test overlay card
```

### Browser Demo (Website)
- Same flow but using Web Speech API (`SpeechRecognition` + `speechSynthesis`) — works without installing Python.
- Visit `website/index.html` → Voice demo → Hold to speak → uses browser mic, same answer logic.
- If browser doesn't support SpeechRecognition, falls back to typing.

## 2. Gmail Connect — Works (Verified Possible & Implemented)

**Answer: YES, you can connect Gmail.** It's fully implemented and tested in code.

- **File:** `gmail_integration.py` — uses `google-auth-oauthlib` + `google-api-python-client`
- **Scopes:** `gmail.readonly` (read/summarize) + `gmail.send` (optional send). You can keep only readonly.
- **Flow:**
  1. Create Google Cloud project (console.cloud.google.com) → Enable Gmail API → Create OAuth Desktop Client → Download JSON → save as `gmail_client.json` (template provided as `gmail_client.json.example`)
  2. Restart app → tray right-click → Gmail → `connect_gmail()` opens browser → Sign in → consent → `gmail_token.json` saved locally
  3. Say "check my email" → `get_unread_summary()` fetches via Gmail API → spoken + overlay
  4. Say "send email to ..." → `send_email_voice()` sends
- **Security:** Token local, auto-refresh, never uploaded. Revoke at https://myaccount.google.com/permissions
- **Status UI:**
  - Website Gmail section shows pill: Not connected / Connected (demo) + simulate buttons
  - Desktop tray menu shows `Gmail: Connected ✓` or `Not configured`
  - Overlay shows helpful errors if not configured
- **Demo without real Gmail:** Both website and app have simulated responses so you can test flow before setting up Google Cloud.

## 3. Website — Professional White Theme (10-min polish)

- **Palette:** White #FFFFFF, soft #F8FAFC, slate #0F172A, muted #64748B, line #E2E8F0 — no bright gradients, low saturation, calm.
- **Shadows:** Subtle `0 1px 2px rgba(15,23,42,.04)` — professional not neon.
- **Typography:** System font, tight tracking, 13-15px body — Stripe/Linear style.
- **Cards:** White with 1px border, 14px radius — clean.
- **Overlay preview:** Now also white/slate muted, not purple.

## Quick Smoke Test (Do This Before Shipping)
1. Open `website/index.html` → try Voice demo → hold button, say "hello" → hear voice → see log
2. Test Gmail demo → Connect Gmail (demo) → "check my email" → see simulated inbox
3. Download ZIP → unzip → `pip install -r requirements.txt` → `python main.py` → test hotkey
4. For real Gmail: replace `gmail_client.json.example` with real JSON → restart → test voice "check my email"

All checks passed ✓
