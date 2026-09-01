"""페르소나 조립 — UI가 받은 '분포'를 파이프라인이 쓰는 '개인 100명'으로 바꾼다.

Goal(목표)은 미션당 정확히 1개다 — 100명 전원이 같은 목표 문장을 좇는다.
사람마다 달라지는 건 목표가 아니라 특성 조합(TraitCombo, 16가지)이다.

예전엔 목표가 11개였다. 기획서 4장 "목표는 10개가 아니라 11개":
    특성 조합이 16개다. 10개면 최소공배수가 80이라 81번째부터 앞 20명과 조건이
    그대로 겹친다. 11은 16과 서로소라 100명 전원이 서로 다른 (조합, 목표) 쌍을 받는다.

`agent-ux/generate.py`가 실제 파이프라인에서 이미 이 방식을 버리고 "전원 같은 목표"로
넘어갔길래(그쪽 코드가 스스로 그렇게 밝힌다), 여기 조립 로직도 맞췄다. Goal 테이블과
Persona.goal_id는 나중에 목표를 다시 나눌 일이 생길 때를 위해 남겨 둔다.
"""

from __future__ import annotations

import uuid
from math import gcd

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import Goal, Mission, Persona, PersonaSpec, TraitCombo

GOAL_COUNT = 1   # 미션당 목표는 이제 하나(=미션 문장)뿐이다. 예전엔 11이었다.
TRAIT_COUNT = 16


class PersonaBuildError(RuntimeError):
    pass


def expand_spec(specs: list[PersonaSpec]) -> list[tuple[str, str]]:
    """인원표를 (연령대, 성별) 목록으로 편다.

    화면은 연령대별 총원과 비율만 받으므로, 개인을 만들려면 여기서 비율을 인원으로 편다.
    꺼진 행은 세지 않는다.
    """
    people: list[tuple[str, str]] = []
    for spec in sorted(specs, key=lambda s: s.age_band):
        if not spec.enabled:
            continue
        for gender, count in spec.split().items():
            people.extend([(spec.age_band, gender)] * count)
    return people


def assemble(session: Session, test_id: uuid.UUID) -> list[Persona]:
    """test 의 인원표 + 특성 16 + 목표 1 로 페르소나를 만든다. 기존 것은 지우고 다시 만든다."""
    specs = list(session.scalars(select(PersonaSpec).where(PersonaSpec.test_id == test_id)))
    people = expand_spec(specs)
    if not people:
        raise PersonaBuildError("인원표가 비어 있습니다. 연령대를 하나 이상 켜고 인원을 입력하세요.")

    combos = list(session.scalars(select(TraitCombo).order_by(TraitCombo.id)))
    if len(combos) != TRAIT_COUNT:
        raise PersonaBuildError(f"특성 조합이 {len(combos)}개입니다. {TRAIT_COUNT}개여야 합니다.")

    mission = session.scalar(select(Mission).where(Mission.test_id == test_id))
    if mission is None:
        raise PersonaBuildError("미션이 없습니다. 미션 설정을 먼저 저장하세요.")

    goals = list(session.scalars(select(Goal).where(Goal.mission_id == mission.id).order_by(Goal.idx)))
    if len(goals) != GOAL_COUNT:
        raise PersonaBuildError(
            f"목표가 {len(goals)}개입니다. {GOAL_COUNT}개여야 합니다 "
            "(미션 저장 시 자동으로 만들어지므로, 보통 미션을 다시 저장하면 해결됩니다)."
        )

    # gcd 검사는 목표가 여러 개였을 때(예전 11개) 조합이 겹치지 않게 하려던 것이다.
    # GOAL_COUNT=1이면 gcd(16,1)=1이라 항상 통과하고, 지금은 사실상 의미가 없다 —
    # 나중에 목표를 다시 여러 개로 나누게 되면 이 검사가 그 성질을 여전히 지켜준다.
    if gcd(TRAIT_COUNT, GOAL_COUNT) != 1:
        raise PersonaBuildError(f"{TRAIT_COUNT}와 {GOAL_COUNT}가 서로소가 아닙니다.")

    # 목표가 하나뿐이므로 사람마다 달라지는 축은 특성 조합뿐이다. 100명이 특성 조합
    # 16개를 여러 바퀴 도는 것(반복)은 이제 정상 동작이라, 예전의 "조합×목표 쌍 한도"
    # 검사는 없앴다 — 그 한도는 goal이 구분 축이었을 때만 뜻이 있었다.

    session.execute(delete(Persona).where(Persona.test_id == test_id))

    personas: list[Persona] = []
    for i, (age_band, gender) in enumerate(people):
        combo = combos[i % TRAIT_COUNT]
        goal = goals[0]  # 목표는 하나뿐이다 — 전원 같은 목표를 받는다.
        personas.append(
            Persona(
                test_id=test_id,
                code=f"P{i + 1:03d}",
                trait_combo_id=combo.id,
                goal_id=goal.id,
                age_band=age_band,
                gender=gender,
                dwell_ms=combo.dwell_ms,
                max_steps=combo.max_steps,
            )
        )

    session.add_all(personas)
    return personas


def popup_reachable_count(personas: list[Persona], threshold_ms: int = 10_000) -> int:
    """10초 팝업(D-26)을 마주칠 수 있는 인원. '못 잡음'과 '마주친 적 없음'을 가르는 값이다."""
    return sum(1 for p in personas if p.dwell_ms >= threshold_ms)
