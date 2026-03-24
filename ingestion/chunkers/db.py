"""Database row chunking — split DB tabular data into token-bounded chunks."""
from __future__ import annotations

from ingestion.chunkers.tabular import chunk_tabular_rows, to_index_docs

def process_db_rows(table_name: str, rows: list[dict], lookups: dict | None = None) -> list[dict]:
    """Chunk in-memory row dicts (from an SQL DB) and return indexable dicts."""
    if lookups is None:
        lookups = {}
    if not rows:
        return []

    headers = list(rows[0].keys())
    # Ensure all values are converted to strings, skipping None
    str_rows = (
        {k: str(v) if v is not None else "" for k, v in row.items()}
        for row in rows
    )
    chunks = chunk_tabular_rows(table_name, headers, str_rows, lookups)
    return to_index_docs(table_name, table_name, chunks, source_type="db")