"""Gemini API client with rate limiting and retry logic."""

import json
import time
from pathlib import Path

import google.generativeai as genai

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


SUMMARIZE_PROMPT = _load_prompt("summarize_ja.txt")
TAGS_PROMPT = _load_prompt("extract_tags_ja.txt")
RELATIONS_PROMPT = _load_prompt("find_relations_ja.txt")
GENERATE_DOC_PROMPT = _load_prompt("generate_document_ja.txt")


class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
        self._last_request_time = 0.0

    def _rate_limit(self):
        """Enforce minimum 0.5s between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self._last_request_time = time.time()

    def _call(self, prompt: str, max_retries: int = 3) -> str:
        """Call Gemini API with retry logic."""
        self._rate_limit()
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt)
                return response.text
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                wait = 2 ** (attempt + 1)
                print(f"  Retry {attempt + 1}/{max_retries} after {wait}s: {e}")
                time.sleep(wait)
        return ""

    def summarize(self, text: str) -> str:
        """Generate a Japanese summary of the note content."""
        prompt = SUMMARIZE_PROMPT.format(text=text[:8000])
        return self._call(prompt).strip()

    def extract_tags(self, text: str) -> list[str]:
        """Extract tags from note content as a list of strings."""
        prompt = TAGS_PROMPT.format(text=text[:8000])
        result = self._call(prompt).strip()
        # Extract JSON array from response
        try:
            # Try to find JSON array in response
            start = result.find("[")
            end = result.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(result[start:end])
        except (json.JSONDecodeError, ValueError):
            pass
        # Fallback: split by common delimiters
        return [t.strip().strip('"').strip("'") for t in result.split(",") if t.strip()]

    def find_related_notes(self, text: str, titles: list[str]) -> list[str]:
        """Find related notes from a list of titles."""
        if not titles:
            return []
        titles_str = "\n".join(f"- {t}" for t in titles)
        prompt = RELATIONS_PROMPT.format(text=text[:4000], titles=titles_str)
        result = self._call(prompt).strip()
        try:
            start = result.find("[")
            end = result.rfind("]") + 1
            if start >= 0 and end > start:
                parsed = json.loads(result[start:end])
                # Only return titles that exist in the vault
                return [t for t in parsed if t in titles]
        except (json.JSONDecodeError, ValueError):
            pass
        return []

    def generate_document(self, text: str, fmt: str, summary: str, tags: str) -> str:
        """Generate a polished document from note content."""
        prompt = GENERATE_DOC_PROMPT.format(
            text=text[:12000], format=fmt, summary=summary, tags=tags
        )
        return self._call(prompt).strip()
