"""PDF chunking — extract text, split into sentence-aware, page-tracked chunks."""
from __future__ import annotations
import os
import re

import nltk
import tiktoken
from pypdf import PdfReader

from core.config import CHUNK_MAX_TOKENS, CHUNK_OVERLAP_TOKENS, PARAGRAPH_BREAK_NEWLINES

try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt", quiet=True)
    nltk.download("punkt_tab", quiet=True)

from nltk.tokenize import sent_tokenize  # noqa: E402

_tokenizer = tiktoken.get_encoding("cl100k_base")


def get_chunks_with_pages(pdf_path: str) -> list[dict]:
    """
    Extract text from a PDF and return a list of chunks, each with:
    text, start_page, end_page, page_numbers.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    reader = PdfReader(pdf_path)
    pages_data = [
        {"page_num": i + 1, "text": page.extract_text()}
        for i, page in enumerate(reader.pages)
        if page.extract_text() and page.extract_text().strip()
    ]
    if not pages_data:
        raise ValueError("No text extracted from PDF.")

    paragraphs_with_pages = []
    for pd_ in pages_data:
        raw = re.split(f"\n{{{PARAGRAPH_BREAK_NEWLINES},}}", pd_["text"])
        for para in raw:
            para = para.strip()
            if para:
                paragraphs_with_pages.append({
                    "sentences": [s.strip() for s in sent_tokenize(para) if s.strip()],
                    "page_num": pd_["page_num"],
                })

    chunks = []
    current_sents: list[str] = []
    current_tokens = 0
    start_page = end_page = None

    for pd_ in paragraphs_with_pages:
        for sentence in pd_["sentences"]:
            stokens = len(_tokenizer.encode(sentence))
            if start_page is None:
                start_page = end_page = pd_["page_num"]
            end_page = max(end_page, pd_["page_num"])

            if current_tokens + stokens > CHUNK_MAX_TOKENS and current_sents:
                page_range = str(start_page) if start_page == end_page else f"{start_page}-{end_page}"
                chunks.append({
                    "text": " ".join(current_sents),
                    "start_page": start_page,
                    "end_page": end_page,
                    "page_numbers": page_range,
                })
                overlap_sents: list[str] = []
                overlap_tokens = 0
                for s in reversed(current_sents):
                    st = len(_tokenizer.encode(s))
                    if overlap_tokens + st <= CHUNK_OVERLAP_TOKENS:
                        overlap_sents.insert(0, s)
                        overlap_tokens += st
                    else:
                        break
                current_sents, current_tokens = overlap_sents, overlap_tokens
                start_page = end_page = pd_["page_num"]

            current_sents.append(sentence)
            current_tokens += stokens

    if current_sents:
        page_range = str(start_page) if start_page == end_page else f"{start_page}-{end_page}"
        chunks.append({
            "text": " ".join(current_sents),
            "start_page": start_page,
            "end_page": end_page,
            "page_numbers": page_range,
        })

    return chunks


def process_pdf(pdf_path: str, doc_name: str, doc_type: str) -> list[dict]:
    """Chunk a PDF and return indexable dicts."""
    return [
        {
            "text":         c["text"],
            "doc_name":     doc_name,
            "doc_type":     doc_type,
            "source_type":  "pdf",
            "table_name":   "",
            "chunk_index":  i,
            "source_file":  os.path.basename(pdf_path),
            "start_page":   c["start_page"],
            "end_page":     c["end_page"],
            "page_numbers": c["page_numbers"],
        }
        for i, c in enumerate(get_chunks_with_pages(pdf_path))
    ]
