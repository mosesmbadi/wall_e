"""Core base code for chunking any tabular data (CSV, DB rows)."""
from __future__ import annotations

import tiktoken

from core.config import CHUNK_MAX_TOKENS
from ingestion.schema import resolve_foreign_keys

_tokenizer = tiktoken.get_encoding("cl100k_base")


def chunk_tabular_rows(
    table_name: str,
    headers: list[str],
    row_iter,  # iterable of raw row dicts
    lookups: dict,
) -> list[dict]:
    """Core chunking logic shared by CSV files and in-memory row lists."""
    header_text = f"Table: {table_name}\nColumns: {', '.join(headers)}\n\n"
    header_tokens = len(_tokenizer.encode(header_text))
    current_rows: list[str] = []
    current_tokens = header_tokens
    start_row = 1
    chunks = []

    for row_num, raw_row in enumerate(row_iter, start=1):
        resolved = resolve_foreign_keys(raw_row, headers, lookups)
        if not resolved:
            continue
        row_text = ", ".join(f"{k}={v}" for k, v in resolved.items())
        row_tokens = len(_tokenizer.encode(row_text))

        if current_tokens + row_tokens > CHUNK_MAX_TOKENS and current_rows:
            chunks.append({
                "text":      header_text + "\n".join(current_rows),
                "start_row": start_row,
                "end_row":   row_num - 1,
                "row_range": f"rows {start_row}-{row_num - 1}",
            })
            current_rows, current_tokens, start_row = [], header_tokens, row_num

        current_rows.append(row_text)
        current_tokens += row_tokens

    if current_rows:
        end_row = start_row + len(current_rows) - 1
        chunks.append({
            "text":      header_text + "\n".join(current_rows),
            "start_row": start_row,
            "end_row":   end_row,
            "row_range": f"rows {start_row}-{end_row}",
        })

    return chunks


def to_index_docs(table_name: str, source_file: str, chunks: list[dict], source_type: str = "csv") -> list[dict]:
    return [
        {
            "text":         c["text"],
            "doc_name":     table_name,
            "doc_type":     "Database Table",
            "source_type":  source_type,
            "table_name":   table_name,
            "chunk_index":  i,
            "source_file":  source_file,
            "start_page":   c["start_row"],
            "end_page":     c["end_row"],
            "page_numbers": c["row_range"],
        }
        for i, c in enumerate(chunks)
    ]