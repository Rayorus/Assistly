"""
Assistly — Voice Engine
Speech-to-text and text-to-speech on background threads.
"""
import threading
from PyQt5.QtCore import QObject, pyqtSignal
import asyncio
import os
import tempfile
import pygame

# Lazy imports for optional dependencies
_sr = None
def _get_sr():
    global _sr
    if _sr is None:
        import speech_recognition as sr
        _sr = sr
    return _sr

try:
    import edge_tts
    pygame.mixer.init()
except Exception as e:
    print(f"[Voice] Edge-TTS init error: {e}")

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
        self._stop_playback = False

    def set_rate(self, rate: int):
        pass # edge-tts uses built in rates

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
        self._stop_playback = False
        threading.Thread(target=self._speak_thread, args=(text,), daemon=True).start()

    def _speak_thread(self, text: str):
        with self._speak_lock:
            try:
                # Remove Markdown for cleaner speech
                import re
                clean_text = re.sub(r'[*_#]', '', text)
                clean_text = re.sub(r'```.*?```', 'code block', clean_text, flags=re.DOTALL)
                
                async def _generate():
                    voice = "en-US-GuyNeural"  # Confident casual male voice
                    communicate = edge_tts.Communicate(clean_text, voice)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                        temp_path = fp.name
                    await communicate.save(temp_path)
                    return temp_path

                path = asyncio.run(_generate())
                
                if not self._stop_playback:
                    pygame.mixer.music.load(path)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy() and not self._stop_playback:
                        pygame.time.Clock().tick(10)
                    if self._stop_playback:
                        pygame.mixer.music.stop()
                    pygame.mixer.music.unload()

                try:
                    os.remove(path)
                except:
                    pass

            except Exception as e:
                print(f"[Voice] TTS error: {e}")
            finally:
                self.speech_finished.emit()

    def stop_speaking(self):
        self._stop_playback = True
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except:
            pass
