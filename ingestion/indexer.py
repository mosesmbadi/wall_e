from __future__ import annotations
from opensearchpy import helpers
from core.config import BATCH_SIZE
from core.opensearch import get_client
from core.embeddings import get_model

INDEX_BODY = {
    "settings": {
        "index.knn": True,
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "content_vector": {
                "type": "knn_vector",
                "dimension": 384,
                "method": {
                    "name": "hnsw",
                    "space_type": "l2",
                    "engine": "lucene",
                },
            },
            "text":         {"type": "text"},
            "doc_name":     {"type": "keyword"},
            "doc_type":     {"type": "keyword"},
            "source_type":  {"type": "keyword"},
            "table_name":   {"type": "keyword"},
            "chunk_index":  {"type": "integer"},
            "source_file":  {"type": "keyword"},
            "page_numbers": {"type": "keyword"},
            "start_page":   {"type": "integer"},
            "end_page":     {"type": "integer"},
        }
    },
}


def ensure_index(index_name: str, fresh: bool = False) -> None:
    client = get_client()
    try:
        exists = client.indices.exists(index=index_name)
        if exists and fresh:
            print(f"Deleting existing index '{index_name}' (--fresh)...")
            client.indices.delete(index=index_name)
            exists = False
        if exists:
            print(f"Index '{index_name}' already exists. Using existing index.")
        else:
            print(f"Creating index '{index_name}'...")
            client.indices.create(index=index_name, body=INDEX_BODY)
            print("Index created.")
    except Exception as e:
        print(f"Warning: could not create index ({e}). Will attempt auto-creation on first insert.")


def bulk_index(chunks: list[dict], index_name: str, start_id: int = 0) -> int:
    """Embed and bulk-insert chunks into OpenSearch. Returns number of docs indexed."""
    client = get_client()
    model = get_model()
    total = len(chunks)
    doc_id = start_id

    for start in range(0, total, BATCH_SIZE):
        batch = chunks[start:start + BATCH_SIZE]
        texts = [c["text"] for c in batch]
        vectors = model.encode(texts, batch_size=BATCH_SIZE).tolist()

        actions = [
            {
                "_index": index_name,
                "_id": str(doc_id + offset),
                "_source": {
                    "text":           chunk["text"],
                    "content_vector": vector,
                    "doc_name":       chunk.get("doc_name", ""),
                    "doc_type":       chunk.get("doc_type", ""),
                    "source_type":    chunk.get("source_type", ""),
                    "table_name":     chunk.get("table_name", ""),
                    "chunk_index":    chunk.get("chunk_index", 0),
                    "source_file":    chunk.get("source_file", ""),
                    "page_numbers":   chunk.get("page_numbers", ""),
                    "start_page":     chunk.get("start_page", 0),
                    "end_page":       chunk.get("end_page", 0),
                },
            }
            for offset, (chunk, vector) in enumerate(zip(batch, vectors))
        ]
        helpers.bulk(client, actions)
        doc_id += len(actions)

    return total
