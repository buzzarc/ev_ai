import argparse
import os
import re
import threading
import time
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

import memory  # noqa: E402
import tools  # noqa: E402

NAME = os.environ.get("AI_NAME", "Ev")
BRIEFING_TIME = os.environ.get("BRIEFING_TIME", "08:30")
BYE = re.compile(r"\b(that'?s all|goodbye|bye|go to sleep|stand down)\b", re.I)

BRIEFING_PROMPT = (
    "[internal trigger, the user did not speak] It's the start of their day. Give a short, "
    "natural morning briefing: greet them, mention the date, check their reminders and notes, and "
    "if something you know about them is relevant today, mention it. Under four sentences."
)


def proactive_loop(brain, say):
    """Background thread: speaks due reminders and the daily briefing without being asked."""
    last_briefing = None
    while True:
        try:
            for text in tools.pop_due_reminders():
                say(brain.respond(f"[internal trigger] Reminder is due now: {text}. Tell the user, briefly."))
            now = datetime.now()
            if now.strftime("%H:%M") == BRIEFING_TIME and last_briefing != now.date():
                last_briefing = now.date()
                say(brain.respond(BRIEFING_PROMPT))
        except Exception as e:
            print("proactive error:", e)
        time.sleep(20)


def run_text(brain, profile):
    def say(t):
        print(f"\n{NAME.lower()}> {t}\n", flush=True)

    threading.Thread(target=proactive_loop, args=(brain, say), daemon=True).start()
    print(f"{NAME} online [{profile}]. /memory shows what I know, /quit exits.\n")
    while True:
        try:
            u = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not u:
            continue
        if u in ("/quit", "/exit"):
            break
        if u == "/memory":
            print(brain.memory.as_text())
            continue
        try:
            say(brain.respond(u))
        except Exception as e:
            print(f"[error talking to the model: {e}]")


def run_voice(brain, profile):
    from voice import Voice

    v = Voice()
    threading.Thread(target=proactive_loop, args=(brain, v.say), daemon=True).start()
    print(f"{NAME} voice [{profile}]. Ctrl+C to quit.")
    while True:
        v.wait_for_wake()
        v.say("Yeah?")
        # stay in conversation until it goes quiet, no wake needed between turns
        while True:
            text = v.listen(wait_s=6)
            if not text:
                break
            print(f"you: {text}")
            try:
                v.say(brain.respond(text))
            except Exception as e:
                print(f"[error talking to the model: {e}]")
                break
            if BYE.search(text):
                break


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=os.environ.get("PROFILE", "personal"),
                    help="memory profile: personal (phone) or professional (laptop)")
    ap.add_argument("--voice", action="store_true", help="talk instead of type (needs requirements-voice.txt)")
    args = ap.parse_args()

    profile = memory.set_profile(args.profile)
    from brain import Brain  # imported after the profile is set

    b = Brain(profile=profile, voice=args.voice)
    run_voice(b, profile) if args.voice else run_text(b, profile)
