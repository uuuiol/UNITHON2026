"""서로 다른 두 프로젝트를 통째로 견준다.

한 프로젝트 안의 clean/flawed 변형(이미 있는 `Run.arm` 기능)과는 다르다 — 예:
리뉴얼 전 사이트(프로젝트 A)와 리뉴얼 후 사이트(프로젝트 B)를 견주는 용도다.
`web/src/api/mock.ts`의 A/B 로직(같은 페르소나 코드로 짝짓고, B 쪽 표를 기준으로
뽑는다)을 그대로 옮겼다.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .journeys import (
    AXIS_LABEL,
    build_diagram,
    build_steps_payload,
    display_name,
    load_walks,
    walk_side_result,
)
from .models import Journey, Persona, Project, Run, Test


def latest_test_with_results(session: Session, project_id: uuid.UUID) -> Test | None:
    """그 프로젝트에서 실행 기록(Journey)이 하나라도 있는 가장 최근 테스트.

    없으면 None — 방금 만든 프로젝트(A/B 만들 때 새로 만드는 B쪽)가 이 경우다.
    """
    return session.scalar(
        select(Test)
        .join(Run, Run.test_id == Test.id)
        .join(Journey, Journey.run_id == Run.id)
        .where(Test.project_id == project_id)
        .order_by(Test.created_at.desc())
        .limit(1)
    )


def _success_rate(session: Session, test_id: uuid.UUID) -> float | None:
    stats = session.execute(
        select(
            func.count(Journey.id).label("total"),
            func.count(Journey.id).filter(Journey.goal_achieved.is_(True)).label("achieved"),
        )
        .select_from(Journey)
        .join(Run, Run.id == Journey.run_id)
        .where(Run.test_id == test_id)
    ).one()
    if not stats.total:
        return None
    return round(100 * stats.achieved / stats.total, 1)


def project_side(session: Session, project_id: uuid.UUID, test: Test | None) -> dict:
    """AbSide 하나: id/name/preview_url/success_rate."""
    project = session.get(Project, project_id)
    return {
        "id": str(project_id),
        "name": project.name if project else "",
        "preview_url": project.preview_url if project else None,
        "success_rate": _success_rate(session, test.id) if test else None,
    }


def compare_projects(session: Session, test_a: Test | None, test_b: Test | None) -> dict:
    """[화면] A/B 상세의 'compare' 블록.

    B(비교 프로젝트) 기준으로 페르소나 표를 뽑는다 — 그 표의 baseline이 곧 A가 된다.
    페르소나는 test_id가 달라도 같은 code(P001…) 규칙으로 만들어지므로 code로 짝짓는다.
    단, 두 프로젝트의 인원표(연령대·성별 분포)가 서로 다르면 같은 code라도 실제로는
    다른 성향의 사람을 짝짓게 된다 — 그 한계는 여기서 고치지 않는다.
    """
    if test_a is None or test_b is None:
        return {"ok": False, "message": "아직 비교할 기록이 없어요.", "items": []}

    walks_a = {w.persona_code: w for w in load_walks(session, test_a.id)}
    walks_b = {w.persona_code: w for w in load_walks(session, test_b.id)}
    personas_b = list(
        session.scalars(select(Persona).where(Persona.test_id == test_b.id).order_by(Persona.code))
    )

    items: list[dict] = []
    changed = 0
    exhausted = 0
    for persona in personas_b:
        wa = walks_a.get(persona.code)
        wb = walks_b.get(persona.code)
        baseline = walk_side_result(wa)
        compare = walk_side_result(wb)
        is_changed = bool(baseline and compare and baseline["outcome"] != compare["outcome"])
        if is_changed:
            changed += 1
        if wb is not None and wb.termination_reason == "step_budget_exhausted":
            exhausted += 1

        items.append({
            "id": str(persona.id),
            "code": persona.code,
            "name": display_name(persona.code),
            "age_band": persona.age_band,
            "gender": persona.gender,
            "traits": {axis: getattr(persona.trait_combo, axis) for axis in AXIS_LABEL},
            "outcome": compare["outcome"] if compare else None,
            "step_count": compare["step_count"] if compare else None,
            "baseline": baseline,
            "compare": compare,
            "changed": is_changed,
        })

    return {
        "ok": True,
        "items": items,
        "total": len(items),
        "changed": changed,
        "exhausted": exhausted,
        "axes": AXIS_LABEL,
    }


def ab_diagrams(session: Session, test_a: Test | None, test_b: Test | None) -> dict:
    return {
        "a": build_diagram(load_walks(session, test_a.id)) if test_a else None,
        "b": build_diagram(load_walks(session, test_b.id)) if test_b else None,
    }


def ab_steps(session: Session, test_a: Test | None, test_b: Test | None) -> dict:
    return {
        "a": build_steps_payload(load_walks(session, test_a.id), test_a.name) if test_a else None,
        "b": build_steps_payload(load_walks(session, test_b.id), test_b.name) if test_b else None,
    }
