"""Tests for TextNormalizer in wmguru/helpers/utils.py."""

from wmguru.helpers.utils import TextNormalizer


def test_accents_are_taken_off():
    assert TextNormalizer().to_comparable_text("Düsseldorf") == "dusseldorf"
    assert TextNormalizer().to_comparable_text("São Paulo") == "sao paulo"


def test_the_turkish_dotless_i_becomes_a_plain_i():
    """It is a letter of its own, so taking accents off does not reach it."""
    assert TextNormalizer().to_comparable_text("Bakı Olimpiya") == "baki olimpiya"


def test_upper_case_is_folded_down():
    assert TextNormalizer().to_comparable_text("METLIFE") == "metlife"


def test_two_spellings_of_the_same_country_are_recognised():
    normalizer = TextNormalizer()

    assert normalizer.mean_the_same_country("Korea", "Korea Republic") is True
    assert normalizer.mean_the_same_country("Türkiye", "turkiye") is True


def test_two_different_countries_are_kept_apart():
    normalizer = TextNormalizer()

    assert normalizer.mean_the_same_country("Brazil", "Belgium") is False


def test_an_empty_country_never_matches():
    normalizer = TextNormalizer()

    assert normalizer.mean_the_same_country("", "Brazil") is False
