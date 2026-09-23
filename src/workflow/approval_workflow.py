import json
import os
from datetime import datetime, timezone
from enum import Enum

AUDIT_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "audit_log.jsonl")


class WorkflowStage(str, Enum):
    DETECTED = "detected"
    EXPLAINED = "explained"
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    VERIFIED = "verified"


class CorrectiveAction:
    def __init__(self, action_id, issue_type, target, detail):
        self.action_id = action_id
        self.issue_type = issue_type
        self.target = target
        self.detail = detail
        self.stage = WorkflowStage.DETECTED
        self.explanation = None
        self.proposal = None
        self.history = []

    def _log(self, note):
        # Fix #5: use timezone-aware UTC datetime (utcnow() is deprecated in Python 3.12+)
        entry = {
            "action_id": self.action_id,
            "stage": self.stage.value,
            "note": note,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.history.append(entry)
        os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
        with open(AUDIT_LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def explain(self, explanation):
        self.explanation = explanation
        self.stage = WorkflowStage.EXPLAINED
        self._log(f"explained: {explanation}")
        return self

    def propose(self, proposal):
        self.proposal = proposal
        self.stage = WorkflowStage.PROPOSED
        self._log(f"proposed: {proposal}")
        return self

    def approve(self, approved_by):
        self.stage = WorkflowStage.APPROVED
        self._log(f"approved by {approved_by}")
        return self

    def reject(self, rejected_by, reason=""):
        self.stage = WorkflowStage.REJECTED
        self._log(f"rejected by {rejected_by}: {reason}")
        return self

    def execute(self, execute_fn):
        if self.stage != WorkflowStage.APPROVED:
            raise ValueError("Action must be approved before execution")
        result = execute_fn()
        self.stage = WorkflowStage.EXECUTED
        self._log(f"executed: {result}")
        return self

    def verify(self, verify_fn):
        if self.stage != WorkflowStage.EXECUTED:
            raise ValueError("Action must be executed before verification")
        passed = verify_fn()
        self.stage = WorkflowStage.VERIFIED
        self._log(f"verified: {'passed' if passed else 'failed'}")
        return self

    # --- Serialization (needed for Redis-backed storage) ---

    def to_dict(self):
        return {
            "action_id": self.action_id,
            "issue_type": self.issue_type,
            "target": self.target,
            "detail": self.detail,
            "stage": self.stage.value,
            "explanation": self.explanation,
            "proposal": self.proposal,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data):
        action = cls(data["action_id"], data["issue_type"], data["target"], data["detail"])
        action.stage = WorkflowStage(data["stage"])
        action.explanation = data.get("explanation")
        action.proposal = data.get("proposal")
        action.history = data.get("history", [])
        return action


def example_dedupe_workflow(action_id, duplicate_pair):
    action = CorrectiveAction(
        action_id=action_id,
        issue_type="duplicate_customer",
        target=duplicate_pair,
        detail=f"Records {duplicate_pair} flagged as likely duplicates",
    )
    action.explain("High name and email similarity across two customer records")
    action.propose(f"Merge record {duplicate_pair[1]} into {duplicate_pair[0]}, keep earliest signup_date")
    return action


if __name__ == "__main__":
    action = example_dedupe_workflow("act_001", (12, 512))
    action.approve(approved_by="data_steward")
    action.execute(lambda: "merged records 12 and 512")
    action.verify(lambda: True)
    print(f"Final stage: {action.stage.value}")
    print(f"History logged to {AUDIT_LOG_PATH}")
