## RAG

## We start by chunking
## Settig up the environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

## Chunking data
DATA_DIR=data/docs python -m ingestion.cli.chunk_dir --fresh

## Chunking database tables
python -m ingestion.cli.chunk_db --fresh

## Then we fire up the API to handle queries
### Using Docker Compose (Recommended)

```bash
docker-compose up -d
```


Better model options (if you have more resources):
- google/flan-t5-large - Good balance of quality and speed
- mistralai/Mistral-7B-Instruct-v0.1 - Higher quality but slower

# Only search database-indexed content
curl -X POST http://localhost:5000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many jobs were marked closed in 2025", "data_source": "db"}'

# Only search documents (PDFs)
curl -X POST http://localhost:5000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the ISO 17025 nonconformance procedure?", "data_source": "docs"}'
