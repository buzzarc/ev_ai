import collections
import os
import subprocess
import tempfile
import threading
import time

import numpy as np
import sounddevice as sd

SR = 16000
THRESH = float(os.environ.get("MIC_THRESHOLD", "500"))  # raise if it cuts you off / hears noise
PIPER_VOICE = os.environ.get("PIPER_VOICE")  # path to a piper .onnx voice
WAKEWORD = os.environ.get("WAKEWORD", "")  # openwakeword model name, e.g. hey_jarvis. Empty = press Enter to talk


class Voice:
    def __init__(self):
        from faster_whisper import WhisperModel

        self.stt = WhisperModel(os.environ.get("WHISPER_MODEL", "small"), device="cpu", compute_type="int8")
        self.oww = None
        if WAKEWORD:
            from openwakeword.model import Model

            self.oww = Model(wakeword_models=[WAKEWORD], inference_framework="onnx")
        self.lock = threading.Lock()
        self.speaking = False

    # ---------- wake word (or push-to-talk) ----------
    def wait_for_wake(self):
        if self.oww is None:
            input("[press Enter, then talk] ")
            return
        self.oww.reset()
        with sd.InputStream(samplerate=SR, channels=1, dtype="int16", blocksize=1280) as s:
            while True:
                data, _ = s.read(1280)
                if self.speaking:
                    continue
                scores = self.oww.predict(data[:, 0])
                if max(scores.values()) > 0.5:
                    return

    # ---------- listen ----------
    def listen(self, wait_s=6.0, max_s=15.0):
        """Record one utterance, return transcript ('' if nothing said)."""
        chunk = 1600  # 0.1s
        pre = collections.deque(maxlen=3)
        frames, started, silence = [], False, 0.0
        t0 = time.time()
        with sd.InputStream(samplerate=SR, channels=1, dtype="int16", blocksize=chunk) as s:
            while True:
                data, _ = s.read(chunk)
                x = data[:, 0].copy()
                rms = float(np.sqrt(np.mean(x.astype(np.float32) ** 2)))
                elapsed = time.time() - t0
                if rms > THRESH:
                    if not started:
                        started = True
                        frames.extend(pre)
                    silence = 0.0
                elif started:
                    silence += 0.1
                if started:
                    frames.append(x)
                else:
                    pre.append(x)
                    if elapsed > wait_s:
                        return ""
                if started and silence >= 1.0:
                    break
                if elapsed > max_s:
                    break
        audio = np.concatenate(frames).astype(np.float32) / 32768.0
        segs, _ = self.stt.transcribe(audio, language="en", vad_filter=True)
        return " ".join(sg.text.strip() for sg in segs).strip()

    # ---------- speak ----------
    def say(self, text):
        print(f"\n> {text}\n")
        with self.lock:
            self.speaking = True
            try:
                if PIPER_VOICE:
                    wav = os.path.join(tempfile.gettempdir(), "jarvis_tts.wav")
                    subprocess.run(["piper", "--model", PIPER_VOICE, "--output_file", wav],
                                   input=text.encode(), check=True, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
                    subprocess.run(["aplay", "-q", wav], check=False)
                else:
                    subprocess.run(["espeak-ng", "-s", "165", text], check=False)
            finally:
                time.sleep(0.3)
                self.speaking = False
