from __future__ import annotations

from app.models import DiffChunk


def chunk_file_diff(*, file_path: str, diff_text: str, max_chars: int) -> list[DiffChunk]:
    if len(diff_text) <= max_chars:
        return [DiffChunk(file_path=file_path, chunk_id=f'{file_path}#1', diff_text=diff_text)]

    lines = diff_text.splitlines()
    chunks: list[DiffChunk] = []
    current_lines: list[str] = []
    current_size = 0

    for line in lines:
        line_size = len(line) + 1
        if current_lines and current_size + line_size > max_chars:
            chunks.append(
                DiffChunk(
                    file_path=file_path,
                    chunk_id=f'{file_path}#{len(chunks) + 1}',
                    diff_text='\n'.join(current_lines),
                )
            )
            current_lines = []
            current_size = 0

        current_lines.append(line)
        current_size += line_size

    if current_lines:
        chunks.append(
            DiffChunk(
                file_path=file_path,
                chunk_id=f'{file_path}#{len(chunks) + 1}',
                diff_text='\n'.join(current_lines),
            )
        )

    return chunks
