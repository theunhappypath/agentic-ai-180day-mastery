"""Count the tokens the lab sends, with the model's own tokenizer when it can (Day 1).

Ollama runs GGUF files with the tokenizer baked in and offers no counting endpoint, so the
lab loads the same tokenizer from Hugging Face (`[tokenizers]` in lab.toml). Without one it
falls back to a rough estimate and says so: estimates are never logged as exact counts.
"""

from __future__ import annotations

import math
from functools import cache

CHARS_PER_TOKEN_ESTIMATE = 4  # English-prose rule of thumb; Day 1 showed how wrong it can be


@cache
def _load(repo: str):
    """The tokenizer for `repo`, from the local Hugging Face cache, downloading it once."""
    from huggingface_hub import hf_hub_download
    from tokenizers import Tokenizer

    try:
        path = hf_hub_download(repo, "tokenizer.json", local_files_only=True)
    except Exception:
        path = hf_hub_download(repo, "tokenizer.json")  # first use: ~7 MB download
    return Tokenizer.from_file(path)


def tokenizer_for(model: str, mapping: dict[str, str]):
    """The tokenizer for an Ollama model tag, or None if there is no mapping or no download."""
    key = model if ":" in model else f"{model}:latest"
    repo = mapping.get(key) or mapping.get(model)
    if not repo:
        return None
    try:
        return _load(repo)
    except Exception:
        return None


def count(text: str, model: str, mapping: dict[str, str]) -> tuple[int, bool]:
    """(tokens, exact). Exact with the model's tokenizer, else a characters/4 estimate."""
    tok = tokenizer_for(model, mapping)
    if tok is not None:
        return len(tok.encode(text, add_special_tokens=False).ids), True
    return math.ceil(len(text) / CHARS_PER_TOKEN_ESTIMATE), False
