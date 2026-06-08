#!/usr/bin/env bash
#
# setup_mac.sh — instalacja pdf_audiobook na macOS (Apple Silicon: M1/M2/M3/M4).
#
# Co robi:
#   1. sprawdza/instaluje Homebrew, Pythona 3.11 i ffmpeg,
#   2. tworzy srodowisko .venv,
#   3. instaluje pakiet z backendem klonowania barwy (XTTS) i OCR,
#   4. wypisuje gotowe komendy nastepnego kroku.
#
# Uzycie:   bash setup_mac.sh
#
set -euo pipefail

info()  { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m[!]\033[0m %s\n" "$*"; }

# --- 0. Architektura --------------------------------------------------------
ARCH="$(uname -m)"
if [[ "$ARCH" != "arm64" ]]; then
  warn "Wykryto $ARCH (nie Apple Silicon). Skrypt jest pod M1/M2/M3/M4; "
  warn "na Intelu PyTorch pojdzie tylko na CPU."
fi

# --- 1. Homebrew ------------------------------------------------------------
if ! command -v brew >/dev/null 2>&1; then
  info "Instaluje Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Dodaj brew do PATH w biezacej sesji (Apple Silicon: /opt/homebrew).
  eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || true)"
else
  info "Homebrew juz jest."
fi

# --- 2. Python 3.11 + ffmpeg ------------------------------------------------
info "Instaluje python@3.11 i ffmpeg (jesli brak)..."
brew install python@3.11 ffmpeg

PY="$(brew --prefix)/bin/python3.11"
if [[ ! -x "$PY" ]]; then
  PY="python3.11"
fi
info "Python: $("$PY" --version)"

# --- 3. Srodowisko wirtualne + pakiet --------------------------------------
info "Tworze .venv i instaluje pakiet (XTTS + OCR)..."
"$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[xtts,ocr]"

# Tesseract z polskim modelem do OCR skanow (opcjonalnie, ale przydatne).
info "Instaluje Tesseract OCR + jezyk polski..."
brew install tesseract tesseract-lang || warn "Pomijam Tesseract (mozesz doinstalowac pozniej)."

cat <<'NEXT'

============================================================
 Gotowe! Aktywuj srodowisko w nowej sesji:   source .venv/bin/activate

 1) Przygotuj probke glosu (6-20 s czystej mowy):
      ffmpeg -i nagranie.mp3 -ss 00:00:30 -t 12 -ar 22050 -ac 1 probka.wav

 2) Szybki podglad tekstu z ksiazki (bez syntezy):
      python -m pdf_audiobook KSIAZKA.pdf --dry-run | head -40

 3) Maly test klonowania barwy (akceleracja GPU Apple = --device mps):
      export COQUI_TOS_AGREED=1
      python -m pdf_audiobook KSIAZKA.pdf -o test/ \
          --backend xtts --voice probka.wav --language pl --device mps

 4) Cala ksiazka -> audiobook M4B z rozdzialami:
      python -m pdf_audiobook KSIAZKA.pdf -o out/ \
          --backend xtts --voice probka.wav --language pl --device mps \
          --m4b --title "Tytul" --author "Autor"

 Uwaga: pierwsze uruchomienie XTTS pobiera model (~1.8 GB).
        Jesli --device mps zglosi blad, uzyj --device cpu (wolniej, ale pewnie).
        Klonowanie barwy realnej osoby - tylko za zgoda / do uzytku prywatnego.
============================================================
NEXT
