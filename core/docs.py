"""
Domain helpers shared between ingestion and rag.
Name normalisation, doc-type inference, index name derivation.
"""
import os
import re


def normalize_doc_key(filename: str) -> str:
    base = os.path.splitext(filename)[0]
    return re.sub(r"[^a-z0-9]+", "", base.lower())


def clean_doc_name(filename: str) -> str:
    base = os.path.splitext(filename)[0]
    base = re.sub(r"\(\d+\)$", "", base).strip()
    base = base.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", base).strip()


def infer_doc_type(filename: str) -> str:
    lower = filename.lower()
    if "service manual" in lower or lower.endswith("_sm.pdf") or " sm.pdf" in lower:
        return "Service Manual"
    if "user manual" in lower or "manual" in lower:
        return "User Manual"
    return "Document"


def dir_to_index_name(dir_path: str) -> str:
    """e.g. data/eqa-monthly  →  eqa_monthly_index"""
    basename = os.path.basename(dir_path.rstrip("/"))
    return re.sub(r"[^a-z0-9]+", "_", basename.lower()).strip("_") + "_index"


def db_name_to_index(db_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", db_name.lower()).strip("_") + "_index"


def resolve_search_index(index_names_env: str) -> str:
    """
    Resolve the OpenSearch index (or comma-separated indices) to query.
    INDEX_NAMES env var takes priority; falls back to wildcard '*_index'.
    """
    if index_names_env:
        return ",".join(n.strip() for n in index_names_env.split(",") if n.strip())
    return "*_index"
