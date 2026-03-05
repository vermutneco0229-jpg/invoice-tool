#!/usr/bin/env python3
"""Main processing script for Obsidian notes with Gemini API.

Reads changed markdown files, calls Gemini API for summarization,
tag extraction, and related note detection, then updates YAML frontmatter.
"""

import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from frontmatter_utils import parse_frontmatter, serialize_frontmatter
from gemini_client import GeminiClient

VAULT_ROOT = Path(".")
EXCLUDED_DIRS = {".github", "docs", "Templates", ".obsidian", ".git", ".trash"}
MODEL_NAME = "gemini-2.0-flash"


def get_all_note_titles() -> dict[str, Path]:
    """Collect all note titles and their paths in the vault."""
    notes = {}
    for md_file in VAULT_ROOT.rglob("*.md"):
        # Skip excluded directories
        if any(part in EXCLUDED_DIRS for part in md_file.parts):
            continue
        notes[md_file.stem] = md_file
    return notes


def compute_content_hash(body: str) -> str:
    """Compute SHA-256 hash of body content for idempotency check."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def process_note(
    filepath: Path,
    client: GeminiClient,
    all_notes: dict[str, Path],
    force: bool = False,
) -> bool:
    """Process a single note. Returns True if the note was modified."""
    content = filepath.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(content)

    # Skip empty or very short notes
    if len(body.strip()) < 20:
        print(f"  Skipping {filepath}: too short ({len(body.strip())} chars)")
        return False

    # Idempotency check
    body_hash = compute_content_hash(body)
    if not force and frontmatter.get("ai_content_hash") == body_hash:
        print(f"  Skipping {filepath}: content unchanged")
        return False

    print(f"  Processing {filepath}...")

    # Summarize
    try:
        summary = client.summarize(body)
        print(f"    Summary: {summary[:80]}...")
    except Exception as e:
        print(f"    Error summarizing: {e}")
        summary = frontmatter.get("ai_summary", "")

    # Extract tags
    try:
        tags = client.extract_tags(body)
        print(f"    Tags: {tags}")
    except Exception as e:
        print(f"    Error extracting tags: {e}")
        tags = frontmatter.get("ai_tags", [])

    # Find related notes
    try:
        other_titles = [t for t in all_notes.keys() if t != filepath.stem]
        related = client.find_related_notes(body, other_titles)
        print(f"    Related: {related}")
    except Exception as e:
        print(f"    Error finding relations: {e}")
        related = frontmatter.get("ai_related_notes", [])

    # Update frontmatter (preserve user fields)
    frontmatter["ai_summary"] = summary
    frontmatter["ai_tags"] = tags
    frontmatter["ai_related_notes"] = [f"[[{r}]]" for r in related]
    frontmatter["ai_content_hash"] = body_hash
    frontmatter["ai_processed_at"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    frontmatter["ai_model"] = MODEL_NAME

    # Write back
    new_content = serialize_frontmatter(frontmatter, body)
    filepath.write_text(new_content, encoding="utf-8")
    print(f"  Done: {filepath}")
    return True


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set")
        sys.exit(1)

    reindex_all = os.environ.get("REINDEX_ALL", "").lower() == "true"
    changed_files_raw = os.environ.get("CHANGED_FILES", "").strip()

    client = GeminiClient(api_key=api_key, model=MODEL_NAME)
    all_notes = get_all_note_titles()

    print(f"Vault contains {len(all_notes)} notes")

    if reindex_all:
        # Process all notes in the vault
        files_to_process = list(all_notes.values())
        print(f"Full reindex: processing all {len(files_to_process)} notes")
    elif changed_files_raw:
        # Process only changed files
        files_to_process = []
        for f in changed_files_raw.split("\n"):
            f = f.strip()
            if f and Path(f).exists() and f.endswith(".md"):
                files_to_process.append(Path(f))
        print(f"Processing {len(files_to_process)} changed files")
    else:
        print("No files to process")
        return

    modified_count = 0
    for filepath in files_to_process:
        try:
            if process_note(filepath, client, all_notes, force=reindex_all):
                modified_count += 1
        except Exception as e:
            print(f"  Error processing {filepath}: {e}")
            continue

    print(f"\nCompleted: {modified_count}/{len(files_to_process)} notes modified")


if __name__ == "__main__":
    main()
