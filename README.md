# pdf_audiobook

Zamiana ksiazek (**PDF / MOBI / EPUB / TXT**) na **audiobooka** czytanego
glosem lektora — z mozliwoscia doboru glosu o pozadanych cechach (gleboki
baryton, spokojna, „lektorska" intonacja).

Potok jest modularny:

```
plik  ->  ekstrakcja tekstu  ->  czyszczenie  ->  podzial na fragmenty
      ->  synteza mowy (TTS)  ->  zlozenie audiobooka
```

## Co juz dziala

- **Ekstrakcja**: PDF (PyMuPDF, z wykrywaniem rozdzialow ze spisu tresci i
  usuwaniem powtarzajacych sie naglowkow/stopek), EPUB (ebooklib),
  MOBI/AZW3/FB2 (przez Calibre `ebook-convert`), TXT.
- **OCR dla skanow** (Tesseract): tryb `auto` rozpoznaje tekst tylko na stronach
  bez warstwy tekstowej, `force` — na wszystkich; domyslny jezyk `pol`.
- **Czyszczenie tekstu**: sklejanie wyrazow dzielonych na koncu wiersza,
  usuwanie numerow stron, scalanie zawijanych linii, normalizacja interpunkcji
  — zeby lektor frazowal naturalnie.
- **Normalizacja PL pod lektora**: rozwijanie skrotow (`np.`→na przyklad,
  `m.in.`→miedzy innymi, `dr`→doktor, `r.`→roku), liczby arabskie na slowa
  (`1939`→tysiac dziewiecset trzydziesci dziewiec) i liczby rzymskie w kontekscie
  (`rozdzial III`→trzeci, `XIX wiek`→dziewietnasty). Wylaczane `--no-normalize`.
- **Podzial na fragmenty** po granicach zdan (heurystyka dla polskiego),
  z poszanowaniem akapitow.
- **Backendy TTS** (wymienne):
  - `espeak` — **zero konfiguracji**, offline (espeak-ng); glos "robotyczny",
    idealny do szybkiego testu calego potoku,
  - `piper` — **lokalny, darmowy, offline**, gotowe polskie glosy (domyslny),
  - `xtts` — **lokalne klonowanie barwy** z probki glosu (XTTS-v2, zero-shot, PL),
  - `elevenlabs` — **chmura**, najlepsza jakosc i klonowanie glosu (wymaga klucza API).
- **Skladanie audiobooka** per rozdzial i (opcjonalnie) w jeden plik;
  uzywa `ffmpeg`, a dla WAV ma czysto-pythonowy fallback (dziala bez ffmpeg).
- **Eksport M4B** z **rozdzialami** (markery), **metadanymi** (tytul, autor)
  i **okladka** — gotowy format audiobooka dla wiekszosci odtwarzaczy.

## Instalacja

**macOS (Apple Silicon M1/M2/M3/M4)** — jedno polecenie instaluje wszystko
(Python 3.11, ffmpeg, Tesseract, pakiet z XTTS i OCR):

```bash
bash setup_mac.sh
```

Recznie / inne systemy:

```bash
pip install -e .            # pakiet + zaleznosci ekstrakcji
pip install -e ".[elevenlabs]"   # dodatkowo backend chmurowy
pip install -e ".[xtts]"         # klonowanie barwy (XTTS)
```

Na Apple Silicon mozna probowac akceleracji GPU: `--device mps`
(gdy zglosi blad — `--device cpu`).

Narzedzia zewnetrzne (wg potrzeb):

| Narzedzie | Do czego | Skad |
|-----------|----------|------|
| **Piper** | lokalny TTS | https://github.com/rhasspy/piper |
| polskie glosy Piper | barwa lektora | https://huggingface.co/rhasspy/piper-voices (katalog `pl/`) |
| **Calibre** (`ebook-convert`) | format MOBI/AZW3 | https://calibre-ebook.com |
| **ffmpeg** | laczenie / format M4B | https://ffmpeg.org |
| **Tesseract** + model `pol` | OCR skanow | `apt-get install tesseract-ocr tesseract-ocr-pol` |
| **coqui-tts** + PyTorch | klonowanie barwy (XTTS) | `pip install -e ".[xtts]"` (GPU zalecane) |

OCR (Python): `pip install -e ".[ocr]"` (pytesseract + Pillow).

## Uzycie

```bash
# Najszybszy test calego potoku (zero konfiguracji, glos syntetyczny):
#   apt-get install espeak-ng
python -m pdf_audiobook ksiazka.pdf -o out/ --backend espeak --merge

# Lokalnie, Piper (zalecane, offline):
python -m pdf_audiobook ksiazka.pdf -o out/ \
    --backend piper --voice pl_PL-darkman-medium.onnx --merge

# Wolniej / dostojniej (charakter lektorski):
python -m pdf_audiobook ksiazka.pdf -o out/ \
    --backend piper --voice glos.onnx --length-scale 1.15

# Lokalne klonowanie barwy z probki (XTTS-v2; --voice = nagranie referencyjne):
python -m pdf_audiobook ksiazka.pdf -o out/ \
    --backend xtts --voice probka_glosu.wav --language pl --merge
# Probka: kilka-kilkanascie sekund czystej mowy. Realnie wymaga GPU.

# Chmura, ElevenLabs (najlepsza jakosc; klucz w srodowisku):
export ELEVENLABS_API_KEY=...
python -m pdf_audiobook ksiazka.mobi -o out/ \
    --backend elevenlabs --voice <voice_id> --merge

# Eksport gotowego audiobooka M4B (rozdzialy + metadane + okladka):
python -m pdf_audiobook ksiazka.pdf -o out/ --backend piper --voice glos.onnx \
    --m4b --title "Tytul ksiazki" --author "Autor" --cover okladka.jpg

# Skanowany PDF (OCR): auto OCR-uje tylko strony bez tekstu
python -m pdf_audiobook skan.pdf -o out/ --backend piper --voice glos.onnx \
    --ocr auto --ocr-lang pol

# Wymus OCR na wszystkich stronach (np. gdy warstwa tekstowa jest bledna):
python -m pdf_audiobook skan.pdf --dry-run --ocr force

# Podglad samego wyciagnietego tekstu (bez syntezy):
python -m pdf_audiobook ksiazka.epub --dry-run
```

Najwazniejsze flagi: `--backend`, `--voice`, `--language`, `--speed`,
`--length-scale`, `--max-chars`, `--ocr`, `--merge`, `--keep-chunks`,
`--dry-run`. Pelna lista: `--help`.

### Rozwiazywanie problemow (XTTS)

`ImportError: cannot import name 'isin_mps_friendly'` — masz zbyt nowy
`transformers` wzgledem `coqui-tts`. Ustaw zgodna pare:

```bash
pip install "coqui-tts==0.25.1" "transformers==4.46.2"
```

`ModuleNotFoundError: No module named 'torchcodec'` / `TorchCodec is required` —
masz zbyt nowy `torchaudio` (>=2.9 wymaga osobnego `torchcodec`). Cofnij torcha
do sprawdzonego, spojnego zestawu:

```bash
pip install "torch==2.4.1" "torchaudio==2.4.1" soundfile
```

## Uwaga prawna — glos konkretnego lektora

Narzedzie *potrafi* klonowac barwe (backendy `xtts` i `elevenlabs`), ale glos
rozpoznawalnej, zyjacej osoby (np. konkretnego lektora) jest **dobrem
osobistym** (art. 23 Kodeksu cywilnego), a regulaminy uslug do klonowania
(np. ElevenLabs) zwykle **wymagaja zgody** tej osoby. Domyslnym, bezpiecznym
wyborem jest wiec glos **o pozadanych cechach** (barwa, tempo, intonacja),
a nie w wierna kopie konkretnej osoby. Klonowanie z probek konkretnego lektora
rob wylacznie do wlasnego, prywatnego uzytku i tylko za zgoda — nie do
dystrybucji.

## Testy

```bash
pip install pytest
pytest -q
```

## Plany / mozliwe rozszerzenia

- Pelna **deklinacja** liczebnikow i porzadkowych wg przypadka (teraz forma
  mianownikowa, np. "rozdziale trzeci" zamiast "trzecim") — zrozumiale dla
  lektora, ale gramatycznie uproszczone.
- Rownolegla synteza fragmentow i wznawianie przerwanej pracy.
