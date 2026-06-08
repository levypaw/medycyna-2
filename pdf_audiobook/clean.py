"""Czyszczenie i normalizacja tekstu pod synteze mowy.

Surowy tekst z PDF/EPUB ma lamane wiersze, dzielone wyrazy, numery stron itp.
Lektor brzmi naturalnie tylko wtedy, gdy poda mu sie plynne zdania i akapity.
"""

from __future__ import annotations

import re

# Wyraz podzielony na koncu wiersza: "infor-\nmacja" -> "informacja"
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
# Pojedyncze zlamanie wiersza wewnatrz akapitu (nie pusta linia) -> spacja
_SINGLE_NEWLINE = re.compile(r"(?<!\n)\n(?!\n)")
# Linia bedaca samym numerem strony
_PAGE_NUMBER_LINE = re.compile(r"^\s*\d{1,4}\s*$", re.MULTILINE)
# Wielokrotne spacje
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
# Trzy i wiecej znakow nowej linii -> podwojny (granica akapitu)
_MULTI_NEWLINE = re.compile(r"\n{3,}")


def clean_text(raw: str) -> str:
    """Zwraca tekst gotowy do podzialu na fragmenty i syntezy."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")

    # Sklej wyrazy przeniesione mysnikiem na koniec wiersza.
    text = _HYPHEN_BREAK.sub(r"\1\2", text)

    # Usun linie bedace samym numerem strony.
    text = _PAGE_NUMBER_LINE.sub("", text)

    # Pojedyncze zlamania wierszy to zwykle zawijanie tekstu, nie nowy akapit.
    text = _SINGLE_NEWLINE.sub(" ", text)

    # Normalizacja bialych znakow.
    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)

    # Usun spacje przed znakami interpunkcyjnymi.
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)

    return text.strip()
