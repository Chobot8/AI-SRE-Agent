# Runbook knowledge base + RAG (KAN-4, extended by KAN-21)

Grounds the agent's recommendations in operational knowledge instead of relying on
raw model output. Source runbooks (and, optionally, scenario-pack snippets) are
chunked with metadata, embedded, and stored behind a swappable `RetrievalBackend`
interface. Retrieval returns the most relevant chunks for an incident, filterable
by metadata, each with a structured citation.

## Pipeline

```
knowledge/runbooks/*.md
scenarios/<slug>/runbook.md (optional)
        │  chunk_markdown() / chunk_file()   (heading-scoped chunks + metadata)
        ▼
     Chunk[]  ──index_documents()──►  RetrievalBackend   ──save()──►  data/rag/index.json
                                            ▲                            (generated, gitignored)
   query / incident ──search(query, filters, k)──┘  ──►  RetrievedChunk[] (+structured Citation)
```

## Components

| Module | Responsibility |
| ------ | -------------- |
| `embeddings.py` | `Embedder` interface; `HashingEmbedder` (deterministic, no deps); `OpenAIEmbedder` placeholder |
| `chunking.py` | Split Markdown into heading-scoped chunks, tagged with metadata |
| `models.py` | `DocumentMetadata`, `RetrievalFilters`, `Chunk`, `Citation`, `RetrievedChunk` |
| `vector_store.py` | In-memory vectors + cosine search (filterable) + JSON save/load |
| `backend.py` | `RetrievalBackend` interface + `KeywordVectorBackend` (default) + planned backends |
| `index.py` | `build_index()` — rebuild the store from source runbooks (+ optional scenario packs) |
| `retriever.py` | `Retriever.retrieve()`, `query_from_incident()`, `citations_for()`, `format_grounded_answer()` |

## Retrieval interface

Retrieval is designed behind an interface so the storage/search engine can be
swapped without touching callers (`backend/analysis/pipeline.py`, `backend/api`):

```python
class RetrievalBackend(ABC):
    def index_documents(self, documents: list[Chunk]) -> None: ...
    def search(self, query: str, filters: RetrievalFilters | None = None, k: int = 3) -> list[RetrievedChunk]: ...
```

`Retriever` (in `retriever.py`) is the higher-level façade the analysis pipeline
uses; it wraps a `VectorStore`/backend and adds incident-shaped convenience
methods (`retrieve_for_incident`, `filters_from_incident`).

## Selected backend and trade-offs

The default and only *implemented* backend is **`KeywordVectorBackend`**
(`backend.py`) — an in-memory cosine-similarity search over deterministic
feature-hashed embeddings (`HashingEmbedder`). It was chosen for the MVP because:

* **Zero dependencies, zero setup.** No vector DB, no API key, no model download —
  `python -m backend.rag build` works offline and in CI.
* **Deterministic and reproducible.** The same runbooks always produce the same
  index, which keeps the acceptance/evaluation tests (`tests/test_evaluation.py`)
  stable.
* **Right-sized for the corpus.** At dozens–hundreds of chunks, brute-force cosine
  search over an in-memory list is fast enough that a dedicated ANN index would
  add operational surface without a measurable latency win.

The trade-off: it doesn't scale past a few thousand chunks, has no persistence
beyond a flat JSON file, and the hashed embeddings are a bag-of-features
proxy rather than a learned semantic embedding, so recall on paraphrased or
out-of-vocabulary queries is weaker than a real embedding model would give.

Three swappable backends are defined but intentionally **not implemented** yet
(`backend.py`, each raises `NotImplementedError` with what it needs):

| Backend | When to reach for it | What it needs |
| ------- | --------------------- | -------------- |
| `ChromaRetrievalBackend` | Fast local semantic search, richer metadata filtering, still no server to run | `chromadb` package + a persistent collection |
| `FaissRetrievalBackend` | Larger corpora, need ANN speed, comfortable managing an index file yourself | `faiss-cpu` package + an on-disk/in-memory index file |
| `PgVectorRetrievalBackend` | Retrieval should live next to the rest of the app's data in Postgres | `vector` Postgres extension, a schema migration, `pgvector` Python package |

Every real backend implements the same `RetrievalBackend` interface, so swapping
one in is a constructor change at the call site, not a rewrite of `retriever.py`
or the analysis pipeline.

### Open question: pgvector now, or Chroma/FAISS for faster local setup?

**Decision: keep `KeywordVectorBackend` for the MVP; target `pgvector` when a
real backend is implemented**, not Chroma/FAISS. PostgreSQL is already being
added to this project (`infra/db/schema.sql`), and the `retrieved_chunks` table
already has a `metadata jsonb` column plus a commented-out
`embedding vector(1536)` column reserved for exactly this migration — so
`pgvector` avoids standing up a second datastore purely for retrieval and keeps
citations, incident history, and vectors queryable together. `PgVectorRetrievalBackend`'s
docstring documents that reserved column and the exact migration shape. Chroma/FAISS
remain documented options if a future need (e.g. fully offline / non-Postgres
deployment) calls for them.

### Open question: should incident history be retrievable, or only static runbooks?

**Decision: static runbooks only for the MVP**, with the design left open to add
incident history later without an interface change. Concretely:

* `Chunk.metadata["document_type"]` already distinguishes `"runbook"` (from
  `knowledge/runbooks/*.md`) from `"runbook_snippet"` (from `scenarios/*/runbook.md`,
  opt-in via `build_index(include_scenario_packs=True)`) — a third value such as
  `"incident_history"` can be added later with no interface change.
  `RetrievalFilters(document_type=...)` already supports filtering it out or in.
* Past incidents/diagnoses aren't yet indexed as retrievable documents because
  there's no ground truth yet for whether surfacing a *previous diagnosis* (as
  opposed to a runbook) improves precision, and it risks grounding new diagnoses
  in a possibly-wrong past guess rather than vetted operational knowledge.
* The `retrieved_chunks` table (already persisting citations per KAN-16) is the
  natural future source for this: once enough diagnoses are stored, indexing
  their high-confidence chunks as `document_type="incident_history"` is a
  data-layer change, not a retrieval-interface change.

## Metadata and filtering

Every chunk carries metadata (`DocumentMetadata` / `Chunk.metadata`):
`service`, `incident_type`, `severity`, `environment`, `document_type`, `source`.
Runbooks are tagged by filename/stem; scenario-pack snippets are tagged from the
pack's own `alert.json`/`expected.yaml`.

`RetrievalFilters(service=..., incident_type=..., severity=..., environment=...,
document_type=..., source=...)` narrows `search()`/`retrieve()` results. A `None`
filter field is a wildcard; a chunk with no value for a given field (e.g. a
generic knowledge-base runbook with no `service`) still matches any filter for
that field, so generic runbooks aren't excluded by a service-scoped search.
`filters_from_incident(incident)` builds a filter from `service`/`scenario`
automatically. See `tests/test_rag.py` for examples of how filtering removes
cross-type/cross-service intrusions that appear in unfiltered top-k results.

## Citations

`RetrievedChunk.structured_citation` (and `citations_for(hits)`) produce a
`Citation` dataclass (`source`, `heading`, `score`, `document_type`, `service`,
`incident_type`, `severity`, `environment`, `text_snippet`) — `to_dict()` is the
JSON-friendly shape persisted per diagnosis (`IncidentDiagnosis.citations`, the
API's `chunk_metadata` column). `format_grounded_answer(answer, retrieved)` still
appends a human-readable, numbered **References** section citing each chunk as
`[source.md > Heading]` for prose answers.

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

```python
from backend.rag import Retriever, build_index, RetrievalFilters

store = build_index(include_scenario_packs=True)   # opt-in: also index scenario-pack snippets
retriever = Retriever(store)
hits = retriever.retrieve(
    "p99 latency slo orders-db slow query",
    filters=RetrievalFilters(service="orders-api", incident_type="db_saturation"),
)
```

## Rebuilding

The index under `data/rag/` is derived data and git-ignored. Rebuild any time
with `python -m backend.rag build` or `build_index(save_to=...)`.
