from __future__ import annotations

import re

_SALARY_PATTERN = re.compile(
    r"(?:USD|ARS|\$)\s?\d[\d.,]*(?:\s*-\s*(?:USD|ARS|\$)?\s?\d[\d.,]*)?",
    re.IGNORECASE,
)


def extract_salary(text: str) -> str | None:
    match = _SALARY_PATTERN.search(text)
    return match.group(0).strip() if match else None
