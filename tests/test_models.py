from pathlib import Path

from recognizer import GestureRecognizerApp


class ClosedCamera:
    def is_closed(self):
        return True


def test_shipped_models_can_be_loaded():
    model_paths = sorted((Path(__file__).resolve().parents[1] / "models").glob("*.task"))
    assert len(model_paths) == 3

    for model_path in model_paths:
        recognizer = GestureRecognizerApp(str(model_path), 1, 0.65, 0.65, 0.55, 0.6, ClosedCamera())
        recognizer.create_recognizer()
        recognizer.close()
