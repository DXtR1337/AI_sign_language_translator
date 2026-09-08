import collections
import threading
import time

import speaker


class FakeVoice:
    id = "system-default"


class FakeEngine:
    """Engine driven through pyttsx3's external event loop API.

    ``say()`` only queues an utterance; it is reported as finished when the
    test releases it and the worker calls ``iterate()`` afterwards, which is
    how the real driver delivers ``finished-utterance``.
    """

    def __init__(self):
        self.started = threading.Event()
        self.finished = threading.Event()
        self.spoken = []
        self.properties = {}
        self.events = []
        self.callbacks = {}
        self.loops = []
        self.ended_loops = 0
        self.run_and_wait_calls = 0
        self._inLoop = False
        self._condition = threading.Condition()
        self._started_count = 0
        self._finished_count = 0
        self._releases = collections.deque()

    def connect(self, topic, cb):
        with self._condition:
            self.callbacks.setdefault(topic, []).append(cb)
            self.events.append(("connect", topic))
        return {"topic": topic, "cb": cb}

    def startLoop(self, useDriverLoop=True):
        with self._condition:
            self.loops.append(useDriverLoop)
            self.events.append(("startLoop", useDriverLoop))
            self._inLoop = True

    def endLoop(self):
        with self._condition:
            self.ended_loops += 1
            self.events.append(("endLoop",))
            self._inLoop = False

    def notify(self, topic, **kwargs):
        """Deliver a driver notification the way pyttsx3's engine does."""
        with self._condition:
            callbacks = list(self.callbacks.get(topic, ()))
        for callback in callbacks:
            callback(**kwargs)

    def getProperty(self, name):
        return [FakeVoice()] if name == "voices" else self.properties.get(name)

    def setProperty(self, name, value):
        self.properties[name] = value
        self.events.append(("set", name))

    def say(self, text):
        with self._condition:
            self.spoken.append(text)
            self.events.append(("say", text))
            self._started_count += 1
            self.started.set()
            self._condition.notify_all()

    def runAndWait(self):
        self.run_and_wait_calls += 1
        raise AssertionError("runAndWait() must not be used")

    def iterate(self):
        """Deliver the finished-utterance callback for a released utterance."""
        with self._condition:
            if self._finished_count >= self._started_count or not self._releases:
                return
            completed = self._releases.popleft()
            self._finished_count += 1
            name = self.spoken[self._finished_count - 1]
        self.notify("finished-utterance", name=name, completed=completed)

    def stop(self):
        with self._condition:
            self.finished.set()
            if self._started_count > self._finished_count + len(self._releases):
                self._releases.append(False)
            self._condition.notify_all()

    def wait_for_started(self, count=1, timeout=2):
        """Wait until the engine has been asked to say ``count`` texts."""
        with self._condition:
            return self._condition.wait_for(
                lambda: self._started_count >= count, timeout=timeout)

    def release_next(self):
        """Let the utterance that is currently in flight finish."""
        with self._condition:
            self._releases.append(True)
            self._condition.notify_all()


class StuckEngine(FakeEngine):
    """Engine that hangs inside iterate() and whose stop() does nothing."""

    def __init__(self):
        super().__init__()
        self.unblocked = threading.Event()

    def iterate(self):
        self.unblocked.wait(timeout=10)

    def stop(self):
        return None


class NeverFinishingEngine(FakeEngine):
    """Engine that never reports an utterance as finished."""

    def iterate(self):
        return None

    def stop(self):
        return None


class SpuriousCallbackEngine(FakeEngine):
    """Engine that emits one stale finished-utterance while nothing is spoken."""

    def say(self, text):
        if not self.spoken:
            self.notify("finished-utterance", name=None, completed=True)
        super().say(text)


class BreakingOnStopEngine(FakeEngine):
    """Engine that fails from iterate() as soon as it has been stopped."""

    def __init__(self):
        super().__init__()
        self.iterating = threading.Event()
        self.stopping = threading.Event()

    def iterate(self):
        self.iterating.set()
        self.stopping.wait(timeout=5)
        raise RuntimeError("driver went away")

    def stop(self):
        self.stopping.set()


class ErrorReportingEngine(FakeEngine):
    """Engine that reports a driver error instead of raising from say()."""

    def say(self, text):
        super().say(text)
        self.notify("error", name=text, exception=RuntimeError("speech failed"))


class FailingEngine(FakeEngine):
    """Engine that fails every utterance."""

    def say(self, text):
        super().say(text)
        raise RuntimeError("speech failed")


def test_create_engine_bypasses_the_init_cache(monkeypatch):
    created = []

    def fake_engine_class(*args, **kwargs):
        created.append((args, kwargs))
        return "engine"

    def forbidden_init(*args, **kwargs):
        raise AssertionError("pyttsx3.init() must not be used")

    monkeypatch.setattr(speaker.pyttsx3.engine, "Engine", fake_engine_class)
    monkeypatch.setattr(speaker.pyttsx3, "init", forbidden_init)

    assert speaker.create_engine() == "engine"
    assert created == [((), {})]


def test_worker_drives_the_external_loop_instead_of_run_and_wait(monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(speaker, "create_engine", lambda: engine)
    text_to_speech = speaker.SpeakerApp()

    try:
        text_to_speech.speak("A")
        assert engine.wait_for_started(1)

        assert engine.loops == [False]
        assert "finished-utterance" in engine.callbacks
        assert "error" in engine.callbacks
        assert (engine.events.index(("startLoop", False))
                < engine.events.index(("say", "A")))
        assert engine.run_and_wait_calls == 0
    finally:
        engine.release_next()
        assert text_to_speech.stop() is False

    assert engine.run_and_wait_calls == 0
    assert engine.ended_loops == 1


def test_speaker_coalesces_pending_texts_while_busy(monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(speaker, "create_engine", lambda: engine)
    text_to_speech = speaker.SpeakerApp(rate=180, volume=0.5)

    try:
        text_to_speech.speak("A")
        assert engine.wait_for_started(1)
        assert engine.spoken == ["A"]

        text_to_speech.speak("B")
        text_to_speech.speak("C")
        engine.release_next()

        assert engine.wait_for_started(2)
        assert engine.spoken == ["A", "C"]
        assert "voice" not in engine.properties
        assert engine.properties["rate"] == 180
        assert engine.properties["volume"] == 0.5
    finally:
        engine.release_next()
        assert text_to_speech.stop() is False


def test_stop_returns_when_the_engine_never_finishes(monkeypatch):
    engine = StuckEngine()
    monkeypatch.setattr(speaker, "create_engine", lambda: engine)
    text_to_speech = speaker.SpeakerApp()

    try:
        text_to_speech.speak("A")
        assert engine.wait_for_started(1)

        start = time.monotonic()
        timed_out = text_to_speech.stop()
        elapsed = time.monotonic() - start

        assert elapsed < 3
        assert timed_out is True
    finally:
        engine.unblocked.set()


def test_stop_returns_promptly_when_the_callback_never_arrives(monkeypatch):
    engine = NeverFinishingEngine()
    monkeypatch.setattr(speaker, "create_engine", lambda: engine)
    text_to_speech = speaker.SpeakerApp()

    text_to_speech.speak("A")
    assert engine.wait_for_started(1)

    start = time.monotonic()
    timed_out = text_to_speech.stop()
    elapsed = time.monotonic() - start

    assert elapsed < 2
    assert timed_out is False
    assert engine.ended_loops == 1


def test_second_stop_returns_immediately_after_a_timed_out_join(monkeypatch):
    engine = StuckEngine()
    monkeypatch.setattr(speaker, "create_engine", lambda: engine)
    text_to_speech = speaker.SpeakerApp()

    try:
        text_to_speech.speak("A")
        assert engine.wait_for_started(1)
        assert text_to_speech.stop() is True

        start = time.monotonic()
        timed_out = text_to_speech.stop()
        elapsed = time.monotonic() - start

        assert elapsed < 0.5
        assert timed_out is True
    finally:
        engine.unblocked.set()


def test_new_instance_creates_a_fresh_engine(monkeypatch):
    engines = []

    def factory():
        engine = FakeEngine()
        engines.append(engine)
        return engine

    monkeypatch.setattr(speaker, "create_engine", factory)

    first = speaker.SpeakerApp()
    assert first.stop() is False

    second = speaker.SpeakerApp()
    try:
        second.speak("B")
        assert engines[1].wait_for_started(1)

        assert len(engines) == 2
        assert engines[0] is not engines[1]
        assert engines[0].spoken == []
        assert engines[1].spoken == ["B"]
        assert engines[1].loops == [False]
    finally:
        engines[1].release_next()
        assert second.stop() is False


def test_rate_and_volume_changes_apply_before_the_next_utterance(monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(speaker, "create_engine", lambda: engine)
    text_to_speech = speaker.SpeakerApp()

    try:
        text_to_speech.set_rate(210)
        text_to_speech.set_volume(0.25)
        text_to_speech.speak("A")

        assert engine.wait_for_started(1)
        assert engine.properties["rate"] == 210
        assert engine.properties["volume"] == 0.25

        assert engine.events[:2] == [("set", "rate"), ("set", "volume")]
        say_index = engine.events.index(("say", "A"))
        assert engine.events.index(("set", "rate"), 2) < say_index
        assert engine.events.index(("set", "volume"), 2) < say_index
        assert engine.events[say_index:] == [("say", "A")]
    finally:
        engine.release_next()
        assert text_to_speech.stop() is False


def test_requests_after_stop_do_not_grow_the_queue(monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(speaker, "create_engine", lambda: engine)
    text_to_speech = speaker.SpeakerApp()

    assert text_to_speech.stop() is False
    assert not text_to_speech._thread.is_alive()

    for _ in range(10):
        text_to_speech.speak("A")
        text_to_speech.set_rate(210)
        text_to_speech.set_volume(0.25)

    assert text_to_speech._queue.qsize() == 0
    assert engine.spoken == []
    assert text_to_speech._rate == 210
    assert text_to_speech._volume == 0.25


def test_whitespace_only_text_is_never_queued(monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(speaker, "create_engine", lambda: engine)
    text_to_speech = speaker.SpeakerApp()

    try:
        text_to_speech.speak("   ")
        text_to_speech.speak("")
        text_to_speech.speak(None)
        assert text_to_speech._queue.qsize() == 0

        text_to_speech.speak("A")
        assert engine.wait_for_started(1)
        assert engine.spoken == ["A"]
    finally:
        engine.release_next()
        assert text_to_speech.stop() is False


def test_destroy_engine_skips_end_loop_when_no_loop_is_running():
    engine = FakeEngine()

    speaker.SpeakerApp._destroy_engine(engine)
    assert engine.ended_loops == 0

    engine.startLoop(False)
    speaker.SpeakerApp._destroy_engine(engine)
    assert engine.ended_loops == 1


def test_a_stale_callback_does_not_finish_the_next_utterance(monkeypatch):
    engine = SpuriousCallbackEngine()
    monkeypatch.setattr(speaker, "create_engine", lambda: engine)
    text_to_speech = speaker.SpeakerApp()

    try:
        text_to_speech.speak("A")
        assert engine.wait_for_started(1)

        text_to_speech.speak("B")
        assert not engine.wait_for_started(2, timeout=0.3)
        assert engine.spoken == ["A"]

        engine.release_next()
        assert engine.wait_for_started(2)
        assert engine.spoken == ["A", "B"]
    finally:
        engine.release_next()
        assert text_to_speech.stop() is False


def test_engine_is_recreated_when_an_utterance_never_finishes(monkeypatch):
    monkeypatch.setattr(speaker, "_UTTERANCE_TIMEOUT", 0.2)
    monkeypatch.setattr(speaker, "_PURGE_TIMEOUT", 0.1)
    engines = []
    recreated = threading.Event()

    def factory():
        engine = FakeEngine() if engines else NeverFinishingEngine()
        engines.append(engine)
        if len(engines) > 1:
            recreated.set()
        return engine

    monkeypatch.setattr(speaker, "create_engine", factory)
    text_to_speech = speaker.SpeakerApp()

    try:
        text_to_speech.speak("A")
        assert engines[0].wait_for_started(1)
        assert recreated.wait(timeout=3)
        assert len(engines) == 2

        text_to_speech.speak("B")
        assert engines[1].wait_for_started(1)
        assert engines[1].spoken == ["B"]
        assert engines[1].loops == [False]
    finally:
        engines[-1].release_next()
        assert text_to_speech.stop() is False


def test_a_failed_recreation_is_retried_for_the_next_text(monkeypatch):
    monkeypatch.setattr(speaker, "_UTTERANCE_TIMEOUT", 0.2)
    monkeypatch.setattr(speaker, "_PURGE_TIMEOUT", 0.1)
    created = []
    engines = []
    recreation_failed = threading.Event()
    retried = threading.Event()

    def factory():
        created.append(True)
        if len(created) == 2:
            recreation_failed.set()
            return None
        engine = NeverFinishingEngine() if len(created) == 1 else FakeEngine()
        engines.append(engine)
        if len(created) > 2:
            retried.set()
        return engine

    monkeypatch.setattr(speaker, "create_engine", factory)
    text_to_speech = speaker.SpeakerApp()

    try:
        text_to_speech.speak("A")
        assert engines[0].wait_for_started(1)
        assert recreation_failed.wait(timeout=3)

        text_to_speech.speak("B")
        assert retried.wait(timeout=3)
        assert len(created) == 3
        assert engines[1].wait_for_started(1)
        assert engines[1].spoken == ["B"]
    finally:
        engines[-1].release_next()
        assert text_to_speech.stop() is False


def test_no_engine_is_recreated_while_stopping(monkeypatch):
    created = []

    def factory():
        created.append(BreakingOnStopEngine())
        return created[-1]

    monkeypatch.setattr(speaker, "create_engine", factory)
    text_to_speech = speaker.SpeakerApp()

    text_to_speech.speak("A")
    assert created[0].wait_for_started(1)
    assert created[0].iterating.wait(timeout=2)

    assert text_to_speech.stop() is False
    assert len(created) == 1


def test_engine_is_recreated_after_a_reported_driver_error(monkeypatch):
    engines = []
    recreated = threading.Event()

    def factory():
        engine = FakeEngine() if engines else ErrorReportingEngine()
        engines.append(engine)
        if len(engines) > 1:
            recreated.set()
        return engine

    monkeypatch.setattr(speaker, "create_engine", factory)
    text_to_speech = speaker.SpeakerApp()

    try:
        text_to_speech.speak("A")
        assert engines[0].wait_for_started(1)
        # Well below _UTTERANCE_TIMEOUT: the error topic, not the timeout,
        # triggers the recreation.
        assert recreated.wait(timeout=3)
        assert len(engines) == 2

        text_to_speech.speak("B")
        assert engines[1].wait_for_started(1)
        assert engines[1].spoken == ["B"]
        assert "finished-utterance" in engines[1].callbacks
        assert "error" in engines[1].callbacks
    finally:
        engines[-1].release_next()
        assert text_to_speech.stop() is False


def test_engine_is_recreated_after_a_failed_utterance(monkeypatch):
    engines = []
    recreated = threading.Event()

    def factory():
        engine = FakeEngine() if engines else FailingEngine()
        engines.append(engine)
        if len(engines) > 1:
            recreated.set()
        return engine

    monkeypatch.setattr(speaker, "create_engine", factory)
    text_to_speech = speaker.SpeakerApp()

    try:
        text_to_speech.speak("A")
        assert engines[0].wait_for_started(1)
        assert recreated.wait(timeout=2)
        assert engines[0] is not engines[1]

        text_to_speech.speak("B")
        assert engines[1].wait_for_started(1)
        assert engines[0].spoken == ["A"]
        assert engines[1].spoken == ["B"]
        assert engines[0].ended_loops == 1
        assert engines[1].loops == [False]
        assert "finished-utterance" in engines[1].callbacks
    finally:
        engines[-1].release_next()
        assert text_to_speech.stop() is False
