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
- **Podzial na fragmenty** po granicach zdan (heurystyka dla polskiego),
  z poszanowaniem akapitow.
- **Backendy TTS** (wymienne):
  - `piper` — **lokalny, darmowy, offline**, gotowe polskie glosy (domyslny),
  - `elevenlabs` — **chmura**, najlepsza jakosc i klonowanie glosu (wymaga klucza API).
- **Skladanie audiobooka** per rozdzial i (opcjonalnie) w jeden plik;
  uzywa `ffmpeg`, a dla WAV ma czysto-pythonowy fallback (dziala bez ffmpeg).

## Instalacja

```bash
pip install -e .            # pakiet + zaleznosci ekstrakcji
pip install -e ".[elevenlabs]"   # dodatkowo backend chmurowy
```

Narzedzia zewnetrzne (wg potrzeb):

| Narzedzie | Do czego | Skad |
|-----------|----------|------|
| **Piper** | lokalny TTS | https://github.com/rhasspy/piper |
| polskie glosy Piper | barwa lektora | https://huggingface.co/rhasspy/piper-voices (katalog `pl/`) |
| **Calibre** (`ebook-convert`) | format MOBI/AZW3 | https://calibre-ebook.com |
| **ffmpeg** | laczenie / format M4B | https://ffmpeg.org |
| **Tesseract** + model `pol` | OCR skanow | `apt-get install tesseract-ocr tesseract-ocr-pol` |

OCR (Python): `pip install -e ".[ocr]"` (pytesseract + Pillow).

## Uzycie

```bash
# Lokalnie, Piper (zalecane, offline):
python -m pdf_audiobook ksiazka.pdf -o out/ \
    --backend piper --voice pl_PL-darkman-medium.onnx --merge

# Wolniej / dostojniej (charakter lektorski):
python -m pdf_audiobook ksiazka.pdf -o out/ \
    --backend piper --voice glos.onnx --length-scale 1.15

# Chmura, ElevenLabs (najlepsza jakosc; klucz w srodowisku):
export ELEVENLABS_API_KEY=...
python -m pdf_audiobook ksiazka.mobi -o out/ \
    --backend elevenlabs --voice <voice_id> --merge

# Skanowany PDF (OCR): auto OCR-uje tylko strony bez tekstu
python -m pdf_audiobook skan.pdf -o out/ --backend piper --voice glos.onnx \
    --ocr auto --ocr-lang pol

# Wymus OCR na wszystkich stronach (np. gdy warstwa tekstowa jest bledna):
python -m pdf_audiobook skan.pdf --dry-run --ocr force

# Podglad samego wyciagnietego tekstu (bez syntezy):
python -m pdf_audiobook ksiazka.epub --dry-run
```

Najwazniejsze flagi: `--backend`, `--voice`, `--length-scale`, `--max-chars`,
`--merge`, `--keep-chunks`, `--dry-run`. Pelna lista: `--help`.

## Uwaga prawna — glos konkretnego lektora

Glos rozpoznawalnej, zyjacej osoby (np. konkretnego lektora) jest **dobrem
osobistym** (art. 23 Kodeksu cywilnego), a regulaminy uslug do klonowania
(np. ElevenLabs) zwykle **wymagaja zgody** tej osoby. Dlatego domyslnie
narzedzie celuje w glos **o pozadanych cechach** (barwa, tempo, intonacja),
a nie w wierna kopie konkretnej osoby. Klonowanie z probek konkretnego lektora
rob wylacznie do wlasnego, prywatnego uzytku i tylko za zgoda — nie do
dystrybucji.

## Testy

```bash
pip install pytest
pytest -q
```

## Plany / mozliwe rozszerzenia

- Eksport **M4B z rozdzialami** i metadanymi (okladka, tytul, autor).
- Backend lokalnego **klonowania** (XTTS-v2 / F5-TTS) dla barwy z probki.
- Slownik wymowy/skrotow i lepsza normalizacja liczb i dat po polsku.
- Rownolegla synteza fragmentow i wznawianie przerwanej pracy.
