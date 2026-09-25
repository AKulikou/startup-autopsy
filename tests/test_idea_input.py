import pytest

from core.idea_input import MIN_LETTERS, InvalidIdeaError, prepare_idea


@pytest.mark.parametrize("text", ["", "   \n\t  "])
def test_empty_text_is_rejected(text):
    with pytest.raises(InvalidIdeaError) as error:
        prepare_idea(text)
    assert error.value.code == "EMPTY"


@pytest.mark.parametrize("text", ["ABC123", "🚀🚀🚀 💰💰💰 !!!", "птички поют"])
def test_text_with_few_letters_is_rejected(text):
    with pytest.raises(InvalidIdeaError) as error:
        prepare_idea(text)
    assert error.value.code == "TOO_SHORT"
    assert f"at least {MIN_LETTERS}" in str(error.value)


def test_short_meaningful_text_goes_on_to_the_input_check():
    text, replaced = prepare_idea("  продать бабушкину квартиру \n")
    assert text == "продать бабушкину квартиру"
    assert replaced == 0


def test_straight_quotes_become_typographic_and_keep_their_meaning():
    text, replaced = prepare_idea(
        'Declared as "costume jewelry" to avoid duties, see "80% used" and a stray " here'
    )
    assert '"' not in text
    assert "“costume jewelry”" in text
    assert "“80% used”" in text
    assert replaced == 5
