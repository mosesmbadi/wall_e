"""CSV and DB-row chunking — split tabular data into token-bounded chunks."""
from __future__ import annotations
import csv
import os

import tiktoken

from core.config import CHUNK_MAX_TOKENS
from ingestion.schema import resolve_foreign_keys

_tokenizer = tiktoken.get_encoding("cl100k_base")


def _chunk_rows(
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


def _to_index_docs(table_name: str, source_file: str, chunks: list[dict]) -> list[dict]:
    return [
        {
            "text":         c["text"],
            "doc_name":     table_name,
            "doc_type":     "CSV Data",
            "source_type":  "csv",
            "table_name":   table_name,
            "chunk_index":  i,
            "source_file":  source_file,
            "start_page":   c["start_row"],
            "end_page":     c["end_row"],
            "page_numbers": c["row_range"],
        }
        for i, c in enumerate(chunks)
    ]


def process_csv(csv_path: str, lookups: dict | None = None) -> list[dict]:
    """Chunk a CSV file and return indexable dicts."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    if lookups is None:
        lookups = {}

    table_name = os.path.splitext(os.path.basename(csv_path))[0]

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return []
        headers = [c.strip() for c in reader.fieldnames]
        chunks = _chunk_rows(table_name, headers, reader, lookups)

    return _to_index_docs(table_name, os.path.basename(csv_path), chunks)


def process_rows(table_name: str, rows: list[dict], lookups: dict | None = None) -> list[dict]:
    """Chunk in-memory row dicts (from Postgres) and return indexable dicts."""
    if lookups is None:
        lookups = {}
    if not rows:
        return []

    headers = list(rows[0].keys())
    str_rows = (
        {k: str(v) if v is not None else "" for k, v in row.items()}
        for row in rows
    )
    chunks = _chunk_rows(table_name, headers, str_rows, lookups)
    return _to_index_docs(table_name, table_name, chunks)
