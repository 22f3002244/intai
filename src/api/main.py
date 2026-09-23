import json
import os
import sys
from fastapi import FastAPI
from pydantic import BaseModel

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from src.agent.query_agent import answer_query
from src.entity_resolution.dedupe import run_entity_resolution
from src.workflow.approval_workflow import CorrectiveAction

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")

app = FastAPI(title="Enterprise AI Data Intelligence Platform")

_pending_actions = {}


class QueryRequest(BaseModel):
    question: str


class ApprovalRequest(BaseModel):
    action_id: str
    approved_by: str


@app.get("/catalog/profiles")
def get_profiles():
    with open(os.path.join(DATA_DIR, "profiles.json")) as f:
        return json.load(f)


@app.get("/catalog/quality")
def get_quality_report():
    with open(os.path.join(DATA_DIR, "quality_report.json")) as f:
        return json.load(f)


@app.get("/catalog/pii")
def get_pii_report():
    with open(os.path.join(DATA_DIR, "pii_report.json")) as f:
        return json.load(f)


@app.get("/entity-resolution/duplicates")
def get_duplicates():
    return run_entity_resolution()


@app.post("/query")
def query(request: QueryRequest):
    return {"answer": answer_query(request.question)}


@app.post("/actions/{action_id}/propose")
def propose_action(action_id: str, issue_type: str, target: str, detail: str, explanation: str, proposal: str):
    action = CorrectiveAction(action_id, issue_type, target, detail)
    action.explain(explanation)
    action.propose(proposal)
    _pending_actions[action_id] = action
    return {"action_id": action_id, "stage": action.stage.value}


@app.post("/actions/approve")
def approve_action(request: ApprovalRequest):
    action = _pending_actions.get(request.action_id)
    if not action:
        return {"error": "action not found"}
    action.approve(approved_by=request.approved_by)
    return {"action_id": request.action_id, "stage": action.stage.value}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
