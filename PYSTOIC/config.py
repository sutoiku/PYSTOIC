import re
from typing import Literal

NotebookLanguage = Literal["ai", "html", "javascript", "markdown", "python", "sql"]
BLOCK_SPLIT_PATTERNS: dict[NotebookLanguage, str] = {
    "ai": r"(// @id \w+)",
    "html": r"(<!-- @id \w+ -->)",
    "javascript": r"(// @id \w+)",
    "markdown": r"(<!-- @id \w+ -->)",
    "python": r"(# @id \w+)",
    "sql": r"(-- @id \w+)",
}
NB_FILE_NAMES: dict[NotebookLanguage, str] = {
    "ai": "blocks.ai",
    "html": "blocks.html",
    "javascript": "blocks.js",
    "markdown": "blocks.md",
    "python": "blocks.py",
    "sql": "blocks.sql",
}
PYTHON_EXCLUSION_PATTERNS = [
    re.compile(r"#\s*exclude[:#\s]*"),
    re.compile(r"#\s*test[:#\s]*"),
    re.compile(r"def\s+test_"),
]
