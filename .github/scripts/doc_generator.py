#!/usr/bin/env python3
"""Document generation script for Obsidian notes.

Reads notes with `publish: true` in frontmatter and generates
polished documents using Gemini 2.5 Pro, outputting Hugo-compatible
markdown to the docs/ directory.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from frontmatter_utils import parse_frontmatter, serialize_frontmatter
from gemini_client import GeminiClient

VAULT_ROOT = Path(".")
DOCS_DIR = VAULT_ROOT / "docs" / "content" / "posts"
EXCLUDED_DIRS = {".github", "docs", "Templates", ".obsidian", ".git", ".trash"}


def find_publishable_notes(note_path: str = "all") -> list[Path]:
    """Find notes marked for publishing."""
    if note_path != "all":
        path = Path(note_path)
        if path.exists():
            return [path]
        return []

    notes = []
    for md_file in VAULT_ROOT.rglob("*.md"):
        if any(part in EXCLUDED_DIRS for part in md_file.parts):
            continue
        content = md_file.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(content)
        if fm.get("publish") is True:
            notes.append(md_file)
    return notes


def generate_document(filepath: Path, client: GeminiClient, output_format: str):
    """Generate a polished document from a note."""
    content = filepath.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)

    summary = fm.get("ai_summary", "")
    tags = ", ".join(fm.get("ai_tags", []))

    print(f"  Generating {output_format} from {filepath}...")
    polished = client.generate_document(body, output_format, summary, tags)

    # Create Hugo-compatible post
    hugo_fm = {
        "title": filepath.stem,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tags": fm.get("ai_tags", []),
        "summary": summary,
        "draft": False,
    }

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DOCS_DIR / f"{filepath.stem}.md"
    output_path.write_text(
        serialize_frontmatter(hugo_fm, polished),
        encoding="utf-8",
    )
    print(f"  Output: {output_path}")


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set")
        sys.exit(1)

    note_path = os.environ.get("NOTE_PATH", "all")
    output_format = os.environ.get("OUTPUT_FORMAT", "blog")

    # Use gemini-2.5-pro for higher quality document generation
    client = GeminiClient(api_key=api_key, model="gemini-2.5-pro")

    notes = find_publishable_notes(note_path)
    if not notes:
        print("No publishable notes found (set `publish: true` in frontmatter)")
        return

    print(f"Generating {len(notes)} documents as '{output_format}'...")
    for filepath in notes:
        try:
            generate_document(filepath, client, output_format)
        except Exception as e:
            print(f"  Error generating from {filepath}: {e}")

    print("Document generation complete")


if __name__ == "__main__":
    main()
