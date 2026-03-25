import os

from flask import Flask, request, jsonify

import re

from api.catalog import DOCUMENT_CATALOG
from api.search import answer_question, search
from api.sql_query import answer_with_sql
from core.config import ENVIRONMENT

# Keywords that strongly suggest an aggregation/counting question → route to SQL
_SQL_PATTERN = re.compile(
    r"\b(how many|count|total|sum|average|avg|list all|show all|which .* in \d{4}|how much)",
    re.IGNORECASE,
)

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/query", methods=["POST"])
def query():
    data = request.get_json(force=True)
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "Missing required field: question"}), 400

    data_source = data.get("data_source") or None
    db_name = data.get("db_name") or None
    use_sql = data.get("use_sql", None)  # explicit override

    # Auto-route to SQL:
    #  - always when db_name is explicitly provided (user wants to query a live DB)
    #  - or when data_source=db + question looks like an aggregation
    if use_sql is None:
        use_sql = bool(db_name) or (data_source == "db" and bool(_SQL_PATTERN.search(question)))

    if use_sql:
        result = answer_with_sql(question, db_name=db_name)
        if ENVIRONMENT.lower() == "production":
            return jsonify({"answer": result["answer"]})
        return jsonify(result)

    result = answer_question(
        question,
        k=int(data.get("k", 10)),
        use_llm=bool(data.get("use_llm", True)),
        doc_filter=data.get("doc_filter") or None,
        data_source=data_source,
        history=data.get("history") or None,
        min_score=float(data["min_score"]) if "min_score" in data else None,
        index=data.get("index") or None,
    )

    if ENVIRONMENT.lower() == "production":
        return jsonify({"answer": result["answer"]})

    return jsonify(result)


@app.route("/search", methods=["POST"])
def search_route():
    data = request.get_json(force=True)
    query_text = data.get("query", "").strip()
    if not query_text:
        return jsonify({"error": "Missing required field: query"}), 400

    results = search(
        query_text,
        k=int(data.get("k", 10)),
        use_hybrid=bool(data.get("use_hybrid", True)),
        doc_filter=data.get("doc_filter") or None,
        index=data.get("index") or None,
    )
    return jsonify({"results": results})


@app.route("/sql", methods=["POST"])
def sql_route():
    data = request.get_json(force=True)
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "Missing required field: question"}), 400
    result = answer_with_sql(question, db_name=data.get("db_name") or None)
    if ENVIRONMENT.lower() == "production":
        return jsonify({"answer": result["answer"]})
    return jsonify(result)


@app.route("/catalog", methods=["GET"])
def catalog():
    return jsonify({"documents": DOCUMENT_CATALOG})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
