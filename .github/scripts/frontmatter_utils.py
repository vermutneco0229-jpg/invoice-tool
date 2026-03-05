"""YAML frontmatter parser and serializer for Obsidian markdown files."""

import re
import yaml
from typing import Any

FRONTMATTER_REGEX = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content.

    Returns (frontmatter_dict, body_text).
    If no frontmatter exists, returns ({}, full_content).
    """
    match = FRONTMATTER_REGEX.match(content)
    if match:
        fm_text = match.group(1)
        body = content[match.end():]
        try:
            fm = yaml.safe_load(fm_text) or {}
        except yaml.YAMLError:
            fm = {}
            body = content
    else:
        fm = {}
        body = content
    return fm, body


def serialize_frontmatter(fm: dict[str, Any], body: str) -> str:
    """Reconstruct file content with frontmatter + body.

    Uses allow_unicode=True for Japanese content.
    """
    if not fm:
        return body
    fm_text = yaml.dump(
        fm,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    return f"---\n{fm_text}---\n{body}"
