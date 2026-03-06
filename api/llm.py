"""LLM integration — Gemini API and local HuggingFace fallback."""
from __future__ import annotations
from core.config import (
    LLM_PROVIDER, GEMINI_API_KEY, GEMINI_MODEL,
    LLM_MODEL, MAX_ANSWER_LENGTH,
)

# ── Gemini ────────────────────────────────────────────────────────────────────

_gemini_client = None
_active_provider = LLM_PROVIDER

if LLM_PROVIDER == "gemini":
    try:
        from google import genai  # type: ignore
        if GEMINI_API_KEY:
            _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            print(f"Using Gemini API ({GEMINI_MODEL})")
        else:
            print("Warning: GEMINI_API_KEY not set in .env file")
            _active_provider = "local"
    except ImportError:
        print("Warning: google-genai not installed. Install with: pip install google-genai")
        _active_provider = "local"


def _build_history_block(history: list[dict] | None, max_turns: int = 6) -> str:
    if not history:
        return ""
    turns = []
    for turn in history[-max_turns:]:
        role = "User" if turn.get("role") == "user" else "Assistant"
        turns.append(f"{role}: {turn.get('content', '').strip()}")
    return "Conversation so far:\n" + "\n".join(turns) + "\n\n" if turns else ""


def generate_answer_with_gemini(
    question: str, context_chunks: list[dict], history: list[dict] | None = None
) -> str:
    if not _gemini_client:
        return "Gemini API not configured. Please set GEMINI_API_KEY in .env file."

    context_parts = []
    for i, chunk in enumerate(context_chunks[:8], 1):
        source_label = chunk.get("table_name") or chunk.get("doc_name", "")
        source_type = chunk.get("source_type", "unknown")
        context_parts.append(
            f"[Context {i} | source: {source_label} ({source_type})]:\n{chunk['text']}"
        )
    context = "\n\n".join(context_parts)
    history_block = _build_history_block(history)

    prompt = f"""You are a helpful assistant answering questions about laboratory data and documents.

{history_block}The context below contains relevant information retrieved for the current question.
The context may contain data from multiple related database tables or documents.
Foreign key columns (ending in _id) link records across tables. Resolved names
(ending in _name) show the human-readable value for those foreign keys.

Context:
{context}

Current question: {question}

Instructions:
- Use the conversation history to understand references to prior answers (e.g. "that program", "those labs")
- Extract and synthesize relevant information from the context
- Cross-reference data from different tables when answering
- If you find the answer in the context, provide it clearly and completely
- If information is incomplete, state what is available
- Do not add information not in the context

Answer:"""

    try:
        from google.genai import types  # type: ignore  # noqa: F401
        response = _gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return response.text
    except Exception as e:
        return f"Error generating answer with Gemini: {e}"


# ── Local LLM ─────────────────────────────────────────────────────────────────

_llm_tokenizer = None
_llm_model = None


def _load_local_llm() -> None:
    global _llm_tokenizer, _llm_model
    if _llm_model is None:
        from transformers import AutoTokenizer, AutoModelForCausalLM  # type: ignore
        print(f"Loading local LLM model: {LLM_MODEL}...")
        _llm_tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL)
        _llm_model = AutoModelForCausalLM.from_pretrained(
            LLM_MODEL, device_map="cpu", low_cpu_mem_usage=True
        )
        print("Local LLM loaded successfully!")


def generate_answer_with_local_llm(
    question: str, context_chunks: list[dict], history: list[dict] | None = None
) -> str:
    _load_local_llm()

    context_parts = []
    for i, chunk in enumerate(context_chunks[:5], 1):
        source_label = chunk.get("table_name") or chunk.get("doc_name", "")
        context_parts.append(f"[Context {i} | source: {source_label}]:\n{chunk['text']}")
    context = "\n\n".join(context_parts)
    history_block = _build_history_block(history, max_turns=4)

    prompt = f"""<|system|>
You are a precise technical assistant. Answer the question using ONLY information from the provided context and conversation history. Do not add any information not present in the context. If the context doesn't contain enough information, say "The provided context does not contain sufficient information to answer this question."</|system|>
<|user|>
{history_block}Context:
{context}

Current question: {question}

Answer based strictly on the context above:</|user|>
<|assistant|>"""

    inputs = _llm_tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
    outputs = _llm_model.generate(
        **inputs,
        max_new_tokens=MAX_ANSWER_LENGTH,
        temperature=0.3,
        do_sample=True,
        top_p=0.9,
        repetition_penalty=1.2,
        pad_token_id=_llm_tokenizer.eos_token_id,
    )
    full_response = _llm_tokenizer.decode(outputs[0], skip_special_tokens=True)
    if "<|assistant|>" in full_response:
        return full_response.split("<|assistant|>")[-1].strip()
    return full_response[len(prompt):].strip()


# ── Dispatch ──────────────────────────────────────────────────────────────────

def generate_answer(
    question: str, context_chunks: list[dict], history: list[dict] | None = None
) -> str:
    if _active_provider == "gemini":
        return generate_answer_with_gemini(question, context_chunks, history=history)
    return generate_answer_with_local_llm(question, context_chunks, history=history)
