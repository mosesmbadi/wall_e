"""Text-to-SQL pipeline — converts natural language questions to SQL and executes them safely.

Only SELECT queries are allowed. All queries are executed read-only via a dedicated
connection so there is zero risk of data mutation.
"""
from __future__ import annotations

import json
import os
import re

import psycopg2
import psycopg2.extras

from api.llm import generate_answer_with_gemini, _gemini_client
from core.config import MAX_ROWS_PER_TABLE, GEMINI_MODEL


# ── DB connection ─────────────────────────────────────────────────────────────

def _get_db_configs() -> list[dict]:
    raw = os.getenv("DB_CONFIGS", "[]")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def _connect(config: dict):
    return psycopg2.connect(
        host=config["host"],
        port=int(config.get("port", 5432)),
        user=config["user"],
        password=config["password"],
        dbname=config["dbname"],
        connect_timeout=10,
        options="-c default_transaction_read_only=on",  # read-only safety
    )


# ── Schema introspection ──────────────────────────────────────────────────────

def _get_schema_summary(conn) -> str:
    """Build a compact schema string: table(col1, col2, ...) for all public tables."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT
                t.table_name,
                array_agg(c.column_name ORDER BY c.ordinal_position) AS columns
            FROM information_schema.tables t
            JOIN information_schema.columns c
              ON c.table_name = t.table_name AND c.table_schema = t.table_schema
            WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
            GROUP BY t.table_name
            ORDER BY t.table_name
        """)
        rows = cur.fetchall()

    lines = []
    for row in rows:
        cols = ", ".join(row["columns"])
        lines.append(f"  {row['table_name']}({cols})")
    return "\n".join(lines)


# ── Schema annotation ───────────────────────────────────────────────────────

_ANNOTATION_SEARCH_PATHS = [
    # relative to project root (works both locally and in Docker via volume mount)
    os.path.join(os.path.dirname(__file__), "..", "data"),
    "/app/data",
]


def _load_schema_annotation(db_name: str) -> str:
    """
    Look for  data/<db-name>.schema.md  and return its contents.
    Returns an empty string if no annotation file is found.
    """
    filename = f"{db_name}.schema.md"
    for search_dir in _ANNOTATION_SEARCH_PATHS:
        candidate = os.path.normpath(os.path.join(search_dir, filename))
        if os.path.isfile(candidate):
            with open(candidate, "r", encoding="utf-8") as f:
                content = f.read().strip()
            print(f"Loaded schema annotation: {candidate}")
            return content
    return ""


# ── SQL safety guard ──────────────────────────────────────────────────────────

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)

def _is_safe_select(sql: str) -> bool:
    """Return True only if the query is a plain SELECT with no mutation keywords."""
    stripped = sql.strip()
    if not stripped.upper().startswith("SELECT"):
        return False
    if _FORBIDDEN.search(stripped):
        return False
    return True


# ── SQL extraction from LLM response ─────────────────────────────────────────

def _extract_sql(text: str) -> str | None:
    """Pull the first SQL block out of an LLM response."""
    # Try fenced code block first: ```sql ... ``` or ``` ... ```
    match = re.search(r"```(?:sql)?\s*(SELECT[\s\S]+?)```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Fallback: find a bare SELECT statement
    match = re.search(r"(SELECT\s[\s\S]+?;)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Last resort: find SELECT to end of string
    match = re.search(r"(SELECT\s[\s\S]+)$", text.strip(), re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


# ── LLM SQL generation ────────────────────────────────────────────────────────

def _generate_sql(question: str, schema: str, db_name: str, annotation: str = "") -> str | None:
    """Ask the LLM to produce a SQL SELECT for the question given the schema."""
    from google import genai  # type: ignore

    if not _gemini_client:
        return None

    annotation_block = ""
    if annotation:
        annotation_block = f"""
## Business context & relationships
{annotation}
"""

    prompt = f"""You are an expert PostgreSQL query writer. Given the database schema below,
write a single read-only SELECT query that answers the user's question.

Database: {db_name}
{annotation_block}
## Raw schema (table → columns)
{schema}

Rules:
- Output ONLY the SQL query, wrapped in a ```sql code block.
- Use only SELECT. Never use INSERT, UPDATE, DELETE, DROP, or any mutation.
- Use table and column names exactly as shown in the schema.
- For date filtering, use the EXTRACT() or date_trunc() functions.
- Prefer JOINs over subqueries for readability.
- If you cannot answer with a single SELECT query, output: CANNOT_ANSWER

Question: {question}
"""
    try:
        response = _gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        raw = response.text.strip()
        if "CANNOT_ANSWER" in raw:
            return None
        return _extract_sql(raw)
    except Exception as e:
        print(f"SQL generation error: {e}")
        return None


# ── Result formatting ─────────────────────────────────────────────────────────

def _format_results(rows: list[dict], columns: list[str]) -> str:
    """Format SQL result rows into a readable text block for the LLM."""
    if not rows:
        return "The query returned no results."
    if len(rows) == 1 and len(columns) == 1:
        # Single scalar result (e.g. COUNT)
        return str(list(rows[0].values())[0])
    lines = [", ".join(columns)]
    for row in rows[:50]:  # cap at 50 rows for LLM context
        lines.append(", ".join(str(v) for v in row.values()))
    suffix = f"\n... ({len(rows)} total rows)" if len(rows) > 50 else ""
    return "\n".join(lines) + suffix


# ── DB routing ────────────────────────────────────────────────────────────────

def _pick_database(question: str, configs: list[dict]) -> dict:
    """
    When no db_name is specified and multiple DBs are configured, score each
    database by counting how many words from the question appear in that DB's
    annotation file. Picks the highest-scoring DB with zero LLM calls.
    Falls back to the first config on a tie or if no annotations exist.
    """
    if len(configs) == 1:
        return configs[0]

    # Tokenise the question into lowercase words (3+ chars to avoid noise)
    question_words = set(w.lower() for w in re.findall(r"[a-z]{3,}", question.lower()))

    best_config = configs[0]
    best_score = -1

    for cfg in configs:
        annotation = _load_schema_annotation(cfg["dbname"])
        if not annotation:
            continue
        annotation_lower = annotation.lower()
        score = sum(1 for w in question_words if w in annotation_lower)
        print(f"DB router score — {cfg['name']}: {score}")
        if score > best_score:
            best_score = score
            best_config = cfg

    print(f"DB router selected: {best_config['name']}")
    return best_config


# ── Public entry point ────────────────────────────────────────────────────────

def answer_with_sql(question: str, db_name: str | None = None) -> dict:
    """
    Generate SQL from the question, execute it, then ask the LLM to
    narrate the results. Returns a dict with 'answer' and 'sql' keys.
    """
    configs = _get_db_configs()
    if not configs:
        return {"answer": "No database is configured.", "sql": None}

    # Pick the requested DB, or auto-route using annotations if multiple DBs exist
    if db_name:
        config = next((c for c in configs if c.get("name") == db_name), configs[0])
    else:
        config = _pick_database(question, configs)

    try:
        conn = _connect(config)
    except Exception as e:
        return {"answer": f"Could not connect to database: {e}", "sql": None}

    try:
        schema = _get_schema_summary(conn)
        annotation = _load_schema_annotation(config["dbname"])
        sql = _generate_sql(question, schema, config["dbname"], annotation=annotation)

        print(f"Generated SQL:\n{sql}")

        if not sql or not _is_safe_select(sql):
            return {
                "answer": "I could not generate a safe SQL query for that question.",
                "sql": sql,
            }

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = [dict(r) for r in cur.fetchmany(MAX_ROWS_PER_TABLE)]
            columns = [desc[0] for desc in cur.description]

        result_text = _format_results(rows, columns)

        # Ask LLM to narrate the raw result in plain English
        narrative_prompt = f"The user asked: \"{question}\"\n\nSQL result:\n{result_text}\n\nSummarise the result in one or two clear sentences."
        answer = generate_answer_with_gemini(narrative_prompt, [])

        return {"answer": answer, "sql": sql}

    except psycopg2.Error as e:
        return {"answer": f"Database query failed: {e}", "sql": sql if 'sql' in dir() else None}
    finally:
        conn.close()
