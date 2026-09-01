"""테스트 상세 화면이 쓰는 집계 — 여정 기록을 '경로'와 '다이어그램'으로 접는다.

화면(Figma 264:8033 / 276:3101)이 요구하는 것은 두 가지다.

1. 경로   — 같은 화면 순서를 밟은 사람끼리 묶은 목록. "동일한 화면 이동 순서 기준으로 묶었어요"
2. 다이어그램 — 같은 자료를 단계(열) × 화면(마디)으로 펼친 흐름도.

둘 다 같은 서명(signature)에서 나온다. 서명을 두 번 따로 만들면 두 화면의 숫자가
어긋나는 순간이 오기 때문에, 접는 규칙은 이 파일 하나에만 둔다.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Journey, Persona, Run, Step
from .pipeline_export import SENTENCES

#: 이탈로 세는 종료 사유. api.py 의 이탈률과 같은 정의를 쓴다 —
#: 예산 상한으로 우리가 끊은 것은 '포기'가 아니다(기획서 4장).
DROP_REASONS = ("gave_up", "loop_detected")

#: 카드 한 장에 나란히 놓는 화면 수. 넘으면 "+3" 으로 접는다 (Figma 264:8163).
CARD_SCREENS = 9


@dataclass
class Screen:
    key: str
    title: str
    url: str | None
    #: 이 화면에 처음 머문 스텝의 생각·행동. /steps 상세 패널이 쓴다.
    thought: str | None = None
    action: str | None = None
    action_target: str | None = None
    blocked: bool = False


@dataclass
class Walk:
    """여정 한 건을 화면 순서로 접은 것."""

    journey_id: uuid.UUID
    persona_id: uuid.UUID
    outcome: str  # 'success' | 'drop' | 'other'
    step_count: int
    screens: list[Screen] = field(default_factory=list)
    #: /steps 상세 패널이 쓴다. 페르소나 표 자체는 test_id 로 따로 조회하므로,
    #: 여기 있는 것만으로 화면을 그릴 수 있게 조금 중복해서 들고 있는다.
    persona_code: str = ""
    age_band: str = ""
    gender: str = ""
    termination_reason: str | None = None

    @property
    def signature(self) -> tuple[str, ...]:
        return tuple(s.key for s in self.screens)


def _screen_key(step: Step) -> str | None:
    """화면 이름. 답사가 붙인 screen_key 가 정본이고, 없으면 주소로 대신한다.

    주소도 없으면 그 스텝은 '어느 화면인지 모르는 스텝'이다. 모르는 것을 하나로 묶으면
    서로 다른 화면이 같은 경로로 접히므로, 아예 뺀다.
    """
    if step.screen_key:
        return step.screen_key
    if step.url:
        return step.url
    return None


def _outcome(journey: Journey) -> str:
    if journey.goal_achieved:
        return "success"
    if journey.termination_reason in DROP_REASONS:
        return "drop"
    return "other"


def load_walks(
    session: Session, test_id: uuid.UUID | None, run_id: uuid.UUID | None = None
) -> list[Walk]:
    """여정을 화면 순서로 접어 온다.

    같은 화면에 연달아 머문 스텝(스크롤·입력)은 한 마디로 합친다. 합치지 않으면
    "장바구니 → 장바구니 → 장바구니" 가 서로 다른 경로가 되어 묶음이 흩어진다.

    `run_id`를 주면 그 실행 하나만(예: 방금 로컬에서 돌린 실행, `/api/live/{run_id}`),
    안 주면 `test_id`의 모든 실행(A/B/C/D)을 합쳐서 본다.
    """
    query = select(Journey).order_by(Journey.started_at)
    if run_id is not None:
        query = query.where(Journey.run_id == run_id)
    else:
        query = query.join(Run, Run.id == Journey.run_id).where(Run.test_id == test_id)
    journeys = list(session.scalars(query))
    if not journeys:
        return []

    by_journey: dict[uuid.UUID, list[Step]] = defaultdict(list)
    steps = session.scalars(
        select(Step)
        .where(Step.journey_id.in_([j.id for j in journeys]))
        .order_by(Step.journey_id, Step.idx)
    )
    for step in steps:
        by_journey[step.journey_id].append(step)

    personas = {
        p.id: p
        for p in session.scalars(
            select(Persona).where(Persona.id.in_([j.persona_id for j in journeys]))
        )
    }

    walks: list[Walk] = []
    for journey in journeys:
        screens: list[Screen] = []
        for step in by_journey.get(journey.id, []):
            # 기록만 남기고 실행되지 않은 행동은 화면을 바꾸지 않는다.
            if not step.executed:
                continue
            key = _screen_key(step)
            if key is None:
                continue
            if screens and screens[-1].key == key:
                continue
            screens.append(Screen(
                key=key, title=step.action_target or key, url=step.url,
                thought=step.thought, action=step.action,
                action_target=step.action_target, blocked=not step.allowed,
            ))

        persona = personas.get(journey.persona_id)
        walks.append(
            Walk(
                journey_id=journey.id,
                persona_id=journey.persona_id,
                outcome=_outcome(journey),
                step_count=journey.step_count,
                screens=screens,
                persona_code=persona.code if persona else "",
                age_band=persona.age_band if persona else "",
                gender=persona.gender if persona else "",
                termination_reason=journey.termination_reason,
            )
        )

    return walks


# --------------------------------------------------------------------------- #
# 경로 카드
# --------------------------------------------------------------------------- #

#: 순위/모양으로 붙는 설명. Figma 의 문구를 그대로 쓴다.
LABEL_TOP = "가장 많이 사용한 경로"
LABEL_SECOND = "두 번째로 인기 있는 경로"
LABEL_SHORTEST = "가장 짧은 경로"
LABEL_LONGEST = "가장 많은 클릭 경로"
LABEL_TOP_DROP = "가장 많이 이탈한 경로"


def _label(rank: int, group: dict, shortest: int | None, longest: int | None, outcome: str) -> str:
    """설명은 붙일 근거가 있을 때만 붙인다.

    근거 없이 "가장 빠른 경로" 같은 말을 돌려가며 붙이면 화면은 그럴듯해 보이지만
    읽는 사람이 숫자와 대조했을 때 맞지 않는다.
    """
    if rank == 1:
        return LABEL_TOP_DROP if outcome == "drop" else LABEL_TOP
    if rank == 2:
        return LABEL_SECOND
    if shortest is not None and group["step_count"] == shortest:
        return LABEL_SHORTEST
    if longest is not None and group["step_count"] == longest:
        return LABEL_LONGEST
    return f"{rank}번째로 많은 경로"


def group_paths(walks: list[Walk], outcome: str) -> list[dict]:
    """같은 화면 순서를 밟은 사람끼리 묶어 인원 많은 순으로 준다."""
    picked = [w for w in walks if w.outcome == outcome and w.screens]
    if not picked:
        return []

    buckets: dict[tuple[str, ...], list[Walk]] = defaultdict(list)
    for walk in picked:
        buckets[walk.signature].append(walk)

    groups = []
    for signature, members in buckets.items():
        sample = members[0]
        # 스텝 수는 사람마다 다르다(같은 화면을 더 만졌을 수 있다). 대표값은 중앙값을 쓴다 —
        # 평균은 한 명이 40스텝을 헤매면 묶음 전체가 그 사람처럼 보인다.
        counts = sorted(w.step_count for w in members)
        median = counts[len(counts) // 2]
        groups.append(
            {
                "signature": list(signature),
                "persona_count": len(members),
                "step_count": median,
                "screens": [
                    {"key": s.key, "title": s.title, "url": s.url} for s in sample.screens
                ],
            }
        )

    groups.sort(key=lambda g: (-g["persona_count"], g["step_count"]))

    steps = [g["step_count"] for g in groups]
    shortest = min(steps) if len(groups) > 2 else None
    longest = max(steps) if len(groups) > 2 else None

    result = []
    for rank, group in enumerate(groups, start=1):
        result.append(
            {
                "rank": rank,
                "name": f"Path {rank}",
                "label": _label(rank, group, shortest, longest, outcome),
                "persona_count": group["persona_count"],
                "step_count": group["step_count"],
                "screens": group["screens"][:CARD_SCREENS],
                # 카드에 다 못 실은 화면 수. 0이면 화면이 "+0" 을 그리지 않는다.
                "more": max(0, len(group["screens"]) - CARD_SCREENS),
            }
        )
    return result


# --------------------------------------------------------------------------- #
# 네비게이션 다이어그램
# --------------------------------------------------------------------------- #

#: 열 개수 상한. 한 명이 40스텝을 헤매면 열이 40개가 되어 아무도 읽지 못한다.
MAX_COLUMNS = 12


def build_diagram(walks: list[Walk]) -> dict:
    """단계(열) × 화면(마디) 흐름도. 마디와 이음새마다 성공/이탈 인원을 함께 센다."""
    picked = [w for w in walks if w.screens]
    if not picked:
        return {"columns": [], "links": [], "total": 0}

    depth = min(MAX_COLUMNS, max(len(w.screens) for w in picked))

    nodes: dict[tuple[int, str], dict] = {}
    links: dict[tuple[str, str], dict] = {}

    for walk in picked:
        previous: str | None = None
        for position, screen in enumerate(walk.screens[:depth]):
            node_id = f"{position}:{screen.key}"
            node = nodes.setdefault(
                node_id,
                {
                    "id": node_id,
                    "column": position,
                    "key": screen.key,
                    "title": screen.title,
                    "count": 0,
                    "success": 0,
                    "drop": 0,
                },
            )
            node["count"] += 1
            if walk.outcome in ("success", "drop"):
                node[walk.outcome] += 1

            if previous is not None:
                link = links.setdefault(
                    (previous, node_id),
                    {"source": previous, "target": node_id, "count": 0, "success": 0, "drop": 0},
                )
                link["count"] += 1
                if walk.outcome in ("success", "drop"):
                    link[walk.outcome] += 1
            previous = node_id

    columns: list[list[dict]] = [[] for _ in range(depth)]
    for node in nodes.values():
        columns[node["column"]].append(node)
    for column in columns:
        column.sort(key=lambda n: -n["count"])

    return {
        "columns": [
            {"index": i, "label": "Start" if i == 0 else f"Step {i + 1}", "nodes": column}
            for i, column in enumerate(columns)
        ],
        "links": sorted(links.values(), key=lambda l: -l["count"]),
        "total": len(picked),
    }


# --------------------------------------------------------------------------- #
# 페르소나 이름
# --------------------------------------------------------------------------- #

#: 화면은 페르소나를 사람 이름으로 부른다(Figma 264:8753). DB 에는 코드(P001)만 있다.
#: 이름을 DB에 저장하면 같은 사람이 실행마다 다른 이름을 갖게 되므로, 코드에서 만든다 —
#: 코드가 같으면 이름도 항상 같다.
FAMILY = ("김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "서", "배", "전")
GIVEN = (
    "승빈", "도현", "지훈", "민성", "현우", "유진", "민혁", "하늘", "다은", "준호",
    "서연", "예린", "진우", "은지", "민재", "서윤", "태윤", "지우", "하린", "성민",
)


def display_name(code: str) -> str:
    """P001 → '이승빈'. 성 14 × 이름 20 = 280 가지라 100명이 겹치지 않는다."""
    try:
        index = int(code.lstrip("P"))
    except ValueError:
        index = abs(hash(code))
    return FAMILY[index % len(FAMILY)] + GIVEN[(index // len(FAMILY)) % len(GIVEN)]


def outcome_counts(walks: list[Walk]) -> Counter:
    return Counter(w.outcome for w in walks)


# --------------------------------------------------------------------------- #
# 스텝 상세 (막대를 눌렀을 때 뜨는 패널)
# --------------------------------------------------------------------------- #

#: DB의 4축(TraitCombo, 2단계) → 화면 라벨. agent-ux 자체 생성기의 축(5단계)과는 다르다
#: (server/app/pipeline_export.py 참고 — 같은 이유로 갈라져 있다).
AXIS_LABEL = {
    "reading_style": "읽기 스타일",
    "pace": "속도",
    "tech_literacy": "숙련도",
    "patience": "인내심",
}

END_LABEL = {
    "goal_achieved": "목표 달성",
    "gave_up": "포기",
    "step_budget_exhausted": "스텝 소진",
    "loop_detected": "제자리 맴돎",
    "budget_cap": "예산 상한",
    "runtime_error": "오류",
}


def walk_side_result(walk: Walk | None) -> dict | None:
    """PersonaSideResult 하나 — 정상판/결함판을 나란히 놓을 때 한쪽 결과."""
    if walk is None:
        return None
    return {
        "outcome": walk.outcome,
        "end_label": END_LABEL.get(walk.termination_reason or "", "진행 중"),
        "step_count": walk.step_count,
        "screens": [s.key for s in walk.screens],
    }


def compared_persona_rows(session: Session, run_baseline: Run | None, run_compare: Run) -> dict:
    """[화면] '페르소나' 탭 — 정상판(baseline)과 결함판(compare)을 코드로 짝짓는다.

    `ab.compare_projects`와 짝짓는 로직은 같지만, 여긴 같은 테스트의 Run 두 개를
    받는다 — 페르소나 테이블이 하나뿐이라 code 매칭이 항상 100% 들어맞는다
    (AB는 서로 다른 프로젝트라 인원표가 다르면 어긋날 수 있었다).

    `run_baseline`이 없으면(clean 실행을 아직 안 돌렸다) baseline은 전부 None —
    지어내지 않고 비워 둔다.
    """
    walks_baseline = (
        {w.persona_code: w for w in load_walks(session, None, run_id=run_baseline.id)}
        if run_baseline else {}
    )
    walks_compare = {w.persona_code: w for w in load_walks(session, None, run_id=run_compare.id)}
    personas = list(
        session.scalars(
            select(Persona).where(Persona.test_id == run_compare.test_id).order_by(Persona.code)
        )
    )

    items: list[dict] = []
    changed = 0
    exhausted = 0
    for persona in personas:
        baseline = walk_side_result(walks_baseline.get(persona.code))
        wc = walks_compare.get(persona.code)
        compare = walk_side_result(wc)
        is_changed = bool(baseline and compare and baseline["outcome"] != compare["outcome"])
        if is_changed:
            changed += 1
        if wc is not None and wc.termination_reason == "step_budget_exhausted":
            exhausted += 1

        items.append({
            "id": str(persona.id),
            "code": persona.code,
            "name": display_name(persona.code),
            "age_band": persona.age_band,
            "gender": persona.gender,
            "outcome": compare["outcome"] if compare else None,
            "step_count": compare["step_count"] if compare else None,
            "baseline": baseline,
            "compare": compare,
            "changed": is_changed,
        })

    return {
        "total": len(items),
        "items": items,
        "changed": changed,
        "exhausted": exhausted,
        "baseline_run": str(run_baseline.id) if run_baseline else None,
        "compare_run": str(run_compare.id),
        "axes": AXIS_LABEL,
    }


def _step_persona(walk: Walk, screen: Screen | None) -> dict:
    return {
        "id": str(walk.persona_id),
        "code": walk.persona_code,
        "label": display_name(walk.persona_code),
        # DB 특성은 2단계 문자열("높음"/"낮음" 등)이라 화면이 기대하는 1~5단계 숫자로
        # 옮길 근거가 없다 — 지어내지 않고 비워 둔다.
        "traits": {},
        "age_band": walk.age_band,
        "gender": walk.gender,
        # StepPersona.outcome은 success/drop 둘뿐이다. 아직 진행 중이거나(other)
        # 스텝을 다 쓰고 끝난 사람도 여기서는 drop 쪽으로 뭉뚱그린다 — 성공은 아니었다는
        # 사실만 남기고, 정확한 사유는 end_label 에 따로 적는다.
        "outcome": "success" if walk.outcome == "success" else "drop",
        "end_label": END_LABEL.get(walk.termination_reason or "", "진행 중"),
        "total_steps": walk.step_count,
        "thought": (screen.thought if screen else None) or "",
        "action": (screen.action if screen else None) or "",
        "target": (screen.action_target if screen else None) or "",
        "blocked": bool(screen.blocked) if screen else False,
    }


def build_steps_payload(walks: list[Walk], test_name: str) -> dict:
    """스텝별 막대 + 필름스트립. build_diagram 과 같은 (position, screen_key) 서명을 쓴다 —
    두 화면의 숫자가 어긋나면 안 되기 때문이다.

    클릭 좌표·스크린샷은 DB에 없어서(찍는 코드가 없다) clicks/screen_clicks 는 빈 배열,
    shot 은 null 로 정직하게 비워 둔다. replay(전체 여정 재생)도 같은 이유로 뺀다 —
    화면 타입에서 둘 다 선택적(optional) 필드라 없어도 깨지지 않는다.
    """
    picked = [w for w in walks if w.screens]
    if not picked:
        return {
            "steps": {}, "filmstrip": [], "sentences": SENTENCES, "axes": AXIS_LABEL,
            "test_name": test_name,
        }

    depth = min(MAX_COLUMNS, max(len(w.screens) for w in picked))

    by_node: dict[str, list[tuple[Walk, Screen]]] = defaultdict(list)
    node_title: dict[str, str] = {}
    for walk in picked:
        for position, screen in enumerate(walk.screens[:depth]):
            node_id = f"{position}:{screen.key}"
            by_node[node_id].append((walk, screen))
            node_title.setdefault(node_id, screen.title)

    steps: dict[str, dict] = {}
    for node_id, here in by_node.items():
        position = int(node_id.split(":", 1)[0])
        here_ids = {w.persona_id for w, _ in here}
        elsewhere = [w for w in picked if len(w.screens) > position and w.persona_id not in here_ids]
        finished = [w for w in picked if len(w.screens) <= position and w.persona_id not in here_ids]

        steps[node_id] = {
            "id": node_id,
            "step": position + 1,
            "screen": node_id.split(":", 1)[1],
            "title": node_title[node_id],
            "count": len(here),
            "shot": None,
            "clicks": [],
            "screen_clicks": [],
            "wasted": 0,
            "personas": [_step_persona(w, s) for w, s in here],
            "elsewhere": [_step_persona(w, None) for w in elsewhere],
            "finished": [_step_persona(w, None) for w in finished],
            "total": len(picked),
        }

    filmstrip: list[dict] = []
    for position in range(depth):
        nodes_here = [s for nid, s in steps.items() if int(nid.split(":", 1)[0]) == position]
        if not nodes_here:
            continue
        top = max(nodes_here, key=lambda n: n["count"])
        others = sum(n["count"] for n in nodes_here) - top["count"]
        filmstrip.append({
            "step": position + 1, "id": top["id"], "title": top["title"],
            "count": top["count"], "shot": None, "others": others,
        })

    return {
        "steps": steps,
        "filmstrip": filmstrip,
        "sentences": SENTENCES,
        "axes": AXIS_LABEL,
        "test_name": test_name,
    }
