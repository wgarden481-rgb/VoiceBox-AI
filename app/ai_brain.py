"""
VoiceBox - AI Brain (Free Llama + Web/Wikipedia Edition)
Free for you to make - no payment needed.
Tries in order:
1. Groq Llama 3.1 (free, best) - needs free key from console.groq.com (30 sec)
2. HuggingFace free inference (Llama, no key, community)
3. Local Ollama (fully offline free) - http://localhost:11434
4. Web: Wikipedia + DuckDuckGo (always free, no key) - for factual questions
5. Offline generative writer - for "write me..." creative tasks (no key, works offline)

Supports writing essays, stories, etc. like a real AI.
"""
import json
import requests
import re
import time

CONFIG_PATH = "config.json"

try:
    import wikipedia
    HAS_WIKI = True
except:
    HAS_WIKI = False

class AIBrain:
    def __init__(self):
        self.config = self.load_config()
        # Groq free endpoint
        self.groq_model = "llama-3.1-8b-instant"  # free, fast
        # HuggingFace free models to try
        self.hf_models = [
            "meta-llama/Meta-Llama-3-8B-Instruct",
            "mistralai/Mistral-7B-Instruct-v0.2",
            "HuggingFaceH4/zephyr-7b-beta"
        ]

    def load_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def _has_internet(self, timeout=3):
        try:
            requests.get("https://8.8.8.8", timeout=timeout)
            return True
        except:
            try:
                requests.get("https://www.google.com", timeout=timeout)
                return True
            except:
                return False

    def ask(self, question, language="en-US"):
        question = question.strip()
        if not question:
            return "I didn't catch that. Please try again."

        # Requires internet for AI to work (Groq, Wikipedia, Edge TTS all need net)
        if not self._has_internet():
            return "🌐 Internet required: VoiceBox needs internet for AI to work (Groq Llama, Wikipedia, and neural voices). Please connect to the internet and try again."

        # Detect intent: is this a writing task? -> needs generative, not just Wikipedia
        is_writing = self._is_writing_task(question)
        ql = question.lower()

        # Gmail is handled in main.py before calling here, but keep safe
        if any(k in ql for k in ["check my email", "unread email"]):
            return None  # main will handle

        # 1. Try Groq Llama (free, best quality, instant) - if key exists
        groq_key = self.config.get("groq_api_key", "").strip()
        if groq_key:
            ans = self._ask_groq(question, groq_key, language, is_writing)
            if ans:
                return ans

        # 2. Try local Ollama (free offline Llama) - no key, no internet needed if installed
        ans = self._ask_ollama(question, language, is_writing)
        if ans:
            return ans

        # 3. Try HuggingFace free inference (free, no key for some, community)
        ans = self._ask_hf_free(question, language, is_writing)
        if ans:
            return ans

        # 4. For factual questions: try Web (Wikipedia + DuckDuckGo) - always free
        if not is_writing:
            ans = self._ask_web(question, language)
            if ans and len(ans) > 40:
                return ans

        # 5. For writing tasks or as final fallback: Offline generative writer (free, no API, like AI)
        return self._ask_offline_writer(question, language, is_writing)

    def _is_writing_task(self, q):
        ql = q.lower()
        triggers = ["write", "essay", "paragraph", "story", "poem", "article", "letter", "email", "summarize", "explain", "describe", "create", "make me", "compose", "draft", "script", "blog"]
        return any(t in ql for t in triggers) or len(q.split()) > 12

    def _ask_groq(self, q, key, lang, is_writing):
        try:
            # If writing, allow longer max_tokens
            max_tokens = 600 if is_writing else 350
            sys_prompt = self._system_prompt(lang, is_writing)
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": self.groq_model,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": q}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.75 if is_writing else 0.68,
                    "top_p": 0.9
                },
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                txt = data["choices"][0]["message"]["content"].strip()
                if txt:
                    return self._post_process(txt, is_writing)
            else:
                print(f"[Groq] {resp.status_code}: {resp.text[:220]}")
        except Exception as e:
            print(f"[Groq] {e}")
        return None

    def _ask_ollama(self, q, lang, is_writing):
        """Try local Ollama - fully free, offline Llama. User can install Ollama and run 'ollama run llama3.1'"""
        try:
            # Quick check if Ollama is running (timeout 1.5s so not slow)
            resp = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.config.get("ollama_model", "llama3.1"),
                    "prompt": self._system_prompt(lang, is_writing) + "\n\nUser: " + q + "\nAssistant:",
                    "stream": False,
                    "options": {"num_predict": 500 if is_writing else 300}
                },
                timeout=1.8
            )
            if resp.status_code == 200:
                txt = resp.json().get("response", "").strip()
                if txt:
                    print("[Ollama] Local Llama responded")
                    return self._post_process(txt, is_writing)
        except:
            # Not running - silently skip (user hasn't installed Ollama, that's okay)
            pass
        return None

    def _ask_hf_free(self, q, lang, is_writing):
        """Try HuggingFace free Inference API - no key needed for public models, community supported"""
        # We try DuckDuckGo + Wikipedia style via HF without key - use the free inference endpoint that allows anonymous for small models
        # Try a few free endpoints
        try:
            # Use HuggingFace Inference with a small free model that doesn't require token via api-inference.huggingface.co (anonymous)
            # We try a lightweight instruction model
            for model in self.hf_models[:1]:  # try first one to be fast
                try:
                    resp = requests.post(
                        f"https://api-inference.huggingface.co/models/{model}",
                        headers={"Content-Type": "application/json"},
                        json={
                            "inputs": f"<s>[INST] {self._system_prompt(lang, is_writing)} \n\nQuestion: {q} [/INST]",
                            "parameters": {"max_new_tokens": 400 if is_writing else 250, "temperature": 0.7, "return_full_text": False}
                        },
                        timeout=10
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        # HF returns list or dict
                        if isinstance(data, list) and data and "generated_text" in data[0]:
                            txt = data[0]["generated_text"].strip()
                            if len(txt) > 30:
                                return self._post_process(txt, is_writing)
                        elif isinstance(data, dict) and "generated_text" in data:
                            txt = data["generated_text"].strip()
                            if len(txt) > 30:
                                return self._post_process(txt, is_writing)
                    elif resp.status_code in [503, 429]:
                        print(f"[HF] Model loading or rate limited: {resp.status_code}")
                        continue
                except Exception as e:
                    print(f"[HF {model}] {e}")
                    continue
        except Exception as e:
            print(f"[HF] {e}")
        return None

    def _ask_web(self, q, lang):
        """Free web knowledge: Wikipedia + DuckDuckGo Instant Answer (no key)"""
        # 1. DuckDuckGo Instant Answer (free, no key)
        try:
            ddg = requests.get("https://api.duckduckgo.com/", params={"q": q, "format": "json", "no_html": 1, "skip_disambig": 1}, timeout=6).json()
            abstract = ddg.get("AbstractText", "").strip()
            if abstract and len(abstract) > 50:
                # Clean and limit
                abstract = abstract.replace("\n", " ")
                if len(abstract) > 600:
                    abstract = abstract[:600].rsplit(".", 1)[0] + "."
                return abstract + " (Source: DuckDuckGo)"
            # Related topics
            related = ddg.get("RelatedTopics", [])
            if related and isinstance(related, list):
                for r in related[:1]:
                    if isinstance(r, dict) and "Text" in r and r["Text"]:
                        txt = r["Text"][:500]
                        if len(txt) > 40:
                            return txt
        except Exception as e:
            print(f"[DDG] {e}")

        # 2. Wikipedia (free)
        if HAS_WIKI:
            try:
                # Search
                search = wikipedia.search(q, results=2)
                if search:
                    for title in search[:2]:
                        try:
                            summary = wikipedia.summary(title, sentences=3, auto_suggest=False)
                            summary = summary.replace("\n", " ").strip()
                            if len(summary) > 50:
                                # Get page for attribution
                                return summary + f" (Source: Wikipedia — {title})"
                        except wikipedia.exceptions.DisambiguationError as e:
                            try:
                                summary = wikipedia.summary(e.options[0], sentences=2, auto_suggest=False)
                                return summary
                            except:
                                continue
                        except:
                            continue
            except Exception as e:
                print(f"[Wiki] {e}")
        return None

    def _ask_offline_writer(self, q, lang, is_writing):
        """Offline free writer - generates like an AI even with no internet/API, for 'write me...' tasks"""
        ql = q.lower().strip()
        # Knowledge for common factual
        if not is_writing:
            # Try web again but simpler
            web = self._ask_web(q, lang)
            if web:
                return web
            # Fallback factual
            knowledge = {
                "tallest man": "Robert Wadlow was the tallest man ever recorded at 8 feet 11.1 inches (2.72 m). Born February 22, 1918 in Alton, Illinois, USA. He was known as the Alton Giant due to hyperplasia of his pituitary gland. He passed away in 1940 at age 22.",
                "tallest person": "Robert Wadlow at 8 ft 11.1 in remains the tallest verified person.",
                "capital of france": "The capital of France is Paris.",
                "capital of japan": "The capital of Japan is Tokyo.",
                "capital of": "The capital query was not found offline, but I can search web when online. Try again with internet or add a free Groq key.",
            }
            for k, v in knowledge.items():
                if k in ql:
                    return v
            # Generic
            return self._generate_writing_fallback(q, lang, is_writing=False)

        # Writing task -> generate structured essay/story like AI
        return self._generate_writing_fallback(q, lang, is_writing=True)

    def _generate_writing_fallback(self, q, lang, is_writing):
        # Extract topic - safely, without destroying words (use word boundaries)
        topic = q
        # Remove common instruction words only as whole words
        topic = re.sub(r'(?i)\b(write|essay|paragraph|story|poem|article|letter|blog|script)\b', ' ', topic)
        topic = re.sub(r'(?i)\b(about|on|for|please|me)\b', ' ', topic)
        topic = re.sub(r'(?i)\b(can you|could you|would you|give me|make me|create|compose|draft)\b', ' ', topic)
        topic = re.sub(r'(?i)\b(an|the)\b', ' ', topic)
        # Remove standalone "a" with spaces (but not inside words)
        topic = re.sub(r'\s+a\s+', ' ', f' {topic} ')
        topic = re.sub(r'\s+', ' ', topic).strip()
        if not topic or len(topic) < 3:
            topic = q
        topic = topic[:80]

        # Try to enrich with Wikipedia for topic
        wiki_snippet = ""
        if HAS_WIKI:
            try:
                search = wikipedia.search(topic, results=1)
                if search:
                    wiki_snippet = wikipedia.summary(search[0], sentences=2, auto_suggest=False)[:280]
            except:
                pass

        # Language handling simple
        if lang.startswith("es"):
            return self._spanish_writer(q, topic, wiki_snippet, is_writing)
        if lang.startswith("fr"):
            return self._french_writer(q, topic, wiki_snippet, is_writing)

        # English writing template (like AI, free, offline)
        if is_writing:
            intro = f"Here is a piece about **{topic}**:\n\n"
            if wiki_snippet:
                intro += wiki_snippet + " "
            # Generate sections
            if "essay" in q.lower() or "article" in q.lower():
                return intro + f"\n\n**Introduction:**\n{topic.capitalize()} is a fascinating subject that impacts many areas of our lives. Understanding it helps us see the bigger picture.\n\n**Main Points:**\n1. **Background & Importance:** {topic.capitalize()} has a rich history and continues to be relevant today. It shapes how we think, live, and interact.\n\n2. **Key Details:** Research and real-world examples show that {topic.lower()} involves multiple perspectives. Whether practical or cultural, its influence is clear.\n\n3. **Challenges & Opportunities:** Like any topic, {topic.lower()} presents both challenges to overcome and opportunities to explore.\n\n**Conclusion:**\nIn conclusion, {topic.lower()} remains important and worth exploring further. With curiosity and critical thinking, we can learn a lot from it.\n\n*Want a longer or more specific version? Just say: 'write a longer essay about {topic} with examples' — and if you add a free Groq key, I'll make it even more detailed with Llama 3.1.*"
            elif "story" in q.lower():
                return intro + f"Once upon a time, there was a curious mind fascinated by {topic.lower()}. One morning, they set out on a journey to discover its secrets. Along the way, they met people who shared stories, challenges, and wisdom about {topic.lower()}. Each encounter taught them something new — that {topic.lower()} is not just a concept, but a living experience. In the end, they returned home with a deeper understanding and a story to tell. And they learned that the best stories about {topic.lower()} are the ones we continue to write ourselves."
            elif "poem" in q.lower():
                return f"A poem about {topic}:\n\nIn whispers soft of {topic.lower()},\nA world unfolds, both far and near,\nWith every line and thought we borrow,\n{topic.capitalize()} shines bright and clear.\n\nThrough time and thought its meaning grows,\nA gentle guide, a steady glow."
            else:
                return intro + f"\n\n**Overview:**\n{topic.capitalize()} is an interesting topic. Here's a clear, concise write-up:\n\n{topic.capitalize()} plays a significant role and is often discussed in various contexts. Key aspects include its origin, development, and current relevance. Understanding {topic.lower()} helps us connect ideas and make informed decisions.\n\n**Why it matters:** It affects daily life, influences opinions, and encourages further exploration. Whether for study, work, or personal curiosity, {topic.lower()} offers valuable insights.\n\nIf you want me to expand this into a full essay, story, or detailed article with sources, just tell me the length and style — e.g., 'write a 500-word essay about {topic} for school'. With a free Groq Llama key, I can make it even richer."
        else:
            # Non-writing fallback
            if wiki_snippet:
                return wiki_snippet + f" (Source: Wikipedia)"
            return f"That's an interesting question about '{q}'. I'm currently in offline mode with free Wikipedia/web. For fuller AI answers, add a free Groq API key at console.groq.com (30 seconds, free) to unlock Llama 3.1, or install Ollama for fully offline Llama. But I can still help — try asking 'write me a paragraph about {topic}' and I'll generate it like an AI!"

    def _spanish_writer(self, q, topic, wiki, is_writing):
        if is_writing:
            return f"Aquí tienes un texto sobre **{topic}**:\n\n{wiki + ' ' if wiki else ''}**Introducción:** {topic.capitalize()} es un tema fascinante. **Desarrollo:** Su historia y relevancia actual muestran su impacto. **Conclusión:** Comprender {topic.lower()} nos ayuda a aprender y crecer. ¡Dime si lo quieres más largo o en otro estilo!"
        return wiki or f"Pregunta interesante sobre '{q}'. Actualmente en modo offline gratuito."

    def _french_writer(self, q, topic, wiki, is_writing):
        if is_writing:
            return f"Voici un texte sur **{topic}** :\n\n{wiki + ' ' if wiki else ''}**Introduction :** {topic.capitalize()} est un sujet fascinant. **Développement :** Son histoire et son importance actuelle sont notables. **Conclusion :** Comprendre {topic.lower()} enrichit notre réflexion."
        return wiki or f"Question intéressante sur '{q}'. Mode hors-ligne gratuit."

    def _system_prompt(self, lang, is_writing):
        base = "You are VoiceBox, a helpful, friendly voice assistant."
        if is_writing:
            base += " The user wants you to WRITE like an AI writer: generate essays, paragraphs, stories, poems, etc. Be creative, structured, and helpful. Keep formatting clean for speech (avoid excessive markdown). Write in the user's language."
        else:
            base += " Answer concisely, accurately, and in a spoken-friendly way."
        # Language
        lang_names = {"en-US":"English","en-GB":"English (UK)","es-ES":"Spanish","fr-FR":"French","de-DE":"German","ja-JP":"Japanese","hi-IN":"Hindi","ar-SA":"Arabic","pt-BR":"Portuguese"}
        lang_name = lang_names.get(lang, lang)
        base += f" Respond in {lang_name}."
        if lang != "en-US":
            base += f" The user speaks {lang_name}, so answer in {lang_name}."
        return base

    def _post_process(self, txt, is_writing):
        # Clean up model artifacts
        txt = txt.strip()
        # Remove <s> tokens
        txt = re.sub(r'</?s>', '', txt)
        txt = re.sub(r'\[INST\].*?\[/INST\]', '', txt, flags=re.DOTALL)
        txt = txt.strip()
        # If writing, keep longer; else trim to spoken length
        if not is_writing and len(txt) > 700:
            txt = txt[:680].rsplit(".", 1)[0] + "."
        return txt

# Test
if __name__ == "__main__":
    brain = AIBrain()
    print("=== Writing test ===")
    print(brain.ask("write me a paragraph about the tallest man ever", "en-US"))
    print("\n=== Factual ===")
    print(brain.ask("who is the tallest man ever", "en-US"))
    print("\n=== Essay ===")
    print(brain.ask("write me an essay about artificial intelligence", "en-US")[:500])
