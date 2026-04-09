# Wall-E — System Architecture

## Overview

Wall-E is a **Hybrid RAG (Retrieval-Augmented Generation)** system that answers natural-language questions about laboratory data by combining semantic vector search, keyword search, and LLM-generated SQL over multiple data sources.

---

## High-Level Architecture

```mermaid
graph TB
    subgraph Client
        U([User / API Client])
    end

    subgraph API["API Layer - Flask Port 5000"]
        R[query endpoint]
        S[search endpoint]
        SQL[sql endpoint]
        CAT[catalog endpoint]
        ROUTER{Intent Router}
        R --> ROUTER
    end

    subgraph RAG["RAG Pipeline"]
        SEARCH["search.py - Hybrid Search + Answer"]
        LLM["llm.py - Answer Synthesis"]
        SEARCH --> LLM
    end

    subgraph SQL_PIPE["SQL Pipeline"]
        SQLGEN["sql_query.py - Text-to-SQL"]
        DBPICK["DB Router - Keyword Scoring"]
        SAFECHK["Safety Check - Read-only Guard"]
        SQLGEN --> DBPICK
        DBPICK --> SAFECHK
    end

    subgraph LLM_BACKEND["LLM Backends"]
        GEMINI["Google Gemini - gemini-1.5-flash"]
        LOCAL["TinyLlama 1.1B - Local CPU"]
    end

    subgraph SEARCH_BACKEND["Search Backend"]
        OS[("OpenSearch - Port 9200")]
        DASH["OpenSearch Dashboards - Port 5601"]
    end

    subgraph DATA_SOURCES["Data Sources"]
        PG[("PostgreSQL Databases")]
        FILES["PDF + CSV Files - data/docs"]
        SCHEMAS["Schema Annotations - .schema.md"]
    end

    U -->|HTTP POST| R
    U -->|HTTP POST| S
    U -->|HTTP POST| SQL
    U -->|HTTP GET| CAT

    ROUTER -->|Semantic question| SEARCH
    ROUTER -->|Aggregation / count / sum| SQLGEN
    S --> SEARCH
    SQL --> SQLGEN

    SEARCH --> OS
    SQLGEN --> PG
    SQLGEN --> SCHEMAS

    LLM -->|Primary| GEMINI
    LLM -->|Fallback| LOCAL

    DASH -.->|Monitor| OS
```

---

## Ingestion Pipeline

```mermaid
flowchart LR
    subgraph Sources["Source Data"]
        PDF[PDF Files]
        CSV[CSV Files]
        DB[(PostgreSQL)]
    end

    subgraph chunk_dir["chunk_dir CLI - File Ingestion"]
        FK1["Build FK Lookup Tables"]
        SCHEMA1["Generate Schema Document"]
        PDFCHUNK["PDF Chunker - Page-Aware"]
        CSVCHUNK["CSV Chunker - FK Resolution"]
    end

    subgraph chunk_db["chunk_db CLI - DB Ingestion"]
        INTROSPECT["Schema Introspection"]
        SCHEMA2["Generate Schema Document"]
        STREAM["Stream Rows - Server-Side Cursor"]
        DBCHUNK["DB Chunker - FK Resolution"]
    end

    subgraph Processing["Shared Processing"]
        EMBED["Embeddings - all-MiniLM-L6-v2 - 384-dim"]
        BULK[Bulk Indexer]
    end

    subgraph Index["OpenSearch Index"]
        IDX[("KNN Index - HNSW L2")]
    end

    PDF --> PDFCHUNK
    CSV --> FK1 --> CSVCHUNK
    CSV --> SCHEMA1

    DB --> INTROSPECT --> SCHEMA2
    DB --> STREAM --> DBCHUNK

    PDFCHUNK --> EMBED
    CSVCHUNK --> EMBED
    SCHEMA1 --> EMBED
    SCHEMA2 --> EMBED
    DBCHUNK --> EMBED

    EMBED --> BULK --> IDX
```

---

## Query Pipeline

```mermaid
sequenceDiagram
    actor User
    participant API as app.py
    participant Catalog as catalog.py
    participant Search as search.py
    participant SQL as sql_query.py
    participant OS as OpenSearch
    participant PG as PostgreSQL
    participant LLM as llm.py

    User->>API: POST /query { question, data_source? }

    API->>Catalog: infer_doc_filter_from_question()
    Catalog-->>API: doc_filter (optional)

    alt Aggregation / count / sum question
        API->>SQL: answer_with_sql(question, db_name?)
        SQL->>SQL: _pick_database() via keyword scoring
        SQL->>LLM: generate SQL from schema annotation
        LLM-->>SQL: SELECT ...
        SQL->>SQL: _is_safe_select() guard
        SQL->>PG: Execute read-only query
        PG-->>SQL: Result rows
        SQL->>LLM: Narrate results
        LLM-->>SQL: Natural language answer
        SQL-->>API: { answer, sql }
    else Semantic / document question
        API->>Search: answer_question(question, doc_filter?)
        Search->>OS: KNN vector search (k=10)
        Search->>OS: Keyword BM25 search
        OS-->>Search: Ranked chunks
        Search->>Search: Filter by score >= 0.5
        Search->>LLM: Synthesize answer from top-8 chunks
        LLM-->>Search: Answer with citations
        Search-->>API: { answer, sources }
    end

    API-->>User: JSON response
```

---

## Component Map

```mermaid
graph LR
    subgraph core["core/"]
        CFG["config.py - Env Config"]
        EMB["embeddings.py - Sentence-Transformers"]
        OC["opensearch.py - Client Singleton"]
        DC["docs.py - Domain Helpers"]
    end

    subgraph ingestion["ingestion/"]
        IDX["indexer.py - Bulk Index"]
        SCH["schema.py - FK Resolution"]
        CPDF["chunkers/pdf.py"]
        CCSV["chunkers/csv.py"]
        CDB["chunkers/db.py"]
        CTAB["chunkers/tabular.py"]
        CDIR["cli/chunk_dir.py"]
        CDBD["cli/chunk_db.py"]
    end

    subgraph api["api/"]
        APP["app.py"]
        SR["search.py"]
        LM["llm.py"]
        SQ["sql_query.py"]
        CT["catalog.py"]
    end

    CFG --> EMB
    CFG --> OC
    CFG --> IDX
    EMB --> IDX
    OC --> IDX
    OC --> SR

    SCH --> CCSV
    SCH --> CDB
    CTAB --> CCSV
    CTAB --> CDB

    IDX --> CDIR
    IDX --> CDBD
    SCH --> CDIR
    SCH --> CDBD
    CPDF --> CDIR
    CCSV --> CDIR
    CDB --> CDBD
    DC --> CDIR

    SR --> APP
    SQ --> APP
    CT --> APP
    LM --> SR
    LM --> SQ
    EMB --> SR
```

---

## Docker Infrastructure

```mermaid
graph TB
    subgraph Host["Host Machine"]
        subgraph DC["Docker Compose Network - opensearch-net"]
            subgraph RAG_SVC["rag service - 2 CPU / 6 GB"]
                FLASK["Flask App - Port 5000"]
                LLMR["TinyLlama - Local Inference"]
            end

            subgraph OS_SVC["opensearch - 512 MB to 2 GB heap"]
                OSN["OpenSearch Node - Port 9200"]
                KV["opensearch-data volume"]
            end

            subgraph DASH_SVC["opensearch-dashboards - 0.5 CPU / 1 GB"]
                DBUI["Dashboards UI - Port 5601"]
            end
        end

        CLI["Ingestion CLI - chunk_dir / chunk_db"]
        DATA["./data/ - Read-Only Mount"]
    end

    EXT_GEMINI["Google Gemini API"]
    EXT_PG[("External PostgreSQL")]

    FLASK -->|HTTPS| OSN
    DBUI -->|HTTPS| OSN
    OSN --- KV
    FLASK -->|HTTPS| EXT_GEMINI
    FLASK -->|psycopg2| EXT_PG
    CLI -->|Bulk index| OSN
    CLI --- DATA
    DATA -->|Volume mount| FLASK
```

---

## Data Model (OpenSearch Document)

Each indexed chunk stored in OpenSearch contains:

| Field | Type | Description |
|---|---|---|
| `text` | keyword + text | Raw chunk content |
| `content_vector` | knn_vector (384-dim) | Sentence embedding |
| `doc_name` | keyword | Source document name |
| `doc_type` | keyword | `Service Manual`, `User Manual`, `Document` |
| `source_type` | keyword | `pdf`, `csv`, `db` |
| `table_name` | keyword | CSV/DB table name |
| `start_page` / `end_page` | integer | PDF page range |
| `start_row` / `end_row` | integer | CSV/DB row range |
| `db_name` | keyword | Source database name |

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Vector index | OpenSearch HNSW (L2) | Combines KNN + keyword in one store |
| Embedding model | `all-MiniLM-L6-v2` (384-dim) | Lightweight, CPU-friendly |
| Primary LLM | Google Gemini 1.5 Flash | Quality + speed |
| Fallback LLM | TinyLlama 1.1B | Offline / no-API-key operation |
| SQL safety | Forbidden-keyword blocklist + read-only transactions | Prevent data mutation |
| Chunking | 300–500 tokens, 50-token overlap | Balances context and precision |
| SQL routing | Regex pattern matching on question | Fast, no LLM needed to route |
| FK resolution | Inline expansion at chunk time | Improves recall and LLM comprehension |
