"""pdf_audiobook — zamiana ksiazek (PDF/MOBI/EPUB) na audiobooka glosem lektora.

Potok przetwarzania:
    plik  ->  ekstrakcja tekstu  ->  czyszczenie  ->  podzial na fragmenty
          ->  synteza mowy (TTS)  ->  zlozenie audiobooka

Modul jest celowo modularny: backend TTS jest wymienny (Piper lokalnie,
ElevenLabs w chmurze itd.), wiec mozna podmienic silnik bez ruszania reszty.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
