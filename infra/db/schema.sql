-- =====================================================================
-- AI SRE Agent — PostgreSQL persistence model (KAN-15)
-- =====================================================================
-- One complete incident-investigation lifecycle: intake -> agent runs ->
-- evidence + retrieved context -> diagnosis -> hypotheses -> recommendations,
-- plus scenario-based evaluation runs.
--
-- Design choices (see docs/data-model.md for the rationale):
--   * Multi-tenant: every tenant-owned row carries org_id (FK -> organizations),
--     ready for PostgreSQL row-level security.
--   * Vectors by reference: retrieved_chunks stores citation text + an external
--     vector-store id only. No embedding column yet — pgvector is a later step.
--   * No secrets at rest: only references/redacted summaries of raw payloads are
--     stored; see the redaction policy in docs/data-model.md.
--   * Replay/review: incidents.intake_source = 'replay' + replay_of_incident_id,
--     and the full run/diagnosis/hypothesis/recommendation chain is keyed to the
--     incident, so any past investigation can be reconstructed.
--
-- This file is idempotent enough for a local Docker Compose Postgres init mount.
-- Target: PostgreSQL 15+.
-- =====================================================================

BEGIN;

-- gen_random_uuid() lives in pgcrypto on PG13; native on PG18+. Safe to request.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- When pgvector is added (see open question #2), uncomment:
--   CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS sre;
SET search_path TO sre, public;

-- ---------------------------------------------------------------------
-- Reusable updated_at trigger
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION sre.set_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- 0. Tenancy root
-- =====================================================================
CREATE TABLE IF NOT EXISTS organizations (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug         text NOT NULL UNIQUE,                 -- url-safe tenant key
    name         text NOT NULL,
    is_active    boolean NOT NULL DEFAULT true,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_organizations_updated
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION sre.set_updated_at();

-- =====================================================================
-- 1. incidents  — one investigation, normalized intake context
-- =====================================================================
CREATE TABLE IF NOT EXISTS incidents (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id               uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Stable human/business key (the NormalizedIncident.id from telemetry).
    external_ref         text,

    -- How the investigation started.
    intake_source        text NOT NULL DEFAULT 'alert'
                          CHECK (intake_source IN ('alert', 'manual', 'replay')),
    is_replay            boolean NOT NULL DEFAULT false,
    replay_of_incident_id uuid REFERENCES incidents(id) ON DELETE SET NULL,

    -- Normalized context (mirrors backend.telemetry.schema.NormalizedIncident).
    scenario             text
                          CHECK (scenario IN ('high_latency','error_rate_spike',
                                 'pod_crash_loop','queue_backlog','db_saturation')),
    service              text NOT NULL,
    environment          text NOT NULL DEFAULT 'local'
                          CHECK (environment IN ('local','staging','production')),
    severity             text NOT NULL DEFAULT 'warning'
                          CHECK (severity IN ('info','warning','critical')),
    title                text NOT NULL,
    summary              text,

    -- Lifecycle status of the investigation itself.
    status               text NOT NULL DEFAULT 'open'
                          CHECK (status IN ('open','investigating','diagnosed',
                                 'resolved','closed')),

    -- Inbound alert (denormalized — the alert that opened the incident).
    alert_source         text,
    alert_summary        text,
    alert_labels         jsonb NOT NULL DEFAULT '{}'::jsonb,  -- redacted; no secrets

    -- Detected symptoms (short tokens, from the analysis layer).
    symptoms             jsonb NOT NULL DEFAULT '[]'::jsonb,

    -- Evaluation ground truth, present only for replayed/sample scenarios.
    expected_root_cause  jsonb,

    -- Pointer to the raw payload in the object/file store. NEVER the raw bytes,
    -- and never secrets — see redaction policy.
    raw_payload_ref      text,

    -- Incident timeline.
    started_at           timestamptz,        -- when the underlying issue began
    detected_at          timestamptz,        -- when the alert fired / intake
    resolved_at          timestamptz,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),

    -- A business key is unique within a tenant (not globally).
    UNIQUE (org_id, external_ref)
);

CREATE INDEX IF NOT EXISTS idx_incidents_org_created   ON incidents (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_org_status    ON incidents (org_id, status);
CREATE INDEX IF NOT EXISTS idx_incidents_org_service   ON incidents (org_id, service);
CREATE INDEX IF NOT EXISTS idx_incidents_replay_of     ON incidents (replay_of_incident_id);

CREATE TRIGGER trg_incidents_updated
    BEFORE UPDATE ON incidents
    FOR EACH ROW EXECUTE FUNCTION sre.set_updated_at();

-- =====================================================================
-- 2. incident_events  — append-only timeline / audit log
-- =====================================================================
CREATE TABLE IF NOT EXISTS incident_events (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    incident_id   uuid NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,

    event_type    text NOT NULL
                  CHECK (event_type IN ('intake','status_change','run_started',
                         'run_completed','evidence_added','diagnosis_added',
                         'recommendation_added','note')),
    -- Free-form, redacted detail for the event (old/new status, message, etc.).
    payload       jsonb NOT NULL DEFAULT '{}'::jsonb,
    -- Who/what produced it: 'system', 'agent', or a user identifier.
    actor         text NOT NULL DEFAULT 'system',
    correlation_id text,

    occurred_at   timestamptz NOT NULL DEFAULT now(),
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_events_incident_time ON incident_events (incident_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_org_type      ON incident_events (org_id, event_type);

-- =====================================================================
-- 3. agent_runs  — one execution of the agent over an incident
-- =====================================================================
CREATE TABLE IF NOT EXISTS agent_runs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    incident_id     uuid NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,

    run_type        text NOT NULL DEFAULT 'full'
                    CHECK (run_type IN ('diagnosis','remediation','full','evaluation')),
    engine          text NOT NULL DEFAULT 'deterministic'
                    CHECK (engine IN ('deterministic','llm')),

    -- Model / provider metadata (placeholders allowed; no API keys ever).
    model_provider  text,                       -- e.g. openai, anthropic
    model_name      text,                       -- e.g. gpt-4o-mini
    prompt_version  text,                       -- e.g. analysis-v3

    status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','running','succeeded','failed')),

    -- Tool calls made during the run: list of
    -- {tool, args_redacted, result_ref, latency_ms, ok}. No secrets in args.
    tool_calls      jsonb NOT NULL DEFAULT '[]'::jsonb,

    -- Cost / performance.
    latency_ms      integer,
    input_tokens    integer,
    output_tokens   integer,
    cost_usd        numeric(10,5),

    -- Error info (redacted message; no payloads/secrets).
    error_type      text,
    error_message   text,

    correlation_id  text,                       -- ties to observability logs (KAN-12)

    started_at      timestamptz,
    finished_at     timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_runs_incident      ON agent_runs (incident_id, created_at);
CREATE INDEX IF NOT EXISTS idx_runs_org_status    ON agent_runs (org_id, status);
CREATE INDEX IF NOT EXISTS idx_runs_correlation   ON agent_runs (correlation_id);

-- =====================================================================
-- 4. evidence_items  — facts gathered during an investigation
-- =====================================================================
CREATE TABLE IF NOT EXISTS evidence_items (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    incident_id   uuid NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    agent_run_id  uuid REFERENCES agent_runs(id) ON DELETE SET NULL,

    kind          text NOT NULL
                  CHECK (kind IN ('log','metric','health_check','runbook',
                         'connector_output')),
    source        text,                          -- e.g. prometheus, loki, grafana
    title         text NOT NULL,
    summary       text,                          -- redacted, human-readable
    -- Structured/extracted value (metric stats, log sample, etc.) — redacted.
    detail        jsonb NOT NULL DEFAULT '{}'::jsonb,
    score         double precision,              -- relevance/severity, when scored
    observed_at   timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_evidence_incident ON evidence_items (incident_id, kind);
CREATE INDEX IF NOT EXISTS idx_evidence_run      ON evidence_items (agent_run_id);

-- =====================================================================
-- 5. retrieved_chunks  — RAG retrievals (vector stored BY REFERENCE only)
-- =====================================================================
CREATE TABLE IF NOT EXISTS retrieved_chunks (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id             uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    incident_id        uuid NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    agent_run_id       uuid REFERENCES agent_runs(id) ON DELETE SET NULL,

    -- Citation fields (mirror backend.rag.models.RetrievedChunk).
    source             text NOT NULL,            -- runbook filename, e.g. high_latency.md
    heading            text,                      -- nearest section heading
    citation           text,                      -- e.g. "[high_latency.md > Remediation]"
    chunk_text         text,                      -- retrieved text, kept for replay/citation
    score              double precision NOT NULL, -- similarity score

    -- Reference into the external vector store (Chroma/pgvector later). The
    -- embedding itself is NOT stored here yet — open question #2.
    vector_store       text,                      -- e.g. 'chroma:runbooks'
    chunk_external_id  text,                      -- id of the chunk/embedding in that store
    metadata           jsonb NOT NULL DEFAULT '{}'::jsonb,

    -- pgvector migration target (left commented until the `vector` extension
    -- and an embedding model are wired in):
    --   embedding      vector(1536),

    retrieved_at       timestamptz NOT NULL DEFAULT now(),
    created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chunks_incident ON retrieved_chunks (incident_id, score DESC);
CREATE INDEX IF NOT EXISTS idx_chunks_run      ON retrieved_chunks (agent_run_id);

-- =====================================================================
-- 6. diagnoses  — one structured diagnosis result per run
-- =====================================================================
CREATE TABLE IF NOT EXISTS diagnoses (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    incident_id   uuid NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    agent_run_id  uuid REFERENCES agent_runs(id) ON DELETE SET NULL,

    status        text NOT NULL DEFAULT 'ok'
                  CHECK (status IN ('ok','error')),
    engine        text NOT NULL DEFAULT 'deterministic'
                  CHECK (engine IN ('deterministic','llm')),
    summary       text,
    symptoms      jsonb NOT NULL DEFAULT '[]'::jsonb,
    -- "references" is a reserved word in SQL, so the column is named explicitly.
    reference_citations jsonb NOT NULL DEFAULT '[]'::jsonb,  -- citation strings
    error         text,

    -- The current/authoritative diagnosis for the incident (latest accepted run).
    is_current    boolean NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_diagnoses_incident ON diagnoses (incident_id, created_at DESC);
-- At most one current diagnosis per incident.
CREATE UNIQUE INDEX IF NOT EXISTS uq_diagnoses_current
    ON diagnoses (incident_id) WHERE is_current;

-- =====================================================================
-- 7. hypotheses  — ranked root-cause hypotheses for a diagnosis
-- =====================================================================
CREATE TABLE IF NOT EXISTS hypotheses (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    incident_id         uuid NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    diagnosis_id        uuid NOT NULL REFERENCES diagnoses(id) ON DELETE CASCADE,

    rank                integer NOT NULL,             -- 1 = most likely
    cause               text NOT NULL,
    confidence          numeric(4,3) NOT NULL
                        CHECK (confidence >= 0 AND confidence <= 1),
    confidence_label    text CHECK (confidence_label IN ('low','medium','high')),
    root_cause_category text,                         -- e.g. slow_dependency, oom_kill

    evidence            jsonb NOT NULL DEFAULT '[]'::jsonb,  -- supporting evidence refs/strings
    recommended_checks  jsonb NOT NULL DEFAULT '[]'::jsonb,
    missing_information jsonb NOT NULL DEFAULT '[]'::jsonb,

    is_selected         boolean NOT NULL DEFAULT false,  -- chosen as the working root cause
    created_at          timestamptz NOT NULL DEFAULT now(),

    UNIQUE (diagnosis_id, rank)
);

CREATE INDEX IF NOT EXISTS idx_hypotheses_diagnosis ON hypotheses (diagnosis_id, rank);
CREATE INDEX IF NOT EXISTS idx_hypotheses_incident  ON hypotheses (incident_id);

-- =====================================================================
-- 8. recommendations  — advisory remediation actions
-- =====================================================================
CREATE TABLE IF NOT EXISTS recommendations (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    incident_id         uuid NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    diagnosis_id        uuid REFERENCES diagnoses(id) ON DELETE SET NULL,
    hypothesis_id       uuid REFERENCES hypotheses(id) ON DELETE SET NULL,
    agent_run_id        uuid REFERENCES agent_runs(id) ON DELETE SET NULL,

    rank                integer NOT NULL DEFAULT 1,
    action_category     text NOT NULL
                        CHECK (action_category IN ('investigate','rollback','scale',
                               'restart','tune_config','page_owner','open_ticket')),
    title               text NOT NULL,
    rationale           text,
    evidence            jsonb NOT NULL DEFAULT '[]'::jsonb,

    risk_level          text NOT NULL DEFAULT 'low'
                        CHECK (risk_level IN ('low','medium','high')),
    rollback_note       text,
    approval_required   boolean NOT NULL DEFAULT false,
    production_impacting boolean NOT NULL DEFAULT false,

    -- Execution status PLACEHOLDER. The MVP never auto-executes; default reflects
    -- the advisory-only contract (backend.remediation).
    execution_status    text NOT NULL DEFAULT 'manual_only'
                        CHECK (execution_status IN ('manual_only','proposed',
                               'approved','rejected','executed')),
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_recos_incident ON recommendations (incident_id, rank);
CREATE INDEX IF NOT EXISTS idx_recos_diagnosis ON recommendations (diagnosis_id);

-- =====================================================================
-- 9. evaluation_runs  — one execution of the scenario regression suite
-- =====================================================================
CREATE TABLE IF NOT EXISTS evaluation_runs (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    baseline_version    text NOT NULL,           -- e.g. KAN-9-baseline-1
    engine              text CHECK (engine IN ('deterministic','llm')),
    model_provider      text,
    model_name          text,
    prompt_version      text,
    git_sha             text,                    -- commit under test

    total_scenarios     integer NOT NULL DEFAULT 0,
    passed              integer NOT NULL DEFAULT 0,
    failed              integer NOT NULL DEFAULT 0,
    pass_rate           numeric(5,4),
    avg_top_confidence  numeric(4,3),

    status              text NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running','completed','failed')),
    notes               text,
    started_at          timestamptz NOT NULL DEFAULT now(),
    finished_at         timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_evalruns_org_time ON evaluation_runs (org_id, created_at DESC);

-- =====================================================================
-- 10. evaluation_results  — per-scenario outcome within an evaluation run
-- =====================================================================
CREATE TABLE IF NOT EXISTS evaluation_results (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id                   uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    evaluation_run_id        uuid NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,

    scenario                 text NOT NULL,
    -- The incident/diagnosis produced while evaluating this scenario (optional
    -- but enables drill-down/replay from a regression result).
    incident_id              uuid REFERENCES incidents(id) ON DELETE SET NULL,
    diagnosis_id             uuid REFERENCES diagnoses(id) ON DELETE SET NULL,

    expected_category        text,
    expected_top_cause       text,
    expected_runbook         text,
    predicted_category       text,
    predicted_top_cause      text,
    top_confidence           numeric(4,3),

    category_match           boolean,
    cause_match              boolean,
    runbook_match            boolean,
    passed                   boolean NOT NULL DEFAULT false,
    details                  jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at               timestamptz NOT NULL DEFAULT now(),

    UNIQUE (evaluation_run_id, scenario)
);

CREATE INDEX IF NOT EXISTS idx_evalresults_run ON evaluation_results (evaluation_run_id);

COMMIT;

-- =====================================================================
-- Row-level security (multi-tenant) — template, disabled by default.
-- Enable per table and set `SET app.current_org = '<uuid>'` per session/request.
-- ---------------------------------------------------------------------
-- ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY incidents_tenant_isolation ON incidents
--     USING (org_id = current_setting('app.current_org')::uuid);
-- (repeat for every org-scoped table)
-- =====================================================================
