"""Podzial tekstu na fragmenty mieszczace sie w limicie silnika TTS.

Wiekszosc silnikow ma limit dlugosci wejscia, a zbyt dlugie wejscie psuje
prozodie. Tniemy po granicach zdan, nigdy w srodku zdania.
"""

from __future__ import annotations

import re

# Koniec zdania: ., !, ? (ew. z cudzyslowem/nawiasem), po ktorym spacja i wielka litera.
_SENTENCE_END = re.compile(r'(?<=[.!?…])["\')\]]?\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ0-9])')
# Granice fraz wewnatrz zdania (po przecinku/sredniku/myslniku) do dzielenia
# bardzo dlugich zdan, ktore przekraczalyby limit silnika.
_CLAUSE_BREAK = re.compile(r'(?<=[,;:])\s+|\s+[–—-]\s+')


def split_sentences(text: str) -> list[str]:
    """Dzieli akapit na zdania (heurystyka dostosowana do polskiego)."""
    sentences = _SENTENCE_END.split(text)
    return [s.strip() for s in sentences if s.strip()]


def _hard_split(text: str, max_chars: int) -> list[str]:
    """Ostatecznosc: dzieli po slowach, gdy nawet fraza jest za dluga."""
    out: list[str] = []
    buf = ""
    for word in text.split():
        cand = f"{buf} {word}".strip() if buf else word
        if len(cand) <= max_chars:
            buf = cand
        else:
            if buf:
                out.append(buf)
            buf = word
    if buf:
        out.append(buf)
    return out


def _split_long_sentence(sentence: str, max_chars: int) -> list[str]:
    """Dzieli zbyt dlugie zdanie na frazy (po przecinkach), <= max_chars."""
    out: list[str] = []
    buf = ""
    for clause in _CLAUSE_BREAK.split(sentence):
        if not clause:
            continue
        cand = f"{buf} {clause}".strip() if buf else clause
        if len(cand) <= max_chars:
            buf = cand
        else:
            if buf:
                out.append(buf)
                buf = ""
            if len(clause) <= max_chars:
                buf = clause
            else:
                out.extend(_hard_split(clause, max_chars))
    if buf:
        out.append(buf)
    return out


def chunk_text(text: str, max_chars: int = 600) -> list[str]:
    """Laczy zdania w fragmenty o dlugosci <= max_chars.

    Szanuje granice akapitow i zdan. Zdanie dluzsze niz max_chars jest dzielone
    na frazy (po przecinkach), a w ostatecznosci po slowach — zaden fragment nie
    przekracza max_chars (wazne dla silnikow z twardym limitem, np. XTTS=224).
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
                chunks.extend(_split_long_sentence(sentence, max_chars))
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
