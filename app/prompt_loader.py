from __future__ import annotations

from pathlib import Path


class PromptLoader:
    def __init__(self, prompt_dir: Path):
        self._prompt_dir = prompt_dir

    def load(self, filename: str) -> str:
        return (self._prompt_dir / filename).read_text(encoding='utf-8').strip()
