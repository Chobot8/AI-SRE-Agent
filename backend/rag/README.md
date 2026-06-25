# Runbook knowledge base + RAG (KAN-4)

Grounds the agent's recommendations in operational knowledge instead of relying on
raw model output. Source runbooks are chunked, embedded, and stored in a
rebuildable vector index; retrieval returns the most relevant chunks for an
incident, each with a citation.

## Pipeline

```
knowledge/runbooks/*.md
        │  chunk_markdown()         (heading-scoped chunks)
        ▼
     Chunk[]  ──embed()──►  VectorStore   ──save()──►  data/rag/index.json
                                  ▲                         (generated, gitignored)
   query / incident ──embed()─────┘  search(top-k, cosine)  ──►  RetrievedChunk[] (+citations)
```

## Components

| Module | Responsibility |
| ------ | -------------- |
| `embeddings.py` | `Embedder` interface; `HashingEmbedder` (deterministic, no deps); `OpenAIEmbedder` placeholder |
| `chunking.py` | Split Markdown into heading-scoped chunks |
| `vector_store.py` | In-memory vectors + cosine search + JSON save/load |
| `index.py` | `build_index()` — rebuild the store from source runbooks |
| `retriever.py` | `Retriever.retrieve()`, `query_from_incident()`, `format_grounded_answer()` |

## Embeddings

The default `HashingEmbedder` uses deterministic feature hashing (stdlib only), so
the index builds and queries locally with **no model download or API key**, and a
rebuild reproduces the same vectors. To use real embeddings, implement
`OpenAIEmbedder.embed` (or add a sentence-transformers embedder) against the
`Embedder` interface and pass it to `build_index(embedder=...)` — nothing else
changes.

## Usage

```bash
python -m backend.rag build                 # build + save the index
python -m backend.rag query "p99 latency slo orders-db slow query"
python -m backend.rag incident high_latency # retrieve for a sample incident
```

`format_grounded_answer(answer, retrieved)` appends a numbered **References**
section citing each retrieved chunk as `[source.md > Heading]`, so downstream
answers (KAN-5) always show the operational context they relied on.

## Rebuilding

The index under `data/rag/` is derived data and git-ignored. Rebuild any time
with `python -m backend.rag build` or `build_index(save_to=...)`.
