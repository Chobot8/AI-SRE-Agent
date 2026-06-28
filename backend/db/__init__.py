"""PostgreSQL storage layer for the AI SRE Agent (KAN-16).

Persistence is intentionally isolated here so the agent workflow
(``backend.analysis`` etc.) stays decoupled from SQL details. Repositories
return plain dicts, not ORM instances, across that boundary.
"""
