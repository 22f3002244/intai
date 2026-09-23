import json
import os
import redis
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.agent.query_agent import answer_query
from src.entity_resolution.dedupe import run_entity_resolution
from src.workflow.approval_workflow import CorrectiveAction, WorkflowStage

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6380")
ENTITY_RESOLUTION_CACHE_KEY = "entity_resolution_result"
ENTITY_RESOLUTION_TTL = int(os.environ.get("ENTITY_RESOLUTION_TTL_SECONDS", 300))  # 5 min default

app = FastAPI(
    title="Enterprise AI Data Intelligence Platform",
    description="AI-powered data management: profiling, entity resolution, governance, and NL querying.",
    version="0.1.0",
)

# Fix #16: CORS middleware so frontends / external services can reach the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fix #2: Redis-backed action store — survives restarts and works across workers.
_redis: redis.Redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def _save_action(action: CorrectiveAction, ttl: int = 86400):
    """Persist a CorrectiveAction to Redis (TTL defaults to 24 h)."""
    _redis.set(f"action:{action.action_id}", json.dumps(action.to_dict()), ex=ttl)


def _load_action(action_id: str) -> CorrectiveAction | None:
    """Retrieve a CorrectiveAction from Redis, or None if not found."""
    raw = _redis.get(f"action:{action_id}")
    if raw is None:
        return None
    return CorrectiveAction.from_dict(json.loads(raw))


# ── Helper ─────────────────────────────────────────────────────────────────────

def _read_json(filename: str):
    """Read a JSON report file produced by the pipeline; raises 404 if missing."""
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail=f"'{filename}' not found. Run the pipeline first: python src/profiling/profiler.py",
        )
    with open(path) as f:
        return json.load(f)


# ── Request / Response models ──────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str


class ApprovalRequest(BaseModel):
    action_id: str
    approved_by: str


# Fix #7: move sensitive fields from query params into a request body.
class ProposeActionRequest(BaseModel):
    issue_type: str
    target: str
    detail: str
    explanation: str
    proposal: str


class RejectActionRequest(BaseModel):
    action_id: str
    rejected_by: str
    reason: str = ""


# ── Catalog endpoints ──────────────────────────────────────────────────────────

@app.get("/catalog/profiles", summary="Dataset schema and column statistics")
def get_profiles():
    # Fix #3: returns 404 with a helpful message instead of crashing.
    return _read_json("profiles.json")


@app.get("/catalog/quality", summary="Data quality scores per dataset")
def get_quality_report():
    return _read_json("quality_report.json")


@app.get("/catalog/pii", summary="Detected PII columns per dataset")
def get_pii_report():
    return _read_json("pii_report.json")


# ── Entity-resolution endpoint ─────────────────────────────────────────────────

@app.get("/entity-resolution/duplicates", summary="Duplicate records across sources")
def get_duplicates():
    # Fix #4: cache the O(n²) result in Redis; recompute only after TTL expires.
    cached = _redis.get(ENTITY_RESOLUTION_CACHE_KEY)
    if cached:
        return json.loads(cached)

    result = run_entity_resolution()
    _redis.set(ENTITY_RESOLUTION_CACHE_KEY, json.dumps(result), ex=ENTITY_RESOLUTION_TTL)
    return result


@app.delete(
    "/entity-resolution/cache",
    summary="Invalidate the entity-resolution cache to force a fresh run",
)
def invalidate_entity_resolution_cache():
    _redis.delete(ENTITY_RESOLUTION_CACHE_KEY)
    return {"detail": "Entity resolution cache invalidated."}


# ── NL query endpoint ──────────────────────────────────────────────────────────

@app.post("/query", summary="Ask a question about the data in plain English")
def query(request: QueryRequest):
    try:
        return {"answer": answer_query(request.question)}
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"AI query service temporarily unavailable: {exc}",
        ) from exc


# ── Corrective-action workflow endpoints ───────────────────────────────────────

@app.post(
    "/actions/{action_id}/propose",
    summary="Propose a corrective action for a detected data issue",
)
def propose_action(action_id: str, request: ProposeActionRequest):
    # Fix #7: all sensitive detail in the request body, not the URL.
    action = CorrectiveAction(action_id, request.issue_type, request.target, request.detail)
    action.explain(request.explanation)
    action.propose(request.proposal)
    _save_action(action)
    return {"action_id": action_id, "stage": action.stage.value}


@app.post("/actions/approve", summary="Approve a pending corrective action")
def approve_action(request: ApprovalRequest):
    action = _load_action(request.action_id)
    # Fix #11: proper 404 instead of HTTP 200 + error body.
    if action is None:
        raise HTTPException(status_code=404, detail=f"Action '{request.action_id}' not found.")
    if action.stage not in (WorkflowStage.PROPOSED, WorkflowStage.EXPLAINED):
        raise HTTPException(
            status_code=409,
            detail=f"Action is in stage '{action.stage.value}' and cannot be approved.",
        )
    action.approve(approved_by=request.approved_by)
    _save_action(action)
    return {"action_id": request.action_id, "stage": action.stage.value}


# Fix #12: missing reject endpoint.
@app.post("/actions/reject", summary="Reject a pending corrective action")
def reject_action(request: RejectActionRequest):
    action = _load_action(request.action_id)
    if action is None:
        raise HTTPException(status_code=404, detail=f"Action '{request.action_id}' not found.")
    if action.stage not in (WorkflowStage.PROPOSED, WorkflowStage.EXPLAINED, WorkflowStage.APPROVED):
        raise HTTPException(
            status_code=409,
            detail=f"Action is in stage '{action.stage.value}' and cannot be rejected.",
        )
    action.reject(rejected_by=request.rejected_by, reason=request.reason)
    _save_action(action)
    return {"action_id": request.action_id, "stage": action.stage.value}


# Fix #13: expose execute and verify in the API.
@app.post(
    "/actions/{action_id}/execute",
    summary="Execute an approved corrective action",
)
def execute_action(action_id: str):
    action = _load_action(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")
    if action.stage != WorkflowStage.APPROVED:
        raise HTTPException(
            status_code=409,
            detail=f"Action must be in 'approved' stage to execute (current: '{action.stage.value}').",
        )
    # Dispatch to the appropriate execution handler based on issue_type.
    action.execute(lambda: _dispatch_execute(action))
    _save_action(action)
    return {"action_id": action_id, "stage": action.stage.value}


@app.post(
    "/actions/{action_id}/verify",
    summary="Verify an executed corrective action",
)
def verify_action(action_id: str):
    action = _load_action(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")
    if action.stage != WorkflowStage.EXECUTED:
        raise HTTPException(
            status_code=409,
            detail=f"Action must be in 'executed' stage to verify (current: '{action.stage.value}').",
        )
    action.verify(lambda: _dispatch_verify(action))
    _save_action(action)
    return {"action_id": action_id, "stage": action.stage.value}


@app.get("/actions/{action_id}", summary="Get the current state of a corrective action")
def get_action(action_id: str):
    action = _load_action(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")
    return action.to_dict()


# ── Internal dispatch helpers ──────────────────────────────────────────────────

def _dispatch_execute(action: CorrectiveAction) -> str:
    """Stub dispatcher — extend with real business logic per issue_type."""
    handlers = {
        "duplicate_customer": lambda a: f"Flagged duplicate pair {a.target} for manual merge review.",
        "pii_exposure": lambda a: f"Masked PII column '{a.detail}' in dataset '{a.target}'.",
        "high_null_rate": lambda a: f"Triggered null-fill job for column '{a.detail}' in '{a.target}'.",
    }
    handler = handlers.get(action.issue_type)
    if handler:
        return handler(action)
    return f"Generic execution for issue type '{action.issue_type}' on target '{action.target}'."


def _dispatch_verify(action: CorrectiveAction) -> bool:
    """Stub verifier — extend with real checks per issue_type."""
    # Default: assume success; replace with actual DB/system checks.
    return True


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
