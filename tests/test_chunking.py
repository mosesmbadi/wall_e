#!/usr/bin/env python3
"""
Test paragraph-aware chunking and page metadata.
Runs without requiring OpenSearch.

Usage:
    DATA_DIR=data/eqa-monthly python -m tests.test_chunking
"""
import os
import sys

import tiktoken

from ingestion.chunkers.pdf import get_chunks_with_pages


_tokenizer = tiktoken.get_encoding("cl100k_base")


def main() -> None:
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.getenv("DATA_DIR", os.path.join(_script_dir, "..", "data"))
    if not os.path.isabs(data_dir):
        data_dir = os.path.join(_script_dir, "..", data_dir)
    data_dir = os.path.normpath(data_dir)

    if not os.path.isdir(data_dir):
        print(f"DATA_DIR not found: {data_dir}")
        sys.exit(1)

    pdf_files = [f for f in os.listdir(data_dir) if f.lower().endswith(".pdf")]
    if not pdf_files:
        print("No PDF files found in data directory")
        return

    test_pdf = os.path.join(data_dir, pdf_files[0])
    print(f"Testing chunking on: {pdf_files[0]}")

    chunks = get_chunks_with_pages(test_pdf)
    token_counts = [len(_tokenizer.encode(c["text"])) for c in chunks]

    print(f"\nChunks     : {len(chunks)}")
    print(f"Min tokens : {min(token_counts)}")
    print(f"Max tokens : {max(token_counts)}")
    print(f"Avg tokens : {sum(token_counts) / len(token_counts):.1f}")

    single = sum(1 for c in chunks if c["start_page"] == c["end_page"])
    print(f"\nSingle-page chunks : {single}")
    print(f"Multi-page chunks  : {len(chunks) - single}")

    print("\nSample chunks (first 3):")
    for i, chunk in enumerate(chunks[:3], 1):
        tokens = len(_tokenizer.encode(chunk["text"]))
        preview = chunk["text"][:150] + "..." if len(chunk["text"]) > 150 else chunk["text"]
        print(f"\n  Chunk {i} ({tokens} tokens, pages {chunk['page_numbers']}):")
        print(f"    {preview}")

    print("\nChunking test completed successfully.")


if __name__ == "__main__":
    main()
