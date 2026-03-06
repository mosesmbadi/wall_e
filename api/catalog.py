"""
Document catalog — discovers files in DATA_DIR and builds a searchable list
used to auto-infer doc filters from natural-language questions.
"""
from __future__ import annotations
import os
import re

from core.config import DATA_DIR
from core.docs import normalize_doc_key, clean_doc_name, infer_doc_type


def _tokenize_for_match(text: str) -> list[str]:
    cleaned = re.sub(r"[^a-z0-9]+", " ", text.lower())
    stopwords = {"user", "manual", "service", "lis", "interface", "guide", "version", "ver", "v"}
    return [t for t in cleaned.split() if t and t not in stopwords]


def build_document_catalog(data_dir: str = "") -> list[dict]:
    effective_dir = data_dir or DATA_DIR
    if not effective_dir:
        effective_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    if not os.path.isabs(effective_dir):
        effective_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), effective_dir)
    if not os.path.isdir(effective_dir):
        return []

    catalog = []
    seen: set[str] = set()

    for root, _dirs, files in os.walk(effective_dir):
        for file_name in sorted(files):
            ext = os.path.splitext(file_name)[1].lower()
            if ext not in (".pdf", ".csv"):
                continue
            key = normalize_doc_key(os.path.splitext(file_name)[0])
            if key in seen:
                continue
            seen.add(key)

            if ext == ".pdf":
                catalog.append({
                    "doc_name":     clean_doc_name(file_name),
                    "doc_type":     infer_doc_type(file_name),
                    "source_file":  file_name,
                    "source_type":  "pdf",
                    "match_tokens": _tokenize_for_match(clean_doc_name(file_name)),
                })
            else:
                table_name = os.path.splitext(file_name)[0]
                catalog.append({
                    "doc_name":     table_name,
                    "doc_type":     "CSV Data",
                    "source_file":  file_name,
                    "source_type":  "csv",
                    "match_tokens": _tokenize_for_match(table_name.replace("_", " ")),
                })

    return catalog


DOCUMENT_CATALOG = build_document_catalog()


def infer_doc_filter_from_question(question: str) -> dict | None:
    if not DOCUMENT_CATALOG:
        return None

    normalized_question = normalize_doc_key(question)
    question_tokens = set(_tokenize_for_match(question))
    best_match = None
    best_score = 0

    for entry in DOCUMENT_CATALOG:
        doc_key = normalize_doc_key(entry["doc_name"])
        if not doc_key:
            continue
        if doc_key in normalized_question:
            score = len(doc_key)
            if score > best_score:
                best_score = score
                best_match = entry

        if question_tokens and entry["match_tokens"]:
            overlap = question_tokens.intersection(entry["match_tokens"])
            if overlap:
                score = len(overlap) * 10 + sum(len(t) for t in overlap)
                if score > best_score:
                    best_score = score
                    best_match = entry

    if best_match:
        return {
            "doc_name":    best_match["doc_name"],
            "doc_type":    best_match["doc_type"],
            "source_file": best_match["source_file"],
        }
    return None
