"""CSV row chunking — split tabular data into token-bounded chunks."""
from __future__ import annotations
import csv
import os

from ingestion.chunkers.tabular import chunk_tabular_rows, to_index_docs

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
        chunks = chunk_tabular_rows(table_name, headers, reader, lookups)

    return to_index_docs(table_name, os.path.basename(csv_path), chunks, source_type="csv")
