"""
Chunk and index all PDFs and CSVs found under DATA_DIR.

Usage:
    DATA_DIR=data/eqa-monthly python -m ingestion.cli.chunk_dir [--fresh]

The index name is derived from the directory name:
    data/eqa-monthly  →  eqa_monthly_index
"""
import os
import sys

from core.docs import normalize_doc_key, clean_doc_name, infer_doc_type, dir_to_index_name
from ingestion.chunkers.csv import process_csv
from ingestion.chunkers.pdf import process_pdf
from ingestion.indexer import bulk_index, ensure_index
from ingestion.schema import (
    build_lookup_tables, build_schema_document, schema_to_chunks,
)


def main() -> None:
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    _default_data_dir = os.path.join(_script_dir, "..", "..", "data")
    data_dir = os.getenv("DATA_DIR", _default_data_dir)
    if not os.path.isabs(data_dir):
        data_dir = os.path.join(_script_dir, "..", "..", data_dir)
    data_dir = os.path.normpath(data_dir)

    if not os.path.isdir(data_dir):
        print(f"Error: DATA_DIR not found: {data_dir}")
        sys.exit(1)

    fresh = "--fresh" in sys.argv
    index_name = dir_to_index_name(data_dir)
    print(f"Data directory : {data_dir}")
    print(f"Target index   : {index_name}")
    if fresh:
        print("Mode: fresh (existing index will be deleted and recreated)")

    ensure_index(index_name, fresh=fresh)

    print("\nBuilding FK lookup tables...")
    lookups, table_key_map = build_lookup_tables(data_dir)
    print(f"  {len(lookups)} reference table(s) loaded.")

    schema_text = build_schema_document(data_dir, lookups, table_key_map)
    if schema_text.strip():
        print("\nIndexing schema document...")
        schema_chunks = schema_to_chunks(schema_text)
        bulk_index(schema_chunks, index_name)
        print(f"  {len(schema_chunks)} schema chunk(s) indexed.")

    SUPPORTED = {".pdf", ".csv"}
    documents = []
    seen: set[str] = set()

    for root, _dirs, files in os.walk(data_dir):
        for file_name in sorted(files):
            ext = os.path.splitext(file_name)[1].lower()
            if ext not in SUPPORTED:
                continue
            key = normalize_doc_key(file_name)
            if key in seen:
                continue
            seen.add(key)
            path = os.path.join(root, file_name)
            if ext == ".pdf":
                documents.append({
                    "path": path,
                    "name": clean_doc_name(file_name),
                    "type": infer_doc_type(file_name),
                    "file_type": "pdf",
                })
            else:
                table_name = os.path.splitext(file_name)[0]
                documents.append({
                    "path": path,
                    "name": table_name,
                    "type": "CSV Data",
                    "file_type": "csv",
                })

    print(f"\nFound {len(documents)} document(s) to process.")

    total_chunks = len(schema_to_chunks(schema_text)) if schema_text.strip() else 0
    doc_id_offset = total_chunks

    try:
        for doc in documents:
            print(f"\nProcessing: {doc['name']} ({doc['type']})")
            if doc["file_type"] == "pdf":
                chunks = process_pdf(doc["path"], doc["name"], doc["type"])
            else:
                chunks = process_csv(doc["path"], lookups=lookups)
            print(f"  {len(chunks)} chunk(s) created — embedding and indexing...")
            indexed = bulk_index(chunks, index_name, start_id=doc_id_offset)
            doc_id_offset += indexed
            total_chunks += indexed
            print("  Done.")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print(f"Indexed {total_chunks} chunk(s) from {len(documents)} document(s) into '{index_name}'.")


if __name__ == "__main__":
    main()
