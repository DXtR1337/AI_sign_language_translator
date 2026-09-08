# Repository Guidelines

## Project scope

This repository contains a PySide6 desktop application for real-time ASL fingerspelling recognition. Runtime inference uses MediaPipe Gesture Recognizer task bundles from `models/`; model training remains in the Google Colab notebook under `notebooks/`.

## Development workflow

- Use Python 3.10 or 3.12 for local development and CI.
- Install development dependencies with `python -m pip install -r requirements-dev.txt`.
- Run the application from the repository root with `python src/main.py`.
- Run the regression suite with `python -m pytest` before committing.
- Keep MediaPipe below 0.10.30 unless the legacy landmark drawing code is migrated and all shipped models are retested.
- Preserve both locally patched protobuf wheels and their provenance. If either wheel or patch changes, rebuild with Python 3.10 using `scripts/build_patched_protobuf.ps1`, update recorded checksums and run `tests/test_protobuf_patch.py`.

## Code boundaries

- Treat `src/gui.ui` as the source of truth for the interface. Regenerate `src/gui.py` with `pyside6-uic`; do not edit the generated file by hand.
- Keep camera capture, recognition, TTS and main-window coordination in their existing modules. Prefer focused fixes over broad refactors.
- Do not replace or retrain the `.task` files without documenting their source, evaluation and checksums.
- Tests must not require a physical camera, audible speech or network access.

## Documentation and security

- Keep `README.md` and `README.pl.md`, as well as both technical documentation files, equivalent in scope and facts.
- Use only real application screenshots. Preserve their aspect ratio and verify every local link.
- Never commit `kaggle.json`, API tokens, credentials, downloaded datasets or personal administrative forms.
- Preserve the license split: source code uses `LICENSE`, while the thesis and original documentation use `LICENSE-docs`.
- Report vulnerabilities according to `SECURITY.md`.
- Write GitHub release titles and descriptions in English. Describe packaging, verification and checksums neutrally; do not mention credential leaks or rewritten Git history.
