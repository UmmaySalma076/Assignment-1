MAX_TITLE_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 1000


def validate_title(value: str | None) -> str:
    if value is None:
        raise ValueError("Title is required.")

    normalized = str(value).strip()
    if not normalized:
        raise ValueError("Title must not be empty.")
    if len(normalized) > MAX_TITLE_LENGTH:
        raise ValueError(f"Title must be {MAX_TITLE_LENGTH} characters or fewer.")
    return normalized


def validate_description(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()
    if len(normalized) > MAX_DESCRIPTION_LENGTH:
        raise ValueError(f"Description must be {MAX_DESCRIPTION_LENGTH} characters or fewer.")
    return normalized or None


def validate_completed(value: bool | int) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    raise ValueError("Completion status must be a boolean value.")
