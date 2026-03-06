import os

from flask import Flask, request, jsonify

from api.catalog import DOCUMENT_CATALOG
from api.search import answer_question, search

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

    result = answer_question(
        question,
        k=int(data.get("k", 10)),
        use_llm=bool(data.get("use_llm", True)),
        doc_filter=data.get("doc_filter") or None,
        history=data.get("history") or None,
        min_score=float(data["min_score"]) if "min_score" in data else None,
        index=data.get("index") or None,
    )
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


@app.route("/catalog", methods=["GET"])
def catalog():
    return jsonify({"documents": DOCUMENT_CATALOG})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
