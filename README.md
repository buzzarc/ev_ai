# Ev: a terminal-first personal AI that remembers you

Ev runs in your terminal, talks like a sharp adult friend (dry, fast, a bit sarcastic), and keeps long-term memory about you on your own device. Powered by NVIDIA Nemotron through Nebius Token Factory.

## Two profiles, two memories

Same code, separate memory per device:

- `personal` (phone, via Termux): friend mode. Knows your life and goals.
- `professional` (laptop): work mode. Knows your projects, deadlines and decisions.

Memory lives in `data/<profile>/` on that device and never mixes between profiles. `data/` is git-ignored.

## Setup (laptop or Termux)

```bash
git clone <repo-url> ev && cd ev
python -m venv .venv && source .venv/bin/activate   # Termux: skip the venv if it complains
pip install -r requirements.txt
cp .env.example .env    # add NEBIUS_API_KEY, optionally TAVILY_API_KEY
python main.py --profile professional      # laptop
python main.py --profile personal          # phone
```

Chat commands: `/memory` shows what Ev knows about you, `/quit` exits.

## Privacy

- Memory is stored locally as plain JSON in `data/<profile>/`. Read it, edit it, delete it.
- Only the text of each request goes to the model endpoint.
- Turn on Zero Data Retention in your Nebius Token Factory account settings, so prompts and responses are not stored after each request (per Nebius's legal quick guide).

## Tools

Current time, web search (Tavily), remember/forget, reminders (spoken or printed when due), notes. A morning briefing fires at `BRIEFING_TIME` while Ev is running.

## Voice (optional, laptop)

```bash
sudo apt install portaudio19-dev espeak-ng alsa-utils
pip install -r requirements-voice.txt piper-tts
python main.py --voice --profile professional
```

Default is press Enter to talk. Set `WAKEWORD` in `.env` (e.g. `hey_jarvis`, a model that ships with openwakeword) for hands-free. Set `PIPER_VOICE` to a Piper `.onnx` voice for a natural voice; otherwise it falls back to espeak-ng.

## Using a different model endpoint

Ev uses the OpenAI-compatible API, so set `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` in `.env` to use any compatible server, such as a local Ollama.

## Files

- `persona.py`: personality and per-profile behavior. Tune the vibe here.
- `brain.py`: model calls, tool loop, background memory extraction.
- `memory.py`: per-profile facts and chat history.
- `tools.py`: tool schemas and implementations.
- `voice.py`: speech-to-text, text-to-speech, optional wake word.
- `main.py`: entrypoint, terminal chat, proactive loop.

## License

MIT. See `LICENSE`.
