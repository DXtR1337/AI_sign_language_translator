import hashlib
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def read_checksum_file(path):
    return {
        relative_path: checksum
        for checksum, relative_path in (
            line.split(maxsplit=1)
            for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip()
        )
    }


@pytest.mark.parametrize(
    ('checksum_file', 'relative_paths'),
    [
        (
            REPOSITORY_ROOT / 'models' / 'SHA256SUMS.txt',
            [
                'gesture_recognizer_asl_0.task',
                'gesture_recognizer_asl_1.task',
                'gesture_recognizer_asl_mp.task',
            ],
        ),
        (
            REPOSITORY_ROOT / 'third_party' / 'protobuf' / 'SHA256SUMS.txt',
            [
                '../wheels/protobuf-4.25.9+aislt.cve20260994.1-cp310-abi3-win_amd64.whl',
                '../wheels/protobuf-4.25.9+aislt.cve20260994.1-py3-none-any.whl',
            ],
        ),
    ],
)
def test_bundled_artifacts_match_recorded_checksums(checksum_file, relative_paths):
    checksums = read_checksum_file(checksum_file)

    for relative_path in relative_paths:
        artifact_path = checksum_file.parent / relative_path
        digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        assert digest == checksums[relative_path]
