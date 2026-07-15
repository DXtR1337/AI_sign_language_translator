import threading

import speaker


class FakeVoice:
    id = "system-default"


class FakeEngine:
    def __init__(self):
        self.started = threading.Event()
        self.finished = threading.Event()
        self.spoken = []
        self.properties = {}

    def getProperty(self, name):
        return [FakeVoice()] if name == "voices" else self.properties.get(name)

    def setProperty(self, name, value):
        self.properties[name] = value

    def say(self, text):
        self.spoken.append(text)

    def runAndWait(self):
        self.started.set()
        self.finished.wait(timeout=2)

    def stop(self):
        self.finished.set()


def test_speaker_coalesces_results_while_busy(monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(speaker.pyttsx3, "init", lambda: engine)
    text_to_speech = speaker.SpeakerApp()

    text_to_speech.speak("A")
    assert engine.started.wait(timeout=1)
    text_to_speech.speak("B")
    assert engine.spoken == ["A"]

    engine.finished.set()
    text_to_speech._thread.join(timeout=1)
    text_to_speech.speak("B")
    text_to_speech._thread.join(timeout=1)

    assert engine.spoken == ["A", "B"]
    assert "voice" not in engine.properties
    text_to_speech.stop()
