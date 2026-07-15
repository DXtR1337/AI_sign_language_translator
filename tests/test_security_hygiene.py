import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
KAGGLE_KEY_PATTERN = re.compile(r'key.{0,16}[a-f0-9]{32}', re.IGNORECASE)


def test_notebook_does_not_contain_embedded_kaggle_credentials():
    notebook = (
        REPOSITORY_ROOT / 'notebooks' / 'Custom_gesture_recognizer.ipynb'
    ).read_text(encoding='utf-8')

    assert KAGGLE_KEY_PATTERN.search(notebook) is None
