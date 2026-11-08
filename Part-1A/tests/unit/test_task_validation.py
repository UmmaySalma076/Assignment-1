import pytest

from app.utils.validation import validate_description, validate_title


@pytest.mark.parametrize(
    "title",
    ["Valid Title", "   Trimmed Title   ", "A"],
)
def test_validate_title_accepts_valid_values(title: str) -> None:
    """FR-009, NFR-003: Valid title values pass validation."""
    assert validate_title(title) == title.strip()


def test_validate_title_rejects_empty_and_whitespace_only_values() -> None:
    """FR-009, NFR-003: Empty and whitespace-only titles are invalid."""
    with pytest.raises(ValueError):
        validate_title("")
    with pytest.raises(ValueError):
        validate_title("   ")


def test_validate_title_rejects_too_long_values() -> None:
    """FR-009, NFR-003: Titles above the maximum length are invalid."""
    with pytest.raises(ValueError):
        validate_title("x" * 101)


def test_validate_title_accepts_maximum_length() -> None:
    """FR-009, FR-012, NFR-003: A maximum-length title is valid."""
    value = "x" * 100

    assert validate_title(value) == value


def test_validate_description_accepts_none_and_short_values() -> None:
    """FR-001, FR-009, FR-012, NFR-003: Description is optional."""
    assert validate_description(None) is None
    assert validate_description("Short description") == "Short description"


def test_validate_description_accepts_maximum_length() -> None:
    """FR-009, FR-012, NFR-003: A maximum-length description is valid."""
    value = "x" * 1000

    assert validate_description(value) == value


def test_validate_description_rejects_too_long_values() -> None:
    """FR-009, NFR-003: Descriptions above the maximum length are invalid."""
    with pytest.raises(ValueError):
        validate_description("x" * 1001)
