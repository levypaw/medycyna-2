"""Normalizacja tekstu pod polska synteze mowy.

Lektor (zwlaszcza lokalny) czesto przekreca skroty ("np.", "m.in."), cyfry
("1939") i liczby rzymskie ("XIX w."). Ten modul rozwija je do pelnych slow:

    skroty:    np. -> na przyklad, itd. -> i tak dalej, dr -> doktor, r. -> roku
    liczby:    1939 -> tysiac dziewiecset trzydziesci dziewiec
    rzymskie:  rozdzial III -> rozdzial trzeci, XIX wiek -> dziewietnasty wiek

Konwersja jest celowo zachowawcza (liczby rzymskie tylko w kontekscie), bo
niektore silniki maja wlasna normalizacje — calosc mozna wylaczyc (--no-normalize).
"""

from __future__ import annotations

import re

# --------------------------------------------------------------------------- #
# Slownik skrotow
# --------------------------------------------------------------------------- #
# Klucz dokladnie tak, jak w tekscie (z kropka, jesli wystepuje). Dopasowanie
# jest niewrazliwe na wielkosc liter, z poszanowaniem granic wyrazow.
ABBREVIATIONS: dict[str, str] = {
    "np.": "na przyklad",
    "itd.": "i tak dalej",
    "itp.": "i tym podobne",
    "tj.": "to jest",
    "tzn.": "to znaczy",
    "tzw.": "tak zwany",
    "m.in.": "miedzy innymi",
    "in.": "innymi",
    "ok.": "okolo",
    "cd.": "ciag dalszy",
    "jw.": "jak wyzej",
    "ww.": "wyzej wymieniony",
    "pt.": "pod tytulem",
    "ds.": "do spraw",
    "wg": "wedlug",
    "godz.": "godzina",
    "nr": "numer",
    "ul.": "ulica",
    "al.": "aleja",
    "pl.": "plac",
    "sw.": "swiety",
    "św.": "święty",
    "prof.": "profesor",
    "dr": "doktor",
    "mgr": "magister",
    "inż.": "inżynier",
    "gen.": "generał",
    "płk": "pułkownik",
    "art.": "artykuł",
    "ust.": "ustęp",
    "str.": "strona",
    "rys.": "rysunek",
    "tab.": "tabela",
    "r.": "roku",
    "w.": "wiek",
}


def _build_abbrev_regex(abbrev: dict[str, str]) -> re.Pattern[str]:
    """Buduje jeden wzorzec z kluczy skrotow, najdluzsze najpierw."""
    keys = sorted(abbrev, key=len, reverse=True)
    alts = "|".join(re.escape(k) for k in keys)
    # Granica: z lewej nie litera/cyfra; z prawej nie litera/cyfra
    # (kropka skrotu jest czescia klucza i zostaje skonsumowana).
    return re.compile(
        rf"(?<![\w])(?:{alts})(?![\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ])",
        re.IGNORECASE,
    )


_ABBREV_RE = _build_abbrev_regex(ABBREVIATIONS)
# Mapa wyszukiwania bez wzgledu na wielkosc liter.
_ABBREV_LOOKUP = {k.lower(): v for k, v in ABBREVIATIONS.items()}


def expand_abbreviations(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        return _ABBREV_LOOKUP[m.group(0).lower()]

    return _ABBREV_RE.sub(repl, text)


# --------------------------------------------------------------------------- #
# Liczby arabskie -> liczebniki glowne
# --------------------------------------------------------------------------- #
_UNITS = ["zero", "jeden", "dwa", "trzy", "cztery",
          "pięć", "sześć", "siedem", "osiem", "dziewięć"]
_TEENS = ["dziesięć", "jedenaście", "dwanaście", "trzynaście", "czternaście",
          "piętnaście", "szesnaście", "siedemnaście", "osiemnaście", "dziewiętnaście"]
_TENS = {2: "dwadzieścia", 3: "trzydzieści", 4: "czterdzieści", 5: "pięćdziesiąt",
         6: "sześćdziesiąt", 7: "siedemdziesiąt", 8: "osiemdziesiąt", 9: "dziewięćdziesiąt"}
_HUNDREDS = {1: "sto", 2: "dwieście", 3: "trzysta", 4: "czterysta", 5: "pięćset",
             6: "sześćset", 7: "siedemset", 8: "osiemset", 9: "dziewięćset"}
# Formy: (pojedyncza, 2-4, 5+)
_SCALES = [
    None,
    ("tysiąc", "tysiące", "tysięcy"),
    ("milion", "miliony", "milionów"),
    ("miliard", "miliardy", "miliardów"),
    ("bilion", "biliony", "bilionów"),
]


def _plural_index(n: int) -> int:
    """0 dla 1, 1 dla 2-4 (poza 12-14), 2 w pozostalych przypadkach."""
    if n == 1:
        return 0
    last, last_two = n % 10, n % 100
    if 2 <= last <= 4 and not 12 <= last_two <= 14:
        return 1
    return 2


def _three_digits_to_words(n: int) -> list[str]:
    """Konwersja grupy 1..999 na liste slow."""
    parts: list[str] = []
    h, rem = divmod(n, 100)
    if h:
        parts.append(_HUNDREDS[h])
    if rem:
        if rem < 10:
            parts.append(_UNITS[rem])
        elif rem < 20:
            parts.append(_TEENS[rem - 10])
        else:
            t, u = divmod(rem, 10)
            parts.append(_TENS[t])
            if u:
                parts.append(_UNITS[u])
    return parts


def int_to_cardinal(n: int) -> str:
    """Liczba calkowita >= 0 jako polski liczebnik glowny (mianownik)."""
    if n == 0:
        return "zero"

    groups: list[int] = []
    while n > 0:
        n, g = divmod(n, 1000)
        groups.append(g)

    words: list[str] = []
    for level in range(len(groups) - 1, -1, -1):
        g = groups[level]
        if g == 0:
            continue
        if level == 0:
            words.extend(_three_digits_to_words(g))
        else:
            scale = _SCALES[level] if level < len(_SCALES) else None
            if scale is None:
                # Poza obslugiwana skala — oddaj cyframi (bardzo rzadkie).
                words.extend(_three_digits_to_words(g))
                continue
            if g == 1:
                # "tysiąc", nie "jeden tysiąc".
                words.append(scale[0])
            else:
                words.extend(_three_digits_to_words(g))
                words.append(scale[_plural_index(g)])
    return " ".join(words)


_NUMBER_RE = re.compile(r"\d+")


def expand_numbers(text: str) -> str:
    return _NUMBER_RE.sub(lambda m: int_to_cardinal(int(m.group(0))), text)


# --------------------------------------------------------------------------- #
# Liczby rzymskie -> liczebniki porzadkowe (tylko w kontekscie)
# --------------------------------------------------------------------------- #
_ORD_UNITS = {1: "pierwszy", 2: "drugi", 3: "trzeci", 4: "czwarty", 5: "piąty",
              6: "szósty", 7: "siódmy", 8: "ósmy", 9: "dziewiąty"}
_ORD_TEENS = {10: "dziesiąty", 11: "jedenasty", 12: "dwunasty", 13: "trzynasty",
              14: "czternasty", 15: "piętnasty", 16: "szesnasty", 17: "siedemnasty",
              18: "osiemnasty", 19: "dziewiętnasty"}
_ORD_TENS = {20: "dwudziesty", 30: "trzydziesty", 40: "czterdziesty",
             50: "pięćdziesiąty", 60: "sześćdziesiąty", 70: "siedemdziesiąty",
             80: "osiemdziesiąty", 90: "dziewięćdziesiąty"}

_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def roman_to_int(s: str) -> int | None:
    """Zamienia poprawna liczbe rzymska na int; None gdy niepoprawna."""
    total, prev = 0, 0
    for ch in reversed(s.upper()):
        val = _ROMAN_VALUES.get(ch)
        if val is None:
            return None
        if val < prev:
            total -= val
        else:
            total += val
            prev = val
    # Walidacja roundtrip odrzuca np. "IIII", "VX".
    return total if total > 0 and int_to_roman(total) == s.upper() else None


def int_to_roman(n: int) -> str:
    table = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
             (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
             (5, "V"), (4, "IV"), (1, "I")]
    out = []
    for val, sym in table:
        while n >= val:
            out.append(sym)
            n -= val
    return "".join(out)


def ordinal_pl(n: int) -> str:
    """Liczebnik porzadkowy (mianownik, rodzaj meski) dla 1..99."""
    if n in _ORD_UNITS:
        return _ORD_UNITS[n]
    if 10 <= n <= 19:
        return _ORD_TEENS[n]
    if n in _ORD_TENS:
        return _ORD_TENS[n]
    if 20 <= n <= 99:
        t, u = (n // 10) * 10, n % 10
        return _ORD_TENS[t] + (" " + _ORD_UNITS[u] if u else "")
    return int_to_cardinal(n)  # poza zakresem — bezpieczny fallback


_CTX_BEFORE = r"rozdział|rozdziale|tom|tomie|część|części|księga|księdze|akt|akcie|punkt|punkcie"
_CTX_AFTER = r"wiek|wieku|wieków|stulecie|stuleciu"
_ROMAN_TOKEN = r"[IVXLCDM]{1,5}"

_ROMAN_BEFORE_RE = re.compile(
    rf"(?P<pre>\b(?:{_CTX_BEFORE})\s+)(?P<rom>{_ROMAN_TOKEN})\b", re.IGNORECASE
)
_ROMAN_AFTER_RE = re.compile(
    rf"\b(?P<rom>{_ROMAN_TOKEN})(?P<post>\s+(?:{_CTX_AFTER})\b)", re.IGNORECASE
)


def expand_roman(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        value = roman_to_int(m.group("rom"))
        if value is None:
            return m.group(0)
        ordinal = ordinal_pl(value)
        pre = m.groupdict().get("pre") or ""
        post = m.groupdict().get("post") or ""
        return f"{pre}{ordinal}{post}"

    text = _ROMAN_BEFORE_RE.sub(repl, text)
    text = _ROMAN_AFTER_RE.sub(repl, text)
    return text


# --------------------------------------------------------------------------- #
# Calosc
# --------------------------------------------------------------------------- #
def normalize_text(text: str) -> str:
    """Pelna normalizacja: skroty -> liczby rzymskie -> liczby arabskie."""
    text = expand_abbreviations(text)
    text = expand_roman(text)   # przed cyframi, by nie psuc kontekstu
    text = expand_numbers(text)
    return text
