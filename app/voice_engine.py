"""
OverlayOS — Voice Engine
Speech-to-text and text-to-speech on background threads.
"""
import threading
import pyttsx3
from PyQt5.QtCore import QObject, pyqtSignal

# Lazy imports for optional dependencies
_sr = None
def _get_sr():
    global _sr
    if _sr is None:
        import speech_recognition as sr
        _sr = sr
    return _sr


class VoiceEngine(QObject):
    transcript_ready = pyqtSignal(str)       # Final transcription
    interim_update = pyqtSignal(str)         # Partial text
    listening_started = pyqtSignal()
    listening_stopped = pyqtSignal()
    speech_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._listening = False
        self._speak_lock = threading.Lock()
        self._tts_engine = None
        self._init_tts()

    def _init_tts(self):
        try:
            self._tts_engine = pyttsx3.init()
            self._tts_engine.setProperty('rate', 175)
            self._tts_engine.setProperty('volume', 0.85)
            voices = self._tts_engine.getProperty('voices')
            # Prefer a female voice if available
            for v in voices:
                if 'zira' in v.name.lower() or 'female' in v.name.lower():
                    self._tts_engine.setProperty('voice', v.id)
                    break
        except Exception as e:
            print(f"[Voice] TTS init error: {e}")

    def set_rate(self, rate: int):
        if self._tts_engine:
            self._tts_engine.setProperty('rate', rate)

    @property
    def is_listening(self):
        return self._listening

    def start_listening(self):
        if self._listening:
            return
        self._listening = True
        self.listening_started.emit()
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def stop_listening(self):
        self._listening = False
        self.listening_stopped.emit()

    def _listen_loop(self):
        try:
            sr = _get_sr()
            recognizer = sr.Recognizer()
            recognizer.energy_threshold = 300
            recognizer.dynamic_energy_threshold = True

            with sr.Microphone() as mic:
                while self._listening:
                    try:
                        self.interim_update.emit("Listening...")
                        audio = recognizer.listen(mic, timeout=5, phrase_time_limit=15)
                        self.interim_update.emit("Processing speech...")
                        text = recognizer.recognize_google(audio)
                        if text.strip():
                            self.transcript_ready.emit(text.strip())
                    except sr.WaitTimeoutError:
                        continue
                    except sr.UnknownValueError:
                        continue
                    except sr.RequestError as e:
                        self.error_occurred.emit(f"Speech API error: {e}")
                        break
        except Exception as e:
            self.error_occurred.emit(f"Mic error: {e}")
        finally:
            self._listening = False
            self.listening_stopped.emit()

    def speak(self, text: str):
        threading.Thread(target=self._speak_thread, args=(text,), daemon=True).start()

    def _speak_thread(self, text: str):
        with self._speak_lock:
            try:
                if self._tts_engine:
                    self._tts_engine.say(text)
                    self._tts_engine.runAndWait()
            except Exception as e:
                print(f"[Voice] TTS error: {e}")
            finally:
                self.speech_finished.emit()

    def stop_speaking(self):
        try:
            if self._tts_engine:
                self._tts_engine.stop()
        except:
            pass
