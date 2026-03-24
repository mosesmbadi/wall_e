"""OpenSearch search and RAG answer pipeline."""
from __future__ import annotations

from core.config import MIN_RELEVANCE_SCORE, INDEX_NAMES
from core.docs import resolve_search_index
from core.opensearch import get_client
from core.embeddings import get_model
from api.catalog import infer_doc_filter_from_question
from api.llm import generate_answer

_default_index = resolve_search_index(INDEX_NAMES)
print(f"Default search index/indices: {_default_index}")


# Maps the user-facing data_source value to the source_type values stored in OpenSearch
_DATA_SOURCE_TYPES: dict[str, list[str]] = {
    "db":   ["db", "csv"],
    "docs": ["pdf"],
}


def search(
    query: str,
    k: int = 10,
    use_hybrid: bool = True,
    doc_filter: dict | None = None,
    data_source: str | None = None,
    index: str | None = None,
) -> list[dict]:
    query_vector = get_model().encode(query).tolist()

    if use_hybrid:
        base_query: dict = {
            "bool": {
                "should": [
                    {"knn": {"content_vector": {"vector": query_vector, "k": k}}},
                    {"match": {"text": {"query": query, "boost": 0.5}}},
                ]
            }
        }
    else:
        base_query = {"knn": {"content_vector": {"vector": query_vector, "k": k}}}

    filter_clauses = []
    if doc_filter:
        for field in ("doc_name", "doc_type", "source_file"):
            if field in doc_filter:
                filter_clauses.append({"term": {field: doc_filter[field]}})
    if data_source and data_source in _DATA_SOURCE_TYPES:
        filter_clauses.append({"terms": {"source_type": _DATA_SOURCE_TYPES[data_source]}})
    if filter_clauses:
        if use_hybrid:
            base_query["bool"]["filter"] = filter_clauses
        else:
            base_query = {"bool": {"must": [base_query], "filter": filter_clauses}}

    target_index = index or _default_index
    try:
        response = get_client().search(
            index=target_index,
            body={"size": k, "query": base_query},
            params={"ignore_unavailable": "true"},
        )
        results = []
        for hit in response["hits"]["hits"]:
            result = {"text": hit["_source"]["text"], "score": hit["_score"]}
            for field in ("doc_name", "doc_type", "source_file", "source_type", "table_name"):
                if field in hit["_source"]:
                    result[field] = hit["_source"][field]
            results.append(result)
        return results
    except Exception as e:
        print(f"Error searching index '{target_index}': {e}")
        return []


def answer_question(
    question: str,
    k: int = 10,
    use_llm: bool = True,
    doc_filter: dict | None = None,
    data_source: str | None = None,
    history: list[dict] | None = None,
    min_score: float | None = None,
    index: str | None = None,
) -> dict:
    threshold = min_score if min_score is not None else MIN_RELEVANCE_SCORE

    search_query = question
    if history:
        last_user = next(
            (t["content"] for t in reversed(history) if t.get("role") == "user"), None
        )
        if last_user and last_user.strip() != question.strip():
            search_query = f"{last_user} {question}"

    effective_filter = doc_filter or infer_doc_filter_from_question(question)
    results = search(search_query, k, doc_filter=effective_filter, data_source=data_source, index=index)
    if not results and effective_filter:
        results = search(search_query, k, doc_filter=None, data_source=data_source, index=index)

    results = [r for r in results if r["score"] >= threshold]

    if not results:
        return {
            "answer": "I could not find relevant information in the documents to answer that question.",
            "sources": [],
        }

    if use_llm:
        answer_text = generate_answer(question, results[:8], history=history)
    else:
        answer_text = "\n\n".join(
            f"[Relevance: {r['score']:.2f}]\n{r['text']}" for r in results
        )

    return {"answer": answer_text, "sources": results, "doc_filter": effective_filter, "data_source": data_source}
