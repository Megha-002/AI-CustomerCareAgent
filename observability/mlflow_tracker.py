"""
MLflow Tracker — Logs every workflow run for observability.
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger("observability.mlflow")

_mlflow_ready = False
_experiment_id = None
_EXPERIMENT_NAME = "refund-agent-workflows"


def _ensure_mlflow():
    global _mlflow_ready, _experiment_id
    if _mlflow_ready:
        return True
    try:
        import mlflow
        from dotenv import load_dotenv
        load_dotenv()
        tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
        mlflow.set_tracking_uri(tracking_uri)
        experiment = mlflow.get_experiment_by_name(_EXPERIMENT_NAME)
        if experiment is None:
            mlflow.create_experiment(_EXPERIMENT_NAME)
            experiment = mlflow.get_experiment_by_name(_EXPERIMENT_NAME)
        _experiment_id = experiment.experiment_id
        _mlflow_ready = True
        logger.info(f"MLflow ready — tracking to {tracking_uri}")
        return True
    except ImportError:
        logger.info("MLflow not installed — tracking disabled")
        return False
    except Exception as e:
        logger.warning(f"MLflow init failed (non-critical): {e}")
        return False


def log_workflow_run(
    user_input: str,
    result: Dict[str, Any],
    processing_time_ms: float,
    session_id: Optional[str] = None,
) -> Optional[str]:
    if not _ensure_mlflow():
        return None
    import mlflow
    import json
    run_id = None
    try:
        with mlflow.start_run(run_name=f"refund-{datetime.now().strftime('%H%M%S')}") as run:
            run_id = run.info.run_id
            mlflow.log_param("user_input", user_input[:200])
            mlflow.log_param("session_id", session_id or "none")
            mlflow.log_param("decision", result.get("decision", "UNKNOWN"))
            mlflow.log_metric("confidence", result.get("confidence") or 0)
            mlflow.log_metric("processing_time_ms", processing_time)
            mlflow.log_metric("error_count", len(result.get("errors", [])))
            mlflow.log_metric("reasoning_steps", len(result.get("reasoning_log", [])))
            decision_map = {"APPROVE": 1, "REJECT": 0, "ESCALATE": -1}
            mlflow.log_metric("decision_code", decision_map.get(result.get("decision"), -99))
            mlflow.set_tag("decision", result.get("decision", "UNKNOWN"))
            mlflow.set_tag("has_errors", str(len(result.get("errors", [])) > 0))
            mlflow.log_text(_format_reasoning(result), "reasoning_log.txt")
            mlflow.log_text(json.dumps(result, default=str, indent=2), "full_result.json")
            logger.info(f"MLflow run logged: {run_id}")
    except Exception as e:
        logger.warning(f"MLflow run logging failed (non-critical): {e}")
        run_id = None
    return run_id


def _format_reasoning(result: Dict[str, Any]) -> str:
    lines = [
        "=" * 60,
        f"DECISION: {result.get('decision', 'UNKNOWN')}",
        f"CONFIDENCE: {result.get('confidence', 0):.2f}",
        f"REASON: {result.get('decision_reason', 'N/A')}",
        "=" * 60, "", "REASONING STEPS:", "-" * 40,
    ]
    for step in result.get("reasoning_log", []):
        lines.append(f"[{step.get('node', '?')}] {step.get('output_summary', '')}")
    if result.get("errors"):
        lines.append("")
        lines.append("ERRORS:")
        for error in result.get("errors", []):
            lines.append(f"  - {error}")
    return "\n".join(lines)


def get_recent_runs(limit: int = 10) -> List[Dict[str, Any]]:
    if not _ensure_mlflow():
        return []
    import mlflow
    try:
        runs = mlflow.search_runs(
            experiment_ids=[_experiment_id],
            max_results=limit,
            order_by=["start_time DESC"],
        )
        return runs.to_dict("records") if not runs.empty else []
    except Exception as e:
        logger.warning(f"Failed to fetch recent runs: {e}")
        return []


def get_run_stats() -> Dict[str, Any]:
    default = {
        "total_runs": 0, "approvals": 0, "rejections": 0,
        "escalations": 0, "approve_rate": 0, "avg_confidence": 0,
    }
    if not _ensure_mlflow():
        return default
    import mlflow
    try:
        runs = mlflow.search_runs(experiment_ids=[_experiment_id])
        if runs.empty:
            return default
        total = len(runs)
        approvals = len(runs[runs["params.decision"] == "APPROVE"])
        rejections = len(runs[runs["params.decision"] == "REJECT"])
        escalations = len(runs[runs["params.decision"] == "ESCALATE"])
        avg_conf = runs["metrics.confidence"].mean() if "metrics.confidence" in runs.columns else 0
        return {
            "total_runs": total,
            "approvals": approvals,
            "rejections": rejections,
            "escalations": escalations,
            "approve_rate": round(approvals / total * 100, 1) if total > 0 else 0,
            "avg_confidence": round(float(avg_conf), 2),
        }
    except Exception as e:
        logger.warning(f"Failed to fetch run stats: {e}")
        return default