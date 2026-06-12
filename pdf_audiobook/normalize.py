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
    "np.": "na przykład",
    "itd.": "i tak dalej",
    "itp.": "i tym podobne",
    "tj.": "to jest",
    "tzn.": "to znaczy",
    "tzw.": "tak zwany",
    "m.in.": "między innymi",
    "in.": "innymi",
    "ok.": "około",
    "cd.": "ciąg dalszy",
    "jw.": "jak wyżej",
    "ww.": "wyżej wymieniony",
    "pt.": "pod tytułem",
    "ds.": "do spraw",
    "wg": "według",
    "godz.": "godzina",
    "nr": "numer",
    "ul.": "ulica",
    "al.": "aleja",
    "pl.": "plac",
    "sw.": "święty",
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
    "r.": "roku",   # zwykle po roku obsluzone w expand_years; tu fallback
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


def _number_repl(m: re.Match[str]) -> str:
    s = m.group(0)
    # Bardzo dlugie ciagi cyfr to zwykle ISBN/kody/identyfikatory — czytanie ich
    # jako gigantycznej liczby ("78 bilionow...") jest blednem; czytamy cyframi.
    if len(s) >= 10:
        return " ".join(_UNITS[int(d)] for d in s)
    return int_to_cardinal(int(s))


def expand_numbers(text: str) -> str:
    return _NUMBER_RE.sub(_number_repl, text)


# --------------------------------------------------------------------------- #
# Liczebniki w przypadku zaleznym (dopelniacz = miejscownik) po przyimkach.
# np. "po 142 stopniach" -> "po stu czterdziestu dwoch stopniach".
# --------------------------------------------------------------------------- #
# 1 w zlozeniach pozostaje nieodmienione ("dwudziestu jeden"); standalone -> jeden.
_OBL_UNITS = {2: "dwóch", 3: "trzech", 4: "czterech", 5: "pięciu", 6: "sześciu",
              7: "siedmiu", 8: "ośmiu", 9: "dziewięciu"}
_OBL_TEENS = {10: "dziesięciu", 11: "jedenastu", 12: "dwunastu", 13: "trzynastu",
              14: "czternastu", 15: "piętnastu", 16: "szesnastu", 17: "siedemnastu",
              18: "osiemnastu", 19: "dziewiętnastu"}
_OBL_TENS = {20: "dwudziestu", 30: "trzydziestu", 40: "czterdziestu",
             50: "pięćdziesięciu", 60: "sześćdziesięciu", 70: "siedemdziesięciu",
             80: "osiemdziesięciu", 90: "dziewięćdziesięciu"}
_OBL_HUNDREDS = {100: "stu", 200: "dwustu", 300: "trzystu", 400: "czterystu",
                 500: "pięciuset", 600: "sześciuset", 700: "siedmiuset",
                 800: "ośmiuset", 900: "dziewięciuset"}


def int_to_oblique(n: int) -> str:
    """Liczebnik glowny w dopelniaczu/miejscowniku dla 2..999.

    Dla 1 oraz liczb >999 nie ma pewnej, prostej formy — zwraca mianownik
    (bezpieczny fallback), bo lepiej zostawic zrozumiale niz wstawic blad.
    """
    if n < 2 or n > 999:
        return int_to_cardinal(n)
    parts: list[str] = []
    h = (n // 100) * 100
    rem = n % 100
    if h:
        parts.append(_OBL_HUNDREDS[h])
    if rem:
        if rem < 10:
            parts.append("jeden" if rem == 1 else _OBL_UNITS[rem])
        elif rem < 20:
            parts.append(_OBL_TEENS[rem])
        else:
            t, u = (rem // 10) * 10, rem % 10
            parts.append(_OBL_TENS[t])
            if u:
                parts.append("jeden" if u == 1 else _OBL_UNITS[u])
    return " ".join(parts)


# Przyimki, ktore jednoznacznie lacza sie z dopelniaczem/miejscownikiem
# (forma liczebnika w obu przypadkach jest taka sama).
_PREP_OBLIQUE = (
    r"po|od|do|bez|dla|u|około|koło|według|obok|wśród|podczas|przy|"
    r"sprzed|znad|spod|naprzeciw|wobec|wzdłuż"
)
_PREP_NUM_RE = re.compile(
    rf"\b(?P<prep>{_PREP_OBLIQUE})\s+(?P<num>\d+)\b", re.IGNORECASE
)


def expand_oblique_after_prep(text: str) -> str:
    """Odmienia liczbe po przyimku rzadzacym dopelniaczem/miejscownikiem."""
    def repl(m: re.Match[str]) -> str:
        return f"{m.group('prep')} {int_to_oblique(int(m.group('num')))}"

    return _PREP_NUM_RE.sub(repl, text)


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


# Liczebniki porzadkowe w dopelniaczu (np. "trzydziestego dziewiatego roku").
_ORD_GEN_UNITS = {1: "pierwszego", 2: "drugiego", 3: "trzeciego", 4: "czwartego",
                  5: "piątego", 6: "szóstego", 7: "siódmego", 8: "ósmego",
                  9: "dziewiątego"}
_ORD_GEN_TEENS = {10: "dziesiątego", 11: "jedenastego", 12: "dwunastego",
                  13: "trzynastego", 14: "czternastego", 15: "piętnastego",
                  16: "szesnastego", 17: "siedemnastego", 18: "osiemnastego",
                  19: "dziewiętnastego"}
_ORD_GEN_TENS = {20: "dwudziestego", 30: "trzydziestego", 40: "czterdziestego",
                 50: "pięćdziesiątego", 60: "sześćdziesiątego",
                 70: "siedemdziesiątego", 80: "osiemdziesiątego",
                 90: "dziewięćdziesiątego"}


def ordinal_genitive(n: int) -> str:
    """Liczebnik porzadkowy w dopelniaczu (rodzaj meski) dla 1..99."""
    if n in _ORD_GEN_UNITS:
        return _ORD_GEN_UNITS[n]
    if 10 <= n <= 19:
        return _ORD_GEN_TEENS[n]
    if n in _ORD_GEN_TENS:
        return _ORD_GEN_TENS[n]
    if 20 <= n <= 99:
        t, u = (n // 10) * 10, n % 10
        return _ORD_GEN_TENS[t] + (" " + _ORD_GEN_UNITS[u] if u else "")
    return int_to_cardinal(n)


def year_to_words(year: int) -> str:
    """Rok jako fraza dopelniacza, np. 1939 -> 'tysiac dziewiecset trzydziestego
    dziewiatego' (bez slowa 'roku' — dodaje je expand_years)."""
    rem = year % 100
    if rem == 0:
        # Okragle setki/tysiace — bezpieczny fallback (rzadkie w tekstach).
        return int_to_cardinal(year)
    prefix = int_to_cardinal(year - rem)  # np. "tysiąc dziewięćset", "dwa tysiące"
    return f"{prefix} {ordinal_genitive(rem)}"


# Rok poprzedzony liczba (3-4 cyfry) i zakonczony r./rok/roku -> dopelniacz + "roku".
_YEAR_RE = re.compile(
    r"\b(\d{3,4})\s+(?:roku|rok|r\.)(?![\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ])",
    re.IGNORECASE,
)


def expand_years(text: str) -> str:
    return _YEAR_RE.sub(lambda m: f"{year_to_words(int(m.group(1)))} roku", text)


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
    """Pelna normalizacja: lata -> skroty -> liczby rzymskie -> liczby (zalezne,
    a potem mianownik)."""
    text = expand_years(text)        # przed skrotami, by zlapac tez "1939 r."
    text = expand_abbreviations(text)  # m.in. "ok."->"około", "wg"->"według"
    text = expand_roman(text)        # przed cyframi, by nie psuc kontekstu
    text = expand_oblique_after_prep(text)  # "po 142 ..." -> "po stu czterdziestu dwóch ..."
    text = expand_numbers(text)      # pozostale liczby w mianowniku
    return text
