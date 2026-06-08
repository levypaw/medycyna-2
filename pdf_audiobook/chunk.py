"""Podzial tekstu na fragmenty mieszczace sie w limicie silnika TTS.

Wiekszosc silnikow ma limit dlugosci wejscia, a zbyt dlugie wejscie psuje
prozodie. Tniemy po granicach zdan, nigdy w srodku zdania.
"""

from __future__ import annotations

import re

# Koniec zdania: ., !, ? (ew. z cudzyslowem/nawiasem), po ktorym spacja i wielka litera.
_SENTENCE_END = re.compile(r'(?<=[.!?…])["\')\]]?\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ0-9])')


def split_sentences(text: str) -> list[str]:
    """Dzieli akapit na zdania (heurystyka dostosowana do polskiego)."""
    sentences = _SENTENCE_END.split(text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_text(text: str, max_chars: int = 600) -> list[str]:
    """Laczy zdania w fragmenty o dlugosci <= max_chars.

    Najpierw szanuje granice akapitow, potem zdan. Bardzo dlugie zdanie
    (dluzsze niz max_chars) jest oddawane w calosci jako wlasny fragment.
    """
    chunks: list[str] = []
    buffer = ""

    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        for sentence in split_sentences(paragraph):
            if len(sentence) > max_chars:
                if buffer:
                    chunks.append(buffer)
                    buffer = ""
                chunks.append(sentence)
                continue

            candidate = f"{buffer} {sentence}".strip() if buffer else sentence
            if len(candidate) <= max_chars:
                buffer = candidate
            else:
                chunks.append(buffer)
                buffer = sentence

        # Granica akapitu — domknij biezacy fragment dla naturalnej pauzy.
        if buffer:
            chunks.append(buffer)
            buffer = ""

    if buffer:
        chunks.append(buffer)
    return chunks
