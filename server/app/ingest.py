"""파이프라인 실행 로그(JSON) → DB 적재.

`agent-ux/run.py`는 결과를 `agent-ux/logs/<run_id>/*.json` 에만 남긴다. 이 스크립트는
그 로그 폴더를 읽어서, `POST /tests/{id}/runs` 가 미리 만들어 둔 Journey 자리에 채워 넣는다.
`agent-ux` 쪽 코드는 건드리지 않는다 — 그쪽은 계속 JSON 만 안다.

    python -m app.ingest --run-id <DB Run UUID> --log-dir ../agent-ux/logs/<pipeline_run_id>

두 프로젝트가 같은 개념을 다른 이름으로 부르는 지점이 있어서(종료 사유, 행동 종류),
아래 매핑 표에서 명시적으로 옮긴다. 모르는 값은 조용히 삼키지 않고 경고로 남긴다.
"""

from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .db import session_scope
from .models import Journey, Persona, Run, Step

# agent-ux(trace.py의 END_REASONS) → DB(models.py의 TerminationReason).
END_REASON_MAP = {
    "goal_reached": "goal_achieved",
    "gave_up": "gave_up",
    "max_steps": "step_budget_exhausted",
    "loop_detected": "loop_detected",
    "budget_stop": "budget_cap",
    "error": "runtime_error",
}

# agent-ux(explore.execute()가 실제로 다루는 타입) → DB(models.py의 ActionType).
# select/done/give_up 은 DB enum에 없어서 other로 뭉뚱그려진다 — 원본은
# Journey.log_path 가 가리키는 JSON에 그대로 남아 있으니 정보가 없어지는 것은 아니다.
ACTION_TYPE_MAP = {
    "click": "click",
    "type": "type",
    "scroll": "scroll",
    "back": "back",
    "wait": "wait",
    "goto": "navigate_link",
}


@dataclass
class IngestSummary:
    run_id: uuid.UUID
    matched: list[str] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    unknown_end_reasons: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        lines = [f"적재 {len(self.matched)}명 (run={self.run_id})"]
        if self.unmatched:
            lines.append(
                f"페르소나 불일치로 건너뜀 {len(self.unmatched)}명: {', '.join(self.unmatched)}"
            )
        if self.unknown_end_reasons:
            lines.append(
                "알 수 없는 종료 사유 → runtime_error 로 대체: "
                + ", ".join(sorted(set(self.unknown_end_reasons)))
            )
        return "\n".join(lines)


def _map_end_reason(raw: str, summary: IngestSummary) -> str:
    mapped = END_REASON_MAP.get(raw)
    if mapped is None:
        summary.unknown_end_reasons.append(raw)
        return "runtime_error"
    return mapped


def _map_action_type(raw: str | None) -> str:
    return ACTION_TYPE_MAP.get(raw or "", "other")


def _parse_dt(raw: str | None) -> datetime | None:
    return datetime.fromisoformat(raw) if raw else None


def ingest_run(session: Session, run_id: uuid.UUID, log_dir: Path) -> IngestSummary:
    run = session.get(Run, run_id)
    if run is None:
        raise ValueError(
            f"run_id {run_id} 를 찾을 수 없습니다 — 먼저 POST /tests/{{id}}/runs 로 만드세요."
        )

    index_path = log_dir / "index.json"
    if not index_path.exists():
        raise FileNotFoundError(
            f"{index_path} 가 없습니다 — run.py 가 이 폴더에 결과를 남겼는지 확인하세요."
        )
    index = json.loads(index_path.read_text(encoding="utf-8"))

    summary = IngestSummary(run_id=run_id)

    for entry in index["personas"]:
        persona_code = entry["id"]
        persona = session.scalar(
            select(Persona).where(Persona.test_id == run.test_id, Persona.code == persona_code)
        )
        if persona is None:
            summary.unmatched.append(persona_code)
            continue

        trace = json.loads((log_dir / entry["file"]).read_text(encoding="utf-8"))

        journey = session.scalar(
            select(Journey).where(Journey.run_id == run_id, Journey.persona_id == persona.id)
        )
        if journey is None:
            journey = Journey(run_id=run_id, persona_id=persona.id)
            session.add(journey)
            session.flush()  # journey.id 를 Step 이 참조하려면 먼저 있어야 한다

        journey.termination_reason = _map_end_reason(trace["end_reason"], summary)
        journey.goal_achieved = trace["end_reason"] == "goal_reached"
        journey.step_count = len(trace["steps"])
        journey.log_path = str(log_dir / entry["file"])
        journey.started_at = _parse_dt(trace.get("started_at"))
        journey.finished_at = _parse_dt(trace.get("ended_at"))
        session.flush()

        # 재실행해도 같은 결과가 나오도록, 기존 스텝을 지우고 다시 채운다.
        session.execute(delete(Step).where(Step.journey_id == journey.id))
        for raw_step in trace["steps"]:
            action = raw_step["action"]
            blocked = raw_step.get("blocked_action") is not None
            outcome = raw_step.get("outcome") or {}
            snapshot = raw_step.get("snapshot") or {}
            session.add(
                Step(
                    journey_id=journey.id,
                    idx=raw_step["step"],
                    thought=raw_step.get("thought"),
                    action=_map_action_type(action.get("type")),
                    action_target=action.get("target"),
                    action_value=action.get("value"),
                    allowed=not blocked,
                    executed=not blocked,
                    url=snapshot.get("url") or outcome.get("url_after"),
                )
            )

        summary.matched.append(persona_code)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="파이프라인 실행 로그를 DB에 적재")
    parser.add_argument("--run-id", required=True, type=uuid.UUID)
    parser.add_argument("--log-dir", required=True, type=Path)
    args = parser.parse_args()

    with session_scope() as session:
        summary = ingest_run(session, args.run_id, args.log_dir)

    print(summary)


if __name__ == "__main__":
    main()
