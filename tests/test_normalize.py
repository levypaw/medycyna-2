"""Testy normalizacji tekstu PL: skroty, liczby, liczby rzymskie."""

from pdf_audiobook.normalize import (
    expand_abbreviations,
    expand_numbers,
    expand_oblique_after_prep,
    expand_roman,
    expand_years,
    int_to_cardinal,
    int_to_oblique,
    normalize_text,
    ordinal_genitive,
    ordinal_pl,
    roman_to_int,
    year_to_words,
)


# --- liczebniki w przypadku zaleznym (po przyimkach) ---------------------- #
def test_int_to_oblique():
    assert int_to_oblique(142) == "stu czterdziestu dwóch"
    assert int_to_oblique(5) == "pięciu"
    assert int_to_oblique(200) == "dwustu"
    assert int_to_oblique(21) == "dwudziestu jeden"


def test_oblique_after_preposition():
    assert expand_oblique_after_prep("po 142 stopniach") == \
        "po stu czterdziestu dwóch stopniach"
    assert expand_oblique_after_prep("od 200 do 300") == "od dwustu do trzystu"
    assert expand_oblique_after_prep("bez 5 minut") == "bez pięciu minut"


def test_oblique_only_after_listed_prepositions():
    # "na" rzadzi biernikiem — nie zmieniamy (zostaje do mianownika).
    assert expand_oblique_after_prep("na 5 stron") == "na 5 stron"


# --- lata (forma porzadkowa, dopelniacz) ---------------------------------- #
def test_year_to_words():
    assert year_to_words(1939) == "tysiąc dziewięćset trzydziestego dziewiątego"
    assert year_to_words(1930) == "tysiąc dziewięćset trzydziestego"
    assert year_to_words(2024) == "dwa tysiące dwudziestego czwartego"


def test_ordinal_genitive():
    assert ordinal_genitive(1) == "pierwszego"
    assert ordinal_genitive(30) == "trzydziestego"
    assert ordinal_genitive(39) == "trzydziestego dziewiątego"


def test_expand_years_always_roku_genitive():
    assert expand_years("w 1930 rok") == "w tysiąc dziewięćset trzydziestego roku"
    assert expand_years("w 1930 roku") == "w tysiąc dziewięćset trzydziestego roku"
    assert expand_years("w 1930 r.") == "w tysiąc dziewięćset trzydziestego roku"


def test_abbreviations_keep_polish_diacritics():
    assert expand_abbreviations("ok.") == "około"
    assert expand_abbreviations("np.") == "na przykład"
    assert expand_abbreviations("m.in.") == "między innymi"
    assert expand_abbreviations("wg") == "według"


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


def test_long_code_read_digit_by_digit():
    # ISBN/kod (>=10 cyfr) nie jest czytany jako gigantyczny liczebnik.
    out = expand_numbers("78121415585220")
    assert "bilion" not in out
    assert out.startswith("siedem osiem jeden")


# --- skroty --------------------------------------------------------------- #
def test_abbreviations_common():
    assert expand_abbreviations("np. kot") == "na przykład kot"
    assert expand_abbreviations("itd.") == "i tak dalej"
    assert expand_abbreviations("m.in. to") == "między innymi to"
    assert expand_abbreviations("dr Nowak") == "doktor Nowak"


def test_abbreviation_case_insensitive_at_sentence_start():
    assert expand_abbreviations("Np. tak") == "na przykład tak"


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
    assert "na przykład" in out
    assert "tysiąc pięćset" in out
