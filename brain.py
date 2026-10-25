import json
import os
import re
import threading
from datetime import datetime

from openai import OpenAI

import persona
import tools
from memory import Memory

# Defaults point at Nebius Token Factory. Any OpenAI-compatible endpoint works by changing
# LLM_BASE_URL / LLM_API_KEY / LLM_MODEL (e.g. a local Ollama at http://localhost:11434/v1).
BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
MODEL = os.environ.get("LLM_MODEL") or os.environ.get("NEBIUS_MODEL", "nvidia/nemotron-3-super-120b-a12b")

THINK = re.compile(r"<think>.*?</think>", re.S)

EXTRACT_PROMPT = """You maintain long-term memory for a personal assistant.
From the exchange below, list NEW durable facts about the user worth remembering
(name, people in their life, projects, preferences, routines, goals, things they care about).
Rules: short third-person statements. Skip small talk, one-off requests, and anything already known.
Never store passwords, ID numbers, card numbers, or other secrets. If nothing qualifies, return [].
Return ONLY a JSON array of strings.

Already known:
{known}

Exchange:
User: {user}
Assistant: {assistant}"""


def clean(text):
    t = THINK.sub("", text or "")
    if "</think>" in t:
        t = t.split("</think>")[-1]
    return t.strip()


class Brain:
    def __init__(self, profile="personal", voice=False):
        key = os.environ.get("LLM_API_KEY") or os.environ.get("NEBIUS_API_KEY")
        if not key:
            raise SystemExit("No API key. Set NEBIUS_API_KEY (or LLM_API_KEY) in .env")
        self.client = OpenAI(base_url=BASE_URL, api_key=key)
        self.profile = profile
        self.voice = voice
        self.memory = Memory()
        self.history = self.memory.load_history()

    def _system(self):
        now = datetime.now().strftime("%A, %d %B %Y, %I:%M %p")
        return (
            f"{persona.build(self.profile, self.voice)}\n"
            f"Current time: {now}\n\n"
            f"What you know about the user:\n{self.memory.as_text()}"
        )

    def _window(self):
        msgs = self.history[-24:]
        # never start mid tool-call sequence
        while msgs and msgs[0]["role"] != "user":
            msgs = msgs[1:]
        return msgs

    def respond(self, text):
        self.history.append({"role": "user", "content": text})
        for _ in range(5):
            r = self.client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": self._system()}] + self._window(),
                tools=tools.SCHEMAS,
                temperature=0.8,
                max_tokens=600,
            )
            m = r.choices[0].message
            if m.tool_calls:
                self.history.append({
                    "role": "assistant",
                    "content": m.content or "",
                    "tool_calls": [
                        {"id": tc.id, "type": "function",
                         "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in m.tool_calls
                    ],
                })
                for tc in m.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    out = tools.run(tc.function.name, args, self.memory)
                    self.history.append({"role": "tool", "tool_call_id": tc.id, "content": out})
                continue
            reply = clean(m.content) or "Sorry, I blanked. Say that again?"
            self.history.append({"role": "assistant", "content": reply})
            self.memory.save_history(self.history)
            threading.Thread(target=self._extract, args=(text, reply), daemon=True).start()
            return reply
        return "I tied myself in knots with my own tools there. Try me again?"

    def _extract(self, user, assistant):
        try:
            r = self.client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": EXTRACT_PROMPT.format(
                    known=self.memory.as_text(), user=user, assistant=assistant)}],
                temperature=0,
                max_tokens=300,
            )
            raw = clean(r.choices[0].message.content)
            match = re.search(r"\[.*\]", raw, re.S)
            if not match:
                return
            for fact in json.loads(match.group(0)):
                if isinstance(fact, str):
                    self.memory.add(fact)
        except Exception:
            pass  # memory extraction is best-effort
