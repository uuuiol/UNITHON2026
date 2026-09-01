"""DB에 조립된 Persona 100명을 agent-ux/run.py가 읽는 personas.json 형식으로 내보낸다.

`agent-ux/generate.py`는 나이·성별을 항상 균등 배정하고, DB의 TraitCombo(16가지,
reading_style/pace/tech_literacy/patience)와는 다른 축(literacy/attention/patience/
breadth, 625가지)을 쓴다. 그래서 generate.py를 부르는 대신 이미 화면 인원표대로
조립된 DB Persona를 직접 이 형식으로 바꾼다 — "누가 몇 명인가"의 결정권을 DB에 둔다.

TraitCombo에 없는 필드(search_allowed, max_idle_attempts, compare_cap)는 아래
_SEARCH_ALLOWED 등에서 규칙을 새로 정한다. 발명이라는 걸 숨기지 않는다:
  - search_allowed: tech_literacy == "능숙" 인 사람만 주소창(goto)을 쓴다.
  - max_idle_attempts: patience 양 끝(높음/낮음)을 agent-ux PATIENCE 표의 대표값으로.
  - compare_cap: DB엔 "탐색 범위" 축이 없다 — 없는 걸 지어내지 않고 전원 0(무제한).
"""

from __future__ import annotations

from .models import Mission, Persona, Test, TraitCombo

# agent-ux/uxagent/persona.py의 SENTENCES와 같은 역할이지만, DB의 2단계 축에 맞춰
# 새로 쓴 문장이다 (그쪽은 1~5단계라 그대로 재사용할 수 없다).
SENTENCES: dict[str, dict[str, str]] = {
    "reading_style": {
        "정독": "화면의 글을 꼼꼼히 읽습니다.",
        "훑기": "필요한 부분만 훑어봅니다.",
    },
    "pace": {
        "여유": "서두르지 않고 여유 있게 둘러봅니다.",
        "급함": "빠르게 훑고 바로 결정합니다.",
    },
    "tech_literacy": {
        "능숙": "온라인 쇼핑에 익숙합니다.",
        "서툼": "온라인 쇼핑이 아직 익숙하지 않습니다.",
    },
    "patience": {
        "높음": "잘 안 돼도 방법을 찾아 다시 시도합니다.",
        "낮음": "조금만 막혀도 바로 그만둡니다.",
    },
}

_AXES = ("reading_style", "pace", "tech_literacy", "patience")

# agent-ux/uxagent/persona.py의 PATIENCE 표(1~5단계, 각 단계별 (허용시도범위, 최대스텝))
# 에서 낮음(1단계)=(4,7), 높음(5단계)=(25,30)의 중간값을 대표로 고정했다.
_MAX_IDLE_ATTEMPTS = {"높음": 24, "낮음": 8}

_BASE_ACTIONS = ["click", "type", "select", "scroll", "back", "wait"]


def _build_prompt(combo: TraitCombo, age_band: str, gender: str, goal: str) -> str:
    lines = [f"{age_band} {gender}입니다."]
    lines += [
        SENTENCES[axis][getattr(combo, axis)]
        for axis in _AXES
    ]
    return "\n".join(lines) + f"\n목표: {goal}"


def _build_one(persona: Persona, combo: TraitCombo, goal: str) -> dict:
    search_allowed = combo.tech_literacy == "능숙"
    actions = list(_BASE_ACTIONS)
    if search_allowed:
        actions.append("goto")

    return {
        "id": persona.code,
        "label": f"{combo.code} {persona.age_band}{persona.gender}",
        "traits": {axis: getattr(combo, axis) for axis in _AXES},
        "age_band": persona.age_band,
        "gender": persona.gender,
        "prompt": _build_prompt(combo, persona.age_band, persona.gender, goal),
        "allowed_actions": actions,
        "search_allowed": search_allowed,
        "max_steps": combo.max_steps,
        "max_idle_attempts": _MAX_IDLE_ATTEMPTS[combo.patience],
        "dwell_ms": combo.dwell_ms,
        "compare_cap": 0,  # DB엔 "탐색 범위" 축이 없다 — 전원 무제한
        "user_type": "new",
        "seed_state": None,
    }


def build_personas_json(
    test: Test, mission: Mission, personas: list[Persona], combos_by_id: dict[int, TraitCombo]
) -> dict:
    """agent-ux/uxagent/trace.py 가 기대하는 {"goal", "start_path", "personas": [...]} 모양.

    --url 모드로 돌리므로 start_path 는 run.py 가 실제로 읽지 않지만(끝에서 두 번째
    문단 참고), 파일 형식을 맞추기 위해 채워는 둔다.
    """
    return {
        "generated_at": None,
        "goal": mission.prompt,
        "start_path": "/",
        "personas": [
            _build_one(p, combos_by_id[p.trait_combo_id], mission.prompt) for p in personas
        ],
    }
