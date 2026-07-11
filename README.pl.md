# AI Sign Language Translator

> System rozpoznawania i tłumaczenia alfabetu palcowego amerykańskiego języka migowego (ASL) w czasie rzeczywistym z wykorzystaniem sztucznej inteligencji.

🇬🇧 **English version:** [README.md](README.md)
📚 **Dokumentacja techniczna:** [docs/TECHNICAL_DOCUMENTATION.pl.md](docs/TECHNICAL_DOCUMENTATION.pl.md) · [English version](docs/TECHNICAL_DOCUMENTATION.md)

![License: MIT](https://img.shields.io/badge/Licencja-MIT-green.svg)
![Python](https://img.shields.io/badge/Python-3.9%E2%80%933.12-blue.svg)
![MediaPipe](https://img.shields.io/badge/MediaPipe-%E2%89%A50.10.14-orange.svg)
![PySide6](https://img.shields.io/badge/PySide6-%E2%89%A56.7.3-41cd52.svg)
![Platform](https://img.shields.io/badge/Platforma-Windows%20%7C%20Linux-lightgrey.svg)

---

## O projekcie

**AI Sign Language Translator** to aplikacja desktopowa, która przechwytuje obraz z kamery internetowej, wykrywa dłoń w kadrze, klasyfikuje pokazywany statyczny znak alfabetu palcowego ASL i tłumaczy go na **tekst** oraz **mowę syntezowaną** — wszystko w czasie rzeczywistym.

System powstał jako część pracy inżynierskiej
*„System rozpoznawania oraz tłumaczenia alfabetu migowego z wykorzystaniem sztucznej inteligencji"*.

Potok rozpoznawania oparty jest na **MediaPipe Gesture Recognizer** z **własnym, wytrenowanym modelem klasyfikacyjnym**, a interfejs graficzny wykorzystuje **Qt for Python (PySide6)** z ciemnym motywem.

![Interfejs aplikacji](docs/images/ui.PNG)

## Najważniejsze funkcje

- 🖐️ **Detekcja i śledzenie dłoni w czasie rzeczywistym** — MediaPipe hand landmarker pracujący w asynchronicznym trybie `LIVE_STREAM`.
- 🔤 **Rozpoznawanie alfabetu palcowego ASL** — własny klasyfikator rozpoznający 24 statyczne litery alfabetu ASL (A–Y, z pominięciem dynamicznych J i Z) oraz klasę `none`.
- 🗣️ **Synteza mowy** — rozpoznane litery mogą być wypowiadane przez systemowy silnik TTS (`pyttsx3`), z regulowanym tempem i głośnością.
- 📊 **Wygładzanie wyników** — opcjonalne głosowanie w oknie przesuwnym po ostatnich *N* wynikach stabilizuje rozpoznany znak i raportuje jego średni poziom pewności.
- 🎥 **Elastyczna konfiguracja kamery** — wybór urządzenia, backendu przechwytywania (DirectShow, Media Foundation, V4L2, GStreamer, …), rozdzielczości oraz dostęp do natywnych ustawień sterownika.
- ⚙️ **Regulowane parametry rozpoznawania** — progi pewności detekcji / obecności / śledzenia dłoni oraz próg klasyfikacji ustawiane z poziomu GUI.
- 🧩 **Wymienne modele** — dowolny pakiet MediaPipe `.task` można wczytać w trakcie działania aplikacji; w repozytorium dostępne są trzy wytrenowane modele.
- 🌒 **Nowoczesny ciemny interfejs** — PySide6 + QDarkStyle, ze wskaźnikami FPS, ręczności (lewa/prawa) i pewności rozpoznania na żywo.

## Jak to działa

```mermaid
flowchart LR
    A[Kamera] -->|OpenCV VideoCapture| B[CameraApp<br/>klatka + znacznik czasu]
    B --> C[GestureRecognizerApp<br/>MediaPipe LIVE_STREAM]
    C -->|punkty charakterystyczne dłoni| D[Rysowanie szkieletu dłoni<br/>style niestandardowe]
    C -->|kategoria gestu + wynik| E[MainApp<br/>głosowanie w oknie przesuwnym]
    D --> F[GUI Qt<br/>podgląd wideo]
    E --> F
    E -->|rozpoznana litera| G[SpeakerApp<br/>pyttsx3 TTS]
```

1. **Przechwytywanie** — `CameraApp` pobiera klatki BGR z wybranej kamery i konwertuje je do RGB wraz ze znacznikiem czasu w nanosekundach.
2. **Rozpoznawanie** — `GestureRecognizerApp` przekazuje każdą klatkę asynchronicznie do MediaPipe Gesture Recognizer; wywołanie zwrotne z wynikiem inicjuje pobranie kolejnej klatki, tworząc samopodtrzymującą się pętlę przetwarzania.
3. **Przetwarzanie końcowe** — `MainApp` opcjonalnie agreguje ostatnie *N* klasyfikacji, wybierając najczęstszy znak i jego średni wynik.
4. **Wyjście** — klatka z naniesionym szkieletem dłoni, rozpoznana litera, pewność i FPS są wyświetlane w GUI; litera może być dodatkowo syntezowana do mowy.

Szczegółowy opis architektury, modelu wątkowości i potoku treningowego znajduje się w [dokumentacji technicznej](docs/TECHNICAL_DOCUMENTATION.pl.md).

## Struktura projektu

```
AI_sign_language_translator/
├── src/                        # Kod źródłowy aplikacji
│   ├── main.py                 # Punkt wejścia
│   ├── main_app.py             # Logika okna głównego (kontroler)
│   ├── recognizer.py           # Silnik rozpoznawania gestów (MediaPipe)
│   ├── camera.py               # Obsługa kamery (OpenCV)
│   ├── speaker.py              # Silnik syntezy mowy (pyttsx3)
│   ├── custom_landmarks.py     # Niestandardowe style rysowania szkieletu dłoni
│   ├── gui.py                  # Klasa UI skompilowana z gui.ui (pyside6-uic)
│   ├── gui.ui                  # Definicja interfejsu (Qt Designer)
│   ├── assets/                 # Ikony i loga
│   ├── requirements.txt        # Zależności Pythona
│   └── setup.sh                # Skrypt instalacji zależności
├── models/                     # Wytrenowane modele MediaPipe (.task)
│   ├── gesture_recognizer_asl_0.task     # Model domyślny
│   ├── gesture_recognizer_asl_1.task
│   └── gesture_recognizer_asl_mp.task
├── notebooks/                  # Trening modelu (Google Colab)
│   ├── Custom_gesture_recognizer.ipynb
│   └── custom_gesture_recognizer.py
├── docs/                       # Dokumentacja, pliki pracy dyplomowej, zrzuty ekranu
├── run_venv.bat                # Uruchamianie na Windows (cmd)
├── run_venv.ps1                # Uruchamianie na Windows (PowerShell)
├── LICENSE                     # Licencja MIT
└── README.md
```

## Wymagania

| Składnik | Wymaganie |
|---|---|
| Python | 3.9 – 3.12 (64-bit), zgodnie ze wsparciem MediaPipe |
| System | Windows 10/11 (platforma docelowa) lub Linux |
| Sprzęt | Kamera internetowa; wystarczy współczesny procesor wielordzeniowy (GPU nie jest wymagane) |
| Kluczowe pakiety | `mediapipe ≥ 0.10.14`, `PySide6 ≥ 6.7.3`, `qdarkstyle ≥ 3.2.3`, `pyttsx3 ≥ 2.98` |

> OpenCV i NumPy są instalowane automatycznie jako zależności MediaPipe.

## Instalacja

```bash
# 1. Sklonuj repozytorium
git clone https://github.com/Kamilr616/AI_sign_language_translator.git
cd AI_sign_language_translator

# 2. Utwórz i aktywuj środowisko wirtualne
python -m venv venv
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (cmd):
venv\Scripts\activate.bat
# Linux / macOS:
source venv/bin/activate

# 3. Zainstaluj zależności
python -m pip install --upgrade pip
python -m pip install -r src/requirements.txt
```

## Uruchamianie

Aplikację należy uruchamiać z katalogu `src/` (ścieżka domyślnego modelu jest rozwiązywana względem niego):

```bash
cd src
python main.py
```

W systemie Windows, przy środowisku wirtualnym utworzonym w katalogu `venv/` jak powyżej, można skorzystać z gotowych skryptów w katalogu głównym repozytorium:

```powershell
.\run_venv.ps1     # PowerShell
```

```bat
run_venv.bat       :: cmd
```

## Obsługa

1. Ustaw dłoń przed kamerą tak, aby była w całości widoczna na podglądzie.
2. Pokaż statyczny znak alfabetu ASL — rozpoznana litera, jej pewność oraz wykryta ręczność (lewa/prawa) wyświetlane są na bieżąco.
3. **Speak** — włącz, aby każda rozpoznana litera była wypowiadana na głos.
4. **Average sign** — włącz wygładzanie po ostatnich *N* wynikach (rozmiar okna ustawiany suwakiem), aby uzyskać stabilniejszy wynik.
5. Dostosuj progi rozpoznawania, rozdzielczość kamery, backend przechwytywania lub tempo/głośność mowy w panelach ustawień, a następnie zatwierdź odpowiednim przyciskiem **Reset**.
6. **Model** — w dowolnym momencie wczytaj inny model `.task` z katalogu `models/`.

Tablica znaków alfabetu ASL dostępna jest w [`docs/images`](docs/images/asl-sign-language-alphabet-vectors.webp).

## Trening modelu

Model klasyfikacyjny został wytrenowany przy użyciu **MediaPipe Model Maker** w środowisku Google Colab — kompletny, odtwarzalny potok znajduje się w [`notebooks/Custom_gesture_recognizer.ipynb`](notebooks/Custom_gesture_recognizer.ipynb):

- **Zbiór danych:** [ASL Alphabet (Kaggle, grassknoted/asl-alphabet)](https://www.kaggle.com/datasets/grassknoted/asl-alphabet) — ok. 87 000 obrazów o rozdzielczości 200×200 px.
- **Przygotowanie danych:** usunięcie dynamicznych liter *J* i *Z* oraz klas *del*/*space*; zmiana nazwy klasy *nothing* na `none` (wymóg Model Makera).
- **Architektura:** ekstraktor punktów charakterystycznych dłoni MediaPipe + własna, w pełni połączona głowica klasyfikacyjna (`128 → 64 → 32`).
- **Hiperparametry:** 70 epok, batch 16, learning rate 0.001 ze współczynnikiem zaniku 0.95, dropout 0.075, focal loss γ = 2.
- **Eksport:** pakiet TensorFlow Lite (`.task`) wykorzystywany bezpośrednio przez aplikację.

Szczegóły, w tym podział zbioru danych i procedura ewaluacji, opisane są w [dokumentacji technicznej](docs/TECHNICAL_DOCUMENTATION.pl.md#5-potok-treningu-modelu).

## Dokumentacja

| Dokument | Opis |
|---|---|
| [Dokumentacja techniczna (PL)](docs/TECHNICAL_DOCUMENTATION.pl.md) | Architektura, moduły, przepływ danych, potok treningowy |
| [Technical documentation (EN)](docs/TECHNICAL_DOCUMENTATION.md) | Wersja angielska dokumentacji technicznej |
| [Praca inżynierska (PL)](docs/System%20rozpoznawania%20oraz%20t%C5%82umaczenia%20alfabetu%20migowego%20z%20wykorzystaniem%20sztucznej%20inteligencji.pdf) | Pełny tekst pracy dyplomowej |

## Licencja

Projekt udostępniany jest na licencji **MIT** — zob. [LICENSE](LICENSE).

## Autor

**Kamil Rataj** — projekt zrealizowany w ramach pracy inżynierskiej.
