"""Repack an extracted protobuf wheel with deterministic metadata."""

import argparse
import base64
import csv
import hashlib
import io
import os
from pathlib import Path
import shutil
import time
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


UPSTREAM_VERSION = "4.25.9"
LOCAL_VERSION = "4.25.9+aislt.cve20260994.1"


def record_hash(data):
    digest = hashlib.sha256(data).digest()
    encoded = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return f"sha256={encoded}"


def replace_once(text, old, new, description):
    if text.count(old) != 1:
        raise ValueError(f"Expected exactly one {description}")
    return text.replace(old, new)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_directory", type=Path)
    parser.add_argument("output_wheel", type=Path)
    args = parser.parse_args()

    source_directory = args.source_directory.resolve()
    upstream_dist_info = source_directory / f"protobuf-{UPSTREAM_VERSION}.dist-info"
    local_dist_info = source_directory / f"protobuf-{LOCAL_VERSION}.dist-info"
    if not upstream_dist_info.is_dir():
        raise FileNotFoundError(upstream_dist_info)
    if local_dist_info.exists():
        raise FileExistsError(local_dist_info)
    upstream_dist_info.rename(local_dist_info)

    metadata_path = local_dist_info / "METADATA"
    metadata = metadata_path.read_text(encoding="utf-8")
    metadata = replace_once(
        metadata,
        f"Version: {UPSTREAM_VERSION}",
        f"Version: {LOCAL_VERSION}",
        "protobuf version in METADATA",
    )
    with metadata_path.open("w", encoding="utf-8", newline="\n") as metadata_file:
        metadata_file.write(metadata)

    record_path = local_dist_info / "RECORD"
    rows = []
    for path in sorted(source_directory.rglob("*")):
        if not path.is_file() or path == record_path:
            continue
        relative_path = path.relative_to(source_directory).as_posix()
        data = path.read_bytes()
        rows.append((relative_path, record_hash(data), str(len(data))))

    relative_record_path = record_path.relative_to(source_directory).as_posix()
    rows.append((relative_record_path, "", ""))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerows(rows)
    with record_path.open("w", encoding="utf-8", newline="\n") as record_file:
        record_file.write(stream.getvalue())

    source_date_epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "1735689600"))
    timestamp = time.gmtime(source_date_epoch)[:6]
    args.output_wheel.parent.mkdir(parents=True, exist_ok=True)
    temporary_wheel = args.output_wheel.with_suffix(".tmp")

    try:
        with ZipFile(
            temporary_wheel,
            "w",
            compression=ZIP_DEFLATED,
            compresslevel=9,
        ) as wheel:
            for path in sorted(source_directory.rglob("*")):
                if not path.is_file():
                    continue
                relative_path = path.relative_to(source_directory).as_posix()
                info = ZipInfo(relative_path, date_time=timestamp)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                wheel.writestr(info, path.read_bytes(), compresslevel=9)
        shutil.move(temporary_wheel, args.output_wheel)
    finally:
        temporary_wheel.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
