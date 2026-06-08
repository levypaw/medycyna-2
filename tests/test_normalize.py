"""Testy normalizacji tekstu PL: skroty, liczby, liczby rzymskie."""

from pdf_audiobook.normalize import (
    expand_abbreviations,
    expand_numbers,
    expand_roman,
    int_to_cardinal,
    normalize_text,
    ordinal_pl,
    roman_to_int,
)


# --- liczby glowne -------------------------------------------------------- #
def test_cardinal_basics():
    assert int_to_cardinal(0) == "zero"
    assert int_to_cardinal(1) == "jeden"
    assert int_to_cardinal(15) == "piętnaście"
    assert int_to_cardinal(21) == "dwadzieścia jeden"
    assert int_to_cardinal(100) == "sto"
    assert int_to_cardinal(200) == "dwieście"


def test_cardinal_thousands_no_jeden_prefix():
    assert int_to_cardinal(1000) == "tysiąc"
    assert int_to_cardinal(2000) == "dwa tysiące"
    assert int_to_cardinal(5000) == "pięć tysięcy"


def test_cardinal_year():
    assert int_to_cardinal(1939) == "tysiąc dziewięćset trzydzieści dziewięć"
    assert int_to_cardinal(2024) == "dwa tysiące dwadzieścia cztery"


def test_cardinal_million():
    assert int_to_cardinal(1_000_000) == "milion"
    assert int_to_cardinal(2_500_000) == "dwa miliony pięćset tysięcy"


def test_expand_numbers_in_text():
    assert expand_numbers("Mam 3 koty.") == "Mam trzy koty."


# --- skroty --------------------------------------------------------------- #
def test_abbreviations_common():
    assert expand_abbreviations("np. kot") == "na przyklad kot"
    assert expand_abbreviations("itd.") == "i tak dalej"
    assert expand_abbreviations("m.in. to") == "miedzy innymi to"
    assert expand_abbreviations("dr Nowak") == "doktor Nowak"


def test_abbreviation_case_insensitive_at_sentence_start():
    assert expand_abbreviations("Np. tak") == "na przyklad tak"


def test_abbreviation_does_not_touch_inside_word():
    # "wgiser" zaczyna sie od "wg" — nie moze byc rozwiniete.
    assert "według" not in expand_abbreviations("wgiser")


# --- liczby rzymskie ------------------------------------------------------ #
def test_roman_to_int_valid_and_invalid():
    assert roman_to_int("XIX") == 19
    assert roman_to_int("III") == 3
    assert roman_to_int("IIII") is None  # niepoprawny zapis


def test_ordinal_pl():
    assert ordinal_pl(3) == "trzeci"
    assert ordinal_pl(19) == "dziewiętnasty"
    assert ordinal_pl(21) == "dwudziesty pierwszy"


def test_roman_only_in_context():
    assert expand_roman("rozdział III") == "rozdział trzeci"
    assert expand_roman("XIX wiek") == "dziewiętnasty wiek"
    # Bez kontekstu liczba rzymska zostaje nietknieta (np. inicjaly).
    assert expand_roman("Cwiczenie X i Y") == "Cwiczenie X i Y"


# --- calosc --------------------------------------------------------------- #
def test_normalize_text_pipeline():
    out = normalize_text("W XIX w. żyło tu np. 1500 osób.")
    assert "dziewiętnasty wiek" in out
    assert "na przyklad" in out
    assert "tysiąc pięćset" in out
