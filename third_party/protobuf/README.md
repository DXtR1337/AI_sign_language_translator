# Patched protobuf 4.25.9

MediaPipe 0.10.21 requires `protobuf>=4.25.3,<5`, while the upstream fix for
CVE-2026-0994 / PYSEC-2026-1805 is not available on the 4.25 release line.
This directory records the locally maintained compatibility build used by the
application.

## Provenance

- Source: the official PyPI `protobuf-4.25.9.tar.gz` sdist.
- Source SHA-256: `b0dc7e7c68de8b1ce831dacb12fb407e838edbb8b6cc0dc3a2a6b4cbf6de9cff`.
- Security fix: backport of protocolbuffers/protobuf PR 25239, commit
  `b210265f2b4c05e396e4590feb0c38ae6ae0cca4`.
- Local version: `4.25.9+aislt.cve20260994.1`.
- Official Windows wheel SHA-256: `3683c05154252206f7cb2d371626514b3708199d9bcf683b503dabf3a2e38e06`.
- Optimized Windows wheel SHA-256: `c3e1802c5b81b5164b895a4fa552551e6aece856ec7aa9e8b93c38ac1d8fa4b3`.
- Portable wheel SHA-256: `ee988f1e7649e5500b9ef14906bef0757b91f271572067819a75384c4f6b7c0c`.

`CVE-2026-0994.patch` contains only the upstream parser fix, while
`local-version.patch` identifies both local builds. The optimized Windows x64
wheel retains the official compiled UPB extension. `pure-python-wheel.patch`
omits that optional extension to provide a portable fallback for other
supported platforms and architectures.

## Rebuild and verification

From the repository root:

```powershell
.\scripts\build_patched_protobuf.ps1 -Python .\venv\Scripts\python.exe
python -m pip install --force-reinstall --no-deps -r .\src\requirements.txt
python -m pytest
```

The build script requires Python 3.10, verifies the upstream sdist and Windows wheel hashes, applies
the visible patches, uses pinned build tools and a fixed
`SOURCE_DATE_EPOCH`, then checks both resulting wheel hashes. The regression test in
`tests/test_protobuf_patch.py` verifies that excessive nested `Any` data is
rejected with `ParseError`.

The local-version wheel cannot be resolved on PyPI, so CI audits dependencies
in two stages. It first audits the application requirements, then separately
audits the upstream `protobuf==4.25.9` base version and ignores only
PYSEC-2026-1805. The regression test and wheel checksum are the compensating
controls for that backported advisory; other protobuf advisories still fail CI.

The bundled protobuf source and binary remain subject to the BSD 3-Clause
license in `LICENSE`.
