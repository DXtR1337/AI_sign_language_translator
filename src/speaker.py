import logging
import queue
import threading
import time

import pyttsx3.engine


ENGINE = r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-US_ZIRA_11.0'

_SENTINEL = object()
_READY_TIMEOUT = 5.0
_JOIN_TIMEOUT = 2.0
_UTTERANCE_TIMEOUT = 15.0
_PURGE_TIMEOUT = 1.0
_ITERATE_INTERVAL = 0.02


def create_engine():
    """Create a fresh speech engine, bypassing the pyttsx3.init() cache."""
    return pyttsx3.engine.Engine()


class SpeakerApp:
    def __init__(self, rate=150, volume=0.8):
        """Initialize the TextToSpeech engine with the given rate and volume."""
        self.engine = None
        self._rate = rate
        self._volume = volume
        self._queue = queue.Queue()
        self._ready = threading.Event()
        self._utterance_done = threading.Event()
        self._stop_requested = threading.Event()
        self._in_flight = False
        self._engine_broken = False
        self._stopped = False
        self._thread = threading.Thread(
            target=self._worker, daemon=True, name="SpeakerWorker")
        self._thread.start()
        if not self._ready.wait(timeout=_READY_TIMEOUT):
            logging.error("Speech engine was not ready within %.1fs", _READY_TIMEOUT)

    def _worker(self):
        """Own the engine for its whole lifetime and speak queued texts."""
        initialized_com = self._init_com()
        try:
            if self._create_configured_engine() is not None:
                self._run_loop()
        finally:
            engine = self.engine
            self.engine = None
            self._destroy_engine(engine)
            del engine
            if initialized_com:
                self._uninit_com()

    @staticmethod
    def _init_com():
        """Initialize COM for this thread so speech callbacks are delivered here."""
        try:
            import pythoncom
        except ImportError:
            return False

        try:
            pythoncom.CoInitialize()
            return True
        except Exception:
            logging.exception("Error while initializing COM for the speech engine")
            return False

    @staticmethod
    def _uninit_com():
        """Release the COM apartment created for this thread."""
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except Exception:
            logging.exception("Error while releasing COM for the speech engine")

    @staticmethod
    def _destroy_engine(engine):
        """End the external loop and release the driver, on the worker thread."""
        if engine is None:
            return

        if getattr(engine, '_inLoop', False):
            try:
                engine.endLoop()
            except Exception:
                logging.exception("Error while ending the speech engine event loop")

        try:
            driver = getattr(getattr(engine, 'proxy', None), '_driver', None)
            destroy = getattr(driver, 'destroy', None)
            if callable(destroy):
                destroy()
        except Exception:
            logging.exception("Error while releasing the speech engine")

    def _create_configured_engine(self):
        """Create the engine, apply settings, and start its external event loop.

        The worker drives pyttsx3's external event loop (``startLoop(False)``
        plus ``iterate()``) instead of calling ``runAndWait()`` per utterance.
        In pyttsx3 2.99 ``Engine.runAndWait`` ends with ``setBusy(False)``, so
        the next ``say()`` is dispatched to the driver *before* the following
        ``runAndWait()`` queues ``endLoop``; SAPI5's loop then pumps that
        ``endLoop``, which purges the utterance that has just started. The
        result is that only the first letter is ever audible. The external loop
        keeps a single loop alive for the whole engine lifetime, so every
        utterance runs to its ``finished-utterance`` callback, and it behaves
        the same on pyttsx3 2.98, which lacks that ``setBusy`` call.
        """
        engine = None
        self._engine_broken = False
        try:
            engine = create_engine()
            engine.setProperty('rate', self._rate)
            engine.setProperty('volume', self._volume)
            self._set_default_voice(engine, ENGINE)
            engine.connect('finished-utterance', self._on_finished_utterance)
            engine.connect('error', self._on_engine_error)
            engine.startLoop(False)
            self.engine = engine
        except Exception:
            logging.exception("Error while initializing the speech engine")
            self._destroy_engine(engine)
            engine = None
        finally:
            self._ready.set()
        return engine

    def _on_finished_utterance(self, **kwargs):
        """Mark the current utterance as finished, whatever its outcome.

        Notifications delivered while no utterance is in flight are stale
        leftovers of a purged one and must not release the next utterance.
        """
        if self._in_flight:
            self._utterance_done.set()

    def _on_engine_error(self, **kwargs):
        """Report a driver error and mark the engine for recreation."""
        logging.error(
            "Speech engine reported an error: %s", kwargs.get('exception'))
        self._engine_broken = True
        self._utterance_done.set()

    @staticmethod
    def _set_default_voice(engine, voice_engine=ENGINE):
        """Set the default voice when its token is available."""
        voices = engine.getProperty('voices') or []
        if any(getattr(voice, 'id', None) == voice_engine for voice in voices):
            engine.setProperty('voice', voice_engine)

    def _recreate_engine(self):
        """Replace a broken engine so that later utterances still work."""
        engine = self.engine
        self.engine = None
        self._destroy_engine(engine)
        del engine
        if self._create_configured_engine() is None:
            logging.error("Speech engine could not be recreated, skipping utterances")

    def _run_loop(self):
        """Speak queued texts one at a time until the sentinel arrives."""
        while True:
            engine = self.engine
            pending_text, stopping = self._collect(engine, self._queue.get())
            if stopping:
                return
            if pending_text is None:
                continue
            if engine is None:
                # A previous recreation failed; retry once for this text. The
                # blocking get() and the coalescing bound the retry rate.
                engine = self._create_configured_engine()
                if engine is None:
                    logging.warning(
                        "Speech engine is still unavailable, dropping one text")
                    continue

            try:
                healthy = self._speak_and_wait(engine, pending_text)
            except Exception:
                logging.exception("Error while speaking the recognized text")
                healthy = False
            if not healthy and not self._stop_requested.is_set():
                self._recreate_engine()

    def _speak_and_wait(self, engine, text):
        """Speak one text, pumping the external loop until the engine is done.

        Returns:
            bool: False when the engine stopped responding or reported an
                  error and has to be recreated, True otherwise.
        """
        self._utterance_done.clear()
        engine.say(text)
        self._in_flight = True
        try:
            deadline = time.monotonic() + _UTTERANCE_TIMEOUT
            purged = False
            while not self._utterance_done.is_set():
                if self._stop_requested.is_set():
                    return True
                if time.monotonic() >= deadline:
                    if purged:
                        logging.warning(
                            "Speech engine did not release the utterance after"
                            " being stopped, recreating it")
                        return False
                    logging.warning(
                        "Speech engine did not finish an utterance within %.1fs,"
                        " stopping it", _UTTERANCE_TIMEOUT)
                    purged = True
                    deadline = time.monotonic() + _PURGE_TIMEOUT
                    try:
                        engine.stop()
                    except Exception:
                        logging.exception("Error while stopping the speech engine")
                engine.iterate()
                time.sleep(_ITERATE_INTERVAL)
        finally:
            self._in_flight = False
        return not self._engine_broken

    def _collect(self, engine, item):
        """Drain the queue, keeping only the newest text and applying settings."""
        pending_text = None
        stopping = False

        while True:
            if item is _SENTINEL:
                stopping = True
            elif item[0] == 'speak':
                pending_text = item[1]
            elif item[0] == 'set' and engine is not None:
                try:
                    engine.setProperty(item[1], item[2])
                except Exception:
                    logging.exception("Error while configuring the speech engine")

            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                return pending_text, stopping

    def set_rate(self, rate=150):
        """Set the speech rate, applied before the next utterance."""
        self._rate = rate
        if self._thread.is_alive():
            self._queue.put(('set', 'rate', rate))

    def set_volume(self, volume=0.8):
        """Set the speech volume, applied before the next utterance."""
        self._volume = volume
        if self._thread.is_alive():
            self._queue.put(('set', 'volume', volume))

    def speak(self, text=""):
        """Queue the given text without blocking, superseding pending texts.

        Blank text is dropped here: pyttsx3 silently discards it instead of
        speaking it, so it would never produce a finished-utterance callback.
        """
        if not str(text or "").strip() or not self._thread.is_alive():
            return

        self._queue.put(('speak', text))

    def stop(self):
        """Stop the speech synthesis and shut the worker down without blocking.

        Returns:
            bool: True when the worker thread did not exit within the join
                  timeout, False when it is gone. Safe to call repeatedly.
        """
        if not self._thread.is_alive():
            self._stopped = True
            return False

        if self._stopped:
            return True

        self._stopped = True
        self._stop_requested.set()
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        engine = self.engine
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                logging.exception("Error while stopping the speech engine")

        self._queue.put(_SENTINEL)
        self._thread.join(timeout=_JOIN_TIMEOUT)
        timed_out = self._thread.is_alive()
        if timed_out:
            logging.warning(
                "Speech worker did not exit within %.1fs", _JOIN_TIMEOUT)
        return timed_out
