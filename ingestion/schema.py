"""
FK resolution and schema document building.
Works with both CSV files on disk (chunk_dir pipeline) and
in-memory row dicts from Postgres (chunk_db pipeline).
"""
from __future__ import annotations
import csv
import os

import tiktoken

from core.config import CHUNK_MAX_TOKENS

_tokenizer = tiktoken.get_encoding("cl100k_base")


# ── FK resolution ─────────────────────────────────────────────────────────────

def build_lookup_tables(csv_dir: str) -> tuple[dict, dict]:
    """
    Scan CSVs under csv_dir. For every file with 'id' and 'name' columns,
    build {id: name} lookup dicts keyed by table suffix.
    Returns (lookups, table_key_map).
    """
    lookups: dict = {}
    table_key_map: dict = {}

    for root, _dirs, files in os.walk(csv_dir):
        for fname in files:
            if not fname.lower().endswith(".csv"):
                continue
            path = os.path.join(root, fname)
            table_name = os.path.splitext(fname)[0]
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    reader = csv.DictReader(fh)
                    if not reader.fieldnames:
                        continue
                    cols = [c.strip() for c in reader.fieldnames]
                    if "id" not in cols or "name" not in cols:
                        continue
                    id_to_name = {
                        (row.get("id") or "").strip(): (row.get("name") or "").strip()
                        for row in reader
                        if (row.get("id") or "").strip() and (row.get("name") or "").strip()
                    }
                    if not id_to_name:
                        continue
                    parts = table_name.split("_")
                    for i in range(len(parts)):
                        candidate = "_".join(parts[i:])
                        if candidate not in lookups:
                            lookups[candidate] = id_to_name
                            table_key_map[candidate] = table_name
                            break
                    else:
                        lookups[table_name] = id_to_name
                        table_key_map[table_name] = table_name
            except Exception:
                continue

    return lookups, table_key_map


def build_lookup_tables_from_rows(tables: dict[str, list[dict]]) -> tuple[dict, dict]:
    """Build lookup tables from in-memory {table_name: [row_dicts]} (used by chunk_db)."""
    lookups: dict = {}
    table_key_map: dict = {}

    for table_name, rows in tables.items():
        if not rows:
            continue
        cols = list(rows[0].keys())
        if "id" not in cols or "name" not in cols:
            continue
        id_to_name = {
            str(row.get("id", "")).strip(): str(row.get("name", "")).strip()
            for row in rows
            if row.get("id") and row.get("name")
        }
        if not id_to_name:
            continue
        parts = table_name.split("_")
        for i in range(len(parts)):
            candidate = "_".join(parts[i:])
            if candidate not in lookups:
                lookups[candidate] = id_to_name
                table_key_map[candidate] = table_name
                break
        else:
            lookups[table_name] = id_to_name
            table_key_map[table_name] = table_name

    return lookups, table_key_map


def resolve_foreign_keys(row: dict, headers: list[str], lookups: dict) -> dict:
    resolved = {}
    skip = {"created_by", "updated_by", "approved_by", "confirmed_by", "reviewed_by", "lab_user"}
    for col in headers:
        val = (row.get(col) or "").strip()
        if not val or val in ("--", "-----", '""', "''"):
            continue
        resolved[col] = val
        if col.endswith("_id"):
            fk_base = col[:-3]
            if fk_base in skip:
                continue
            lookup = lookups.get(fk_base)
            if lookup and val in lookup:
                resolved[f"{fk_base}_name"] = lookup[val]
    return resolved


# ── Schema document ───────────────────────────────────────────────────────────

def build_schema_document(csv_dir: str, lookups: dict, table_key_map: dict) -> str:
    lines = [
        "DATABASE SCHEMA AND TABLE RELATIONSHIPS",
        "=" * 50,
        "This document describes all data tables, their columns, "
        "and how they relate to each other via foreign keys.\n",
    ]
    for root, _dirs, files in os.walk(csv_dir):
        for fname in sorted(files):
            if not fname.lower().endswith(".csv"):
                continue
            path = os.path.join(root, fname)
            table_name = os.path.splitext(fname)[0]
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    reader = csv.DictReader(fh)
                    if not reader.fieldnames:
                        continue
                    cols = [c.strip() for c in reader.fieldnames]
            except Exception:
                continue
            fk_descs = [
                f"  - {col} → references {table_key_map.get(col[:-3], col[:-3])}.id"
                for col in cols
                if col.endswith("_id") and col[:-3] in lookups
            ]
            lines.append(f"Table: {table_name}")
            lines.append(f"  Columns: {', '.join(cols)}")
            if fk_descs:
                lines.append("  Foreign keys:")
                lines.extend(fk_descs)
            lines.append("")
    return "\n".join(lines)


def build_schema_document_from_rows(
    tables: dict[str, list[dict]], lookups: dict, table_key_map: dict
) -> str:
    lines = [
        "DATABASE SCHEMA AND TABLE RELATIONSHIPS",
        "=" * 50,
        "This document describes all data tables, their columns, "
        "and how they relate to each other via foreign keys.\n",
    ]
    for table_name, rows in sorted(tables.items()):
        cols = list(rows[0].keys()) if rows else []
        fk_descs = [
            f"  - {col} → references {table_key_map.get(col[:-3], col[:-3])}.id"
            for col in cols
            if col.endswith("_id") and col[:-3] in lookups
        ]
        lines.append(f"Table: {table_name}")
        lines.append(f"  Columns: {', '.join(cols)}")
        if fk_descs:
            lines.append("  Foreign keys:")
            lines.extend(fk_descs)
        lines.append("")
    return "\n".join(lines)


# ── Schema chunking ───────────────────────────────────────────────────────────

def schema_to_chunks(schema_text: str) -> list[dict]:
    """Split a schema document into indexable chunks."""
    schema_tokens = len(_tokenizer.encode(schema_text))
    if schema_tokens <= CHUNK_MAX_TOKENS * 3:
        texts = [schema_text]
    else:
        sections = schema_text.split("\nTable: ")
        current = sections[0]
        texts = []
        for section in sections[1:]:
            full = "\nTable: " + section
            if len(_tokenizer.encode(current + full)) > CHUNK_MAX_TOKENS:
                texts.append(current)
                current = "DATABASE SCHEMA (continued)\n" + full
            else:
                current += full
        if current:
            texts.append(current)

    return [
        {
            "text":        t,
            "doc_name":    "database_schema",
            "doc_type":    "Schema",
            "source_type": "schema",
            "table_name":  "",
            "chunk_index": i,
            "source_file": "_schema",
            "page_numbers": "schema",
            "start_page":  0,
            "end_page":    0,
        }
        for i, t in enumerate(texts)
    ]
