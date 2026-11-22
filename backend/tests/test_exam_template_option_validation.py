"""Validation tests for options on reusable exam template questions."""

from types import SimpleNamespace

import pytest

from app.services.exam_name import validate_template_question_options


def options(count: int, correct_count: int = 1, text: str = "Option"):
    return [
        SimpleNamespace(
            option_text=text,
            is_correct=index < correct_count,
        )
        for index in range(count)
    ]


@pytest.mark.parametrize(
    ("count", "correct_count", "valid"),
    [
        (1, 1, False),
        (2, 1, True),
        (6, 1, True),
        (7, 1, False),
        (2, 0, False),
        (2, 1, True),
        (2, 2, False),
    ],
)
def test_template_question_option_count_and_correctness(count, correct_count, valid):
    question_options = options(count, correct_count)

    if valid:
        validate_template_question_options(question_options)
    else:
        with pytest.raises(ValueError):
            validate_template_question_options(question_options)


@pytest.mark.parametrize("text", ["", "   ", "\t\n"])
def test_template_question_rejects_empty_option_text(text):
    with pytest.raises(ValueError, match="non-empty text"):
        validate_template_question_options(options(2, text=text))
