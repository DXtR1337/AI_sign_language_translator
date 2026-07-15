import google.protobuf
import pytest
from google.protobuf import any_pb2, json_format


PATCHED_PROTOBUF_VERSION = "4.25.9+aislt.cve20260994.1"


def nested_any(depth):
    value = {}
    for _ in range(depth):
        value = {
            "@type": "type.googleapis.com/google.protobuf.Any",
            "value": value,
        }
    return value


def test_nested_any_respects_recursion_limit():
    assert google.protobuf.__version__ == PATCHED_PROTOBUF_VERSION

    json_format.ParseDict(
        nested_any(4),
        any_pb2.Any(),
        max_recursion_depth=5,
    )

    with pytest.raises(
        json_format.ParseError,
        match="Message too deep. Max recursion depth is 5",
    ):
        json_format.ParseDict(
            nested_any(5),
            any_pb2.Any(),
            max_recursion_depth=5,
        )
