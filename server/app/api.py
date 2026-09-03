"""React 화면이 쓰는 읽기/쓰기 엔드포인트. 화면 하나가 엔드포인트 하나에 대응한다."""

from __future__ import annotations

import datetime as dt
import re
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .categories import CATEGORIES, normalize as normalize_category
from .connectivity import check_as_dict
from .db import get_session
from .estimates import DEFAULT_PAGE_COUNT, estimate
from .journeys import (
    DROP_REASONS,
    build_diagram,
    build_replay,
    build_steps_payload,
    compared_persona_rows,
    group_paths,
    load_walks,
    outcome_counts,
)
from . import ab, auth, orchestrate, static_scan
from .missions import analyze_as_dict
from .models import (
    AbTest,
    Goal,
    Journey,
    Mission,
    Persona,
    PersonaSpec,
    Project,
    Run,
    RunScore,
    SiteMap,
    SiteVariant,
    Test,
    User,
)
from .personas import PersonaBuildError, assemble, popup_reachable_count
from .thumbnails import capture as capture_thumbnail

router = APIRouter(prefix="/api")


class ConnectivityIn(BaseModel):
    url: str


@router.post("/connectivity/check")
def connectivity_check(body: ConnectivityIn, user: User = Depends(auth.get_current_user)) -> dict:
    """[화면] 새 프로젝트 · 새 테스트의 '연결하기'.

    DB를 쓰지 않는다 — 주소를 저장하기 전에 눌러볼 수 있어야 한다. 프로젝트
    데이터를 다루진 않지만 로그인은 요구한다 — 안 그러면 비로그인 상태로 서버가
    아무 주소나 대신 열어주는 통로가 된다.
    """
    return check_as_dict(body.url)


@router.get("/thumbnail")
async def thumbnail(url: str, user: User = Depends(auth.get_current_user)) -> Response:
    """[화면] 프로젝트 카드·테스트 목록의 웹 썸네일.

    사이트 첫 화면을 서버에서 PNG 로 찍어 준다. 프론트는 <img> 하나로 받으므로
    카드 안에서 무언가 움직일 여지가 없다. 찍지 못하면 404 — 화면이 기본 이미지로
    떨어진다. DB를 쓰지 않지만 로그인은 요구한다(connectivity/check와 같은 이유).
    """
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="http(s) 주소만 찍을 수 있어요")

    png = await capture_thumbnail(url)
    if png is None:
        raise HTTPException(status_code=404, detail="썸네일을 찍지 못했어요")

    return Response(
        content=png,
        media_type="image/png",
        # 캐시는 서버에도 있지만, 목록을 오갈 때마다 다시 받아올 이유가 없다.
        headers={"Cache-Control": "public, max-age=3600"},
    )


_SAFE_SHOTS_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


def _safe_shots_dir(stem: str) -> Path:
    """stem을 경로 하나로. 검사에 실패하면(위로 나가거나 이상한 문자) 400."""
    if not _SAFE_SHOTS_SEGMENT.match(stem):
        raise HTTPException(status_code=400, detail="잘못된 주소예요")
    base = orchestrate.SHOTS_DIR.resolve()
    target = (orchestrate.SHOTS_DIR / stem).resolve()
    if base not in target.parents and target != base:
        raise HTTPException(status_code=400, detail="잘못된 주소예요")
    return target


@router.get("/shots/{stem}")
def shots_gallery(stem: str) -> Response:
    """[화면] "답사자가 본 화면 보기" — 답사(survey.py) 중 찍힌 스크린샷 갤러리.

    로그인을 요구하지 않는다 — 새 창으로 열거나(target="_blank") <img>로
    받는 통로는 로그인 토큰(Bearer)을 실어 보낼 방법이 없다(/api/thumbnail이
    똑같이 겪는 제약). 여기서 보여주는 것도 이미 공개된 페이지를 답사가
    찍어 둔 사진이라, 로그인 없이 열어도 새로 새는 정보가 없다.
    """
    d = _safe_shots_dir(stem)
    files = sorted(p.name for p in d.glob("*.png")) if d.is_dir() else []
    if not files:
        body = '<p style="color:#999">아직 답사 스크린샷이 없습니다.</p>'
    else:
        body = "".join(
            f'<figure><img src="/api/shots/{stem}/{f}" loading="lazy">'
            f'<figcaption>{f}</figcaption></figure>'
            for f in files
        )
    html = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<title>답사자가 본 화면 · {stem}</title>"
        "<style>"
        "body{font-family:system-ui,sans-serif;background:#111;color:#eee;margin:0;padding:24px}"
        "h1{font-size:16px;font-weight:600}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin-top:16px}"
        "figure{margin:0}"
        "img{width:100%;border-radius:8px;display:block;background:#222}"
        "figcaption{font-size:12px;color:#999;margin-top:6px;word-break:break-all}"
        "</style></head><body>"
        f"<h1>{stem}</h1>"
        f'<div class="grid">{body}</div>'
        "</body></html>"
    )
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.get("/shots/{stem}/{filename}")
def shots_image(stem: str, filename: str) -> Response:
    if not _SAFE_SHOTS_SEGMENT.match(filename) or not filename.endswith(".png"):
        raise HTTPException(status_code=400, detail="잘못된 파일명이에요")
    fp = _safe_shots_dir(stem) / filename
    if not fp.is_file():
        raise HTTPException(status_code=404, detail="스크린샷을 찾을 수 없어요")
    return Response(
        content=fp.read_bytes(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


class MissionAnalyzeIn(BaseModel):
    prompt: str


@router.post("/missions/analyze")
def analyze_mission(body: MissionAnalyzeIn, user: User = Depends(auth.get_current_user)) -> dict:
    """[화면] 미션 설정 — 문장을 검사하고 성공 기준을 만들어 준다.

    DB를 쓰지 않는다. 타이핑 중에도 불러야 하기 때문이다.
    """
    return analyze_as_dict(body.prompt)


# --------------------------------------------------------------------------- #
# 스키마
# --------------------------------------------------------------------------- #

class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str

    @field_validator("category")
    @classmethod
    def known_category(cls, value: str) -> str:
        # 목록 밖 값을 받아주면 카테고리별 묶기가 그 순간부터 어긋난다.
        resolved = normalize_category(value)
        if resolved is None:
            raise ValueError(f"카테고리는 {', '.join(CATEGORIES)} 중 하나여야 합니다")
        return resolved
    source: str = "web_link"
    device_preset: str = "16:9 데스크탑"
    target_url: str
    flow_map_path: str | None = None
    #: 연결 검사에서 받은 값. 카드 썸네일을 실제 화면으로 띄울지 판단한다.
    preview_embeddable: bool = False


def _as_utc(value: dt.datetime) -> dt.datetime:
    """시간대 없는 값은 UTC로 본다.

    SQLite 는 timestamptz 를 모르기 때문에 naive 로 돌아온다. 그대로 내보내면
    브라우저가 로컬 시각으로 읽어 KST 기준 9시간 어긋난 "9시간 전"이 찍힌다.
    """
    return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)


class ProjectCard(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    test_count: int
    last_activity_at: dt.datetime
    preview_url: str | None = None
    preview_embeddable: bool = False
    # 데모용 "지울 수 없는 프로젝트" 개념은 서버에 없다 — 항상 지울 수 있다.
    removable: bool = True

    @field_validator("last_activity_at")
    @classmethod
    def to_utc(cls, value: dt.datetime) -> dt.datetime:
        return _as_utc(value)


class TestIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    device: str
    target_url: str


class MissionIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=200)
    success_criteria: str
    auto_detect: bool = True
    expect: str = ""


class PersonaSpecIn(BaseModel):
    age_band: str
    total: int = Field(ge=0)
    female_percent: int = Field(ge=0, le=100, default=50)
    gender_agnostic: bool = False
    enabled: bool = True


class TestStats(BaseModel):
    test_id: uuid.UUID
    name: str
    created_at: dt.datetime
    persona_count: int
    success_rate: float | None
    drop_rate: float | None

    @field_validator("created_at")
    @classmethod
    def to_utc(cls, value: dt.datetime) -> dt.datetime:
        return _as_utc(value)


# --------------------------------------------------------------------------- #
# [화면] 프로젝트 목록
# --------------------------------------------------------------------------- #

@router.get("/projects", response_model=list[ProjectCard])
def list_projects(
    session: Session = Depends(get_session), user: User = Depends(auth.get_current_user)
) -> list[ProjectCard]:
    rows = session.execute(
        select(
            Project.id,
            Project.name,
            Project.category,
            Project.preview_url,
            Project.preview_embeddable,
            func.count(Test.id).label("test_count"),
            func.coalesce(func.max(Test.created_at), Project.created_at).label("last_activity_at"),
        )
        .outerjoin(Test, Test.project_id == Project.id)
        .where(Project.user_id == user.id)
        .group_by(Project.id)
        .order_by(func.coalesce(func.max(Test.created_at), Project.created_at).desc())
    ).all()

    return [ProjectCard.model_validate(row._mapping) for row in rows]


@router.post("/projects", response_model=ProjectCard, status_code=201)
def create_project(
    body: ProjectIn,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> ProjectCard:
    project = Project(
        user_id=user.id,
        name=body.name,
        category=body.category,
        source=body.source,
        device_preset=body.device_preset,
        flow_map_path=body.flow_map_path,
        preview_url=body.target_url,
        preview_embeddable=body.preview_embeddable,
    )
    session.add(project)
    session.flush()

    # 기획서 5장: 대조군 없이는 정밀도를 잴 수 없다.
    # 프로젝트를 만들 때 두 변형을 함께 만들어, clean 없는 프로젝트가 생기지 않게 한다.
    for key, label, is_control in (("clean", "정상판", True), ("flawed", "결함판", False)):
        session.add(
            SiteVariant(
                project_id=project.id,
                key=key,
                label=label,
                base_url=f"{body.target_url.rstrip('/')}/{key}/",
                is_control=is_control,
                cart_storage_key=f"moji_cart_{key}",
            )
        )

    session.commit()
    return ProjectCard(
        id=project.id,
        name=project.name,
        category=project.category,
        test_count=0,
        last_activity_at=project.created_at,
        preview_url=project.preview_url,
        preview_embeddable=project.preview_embeddable,
    )


# --------------------------------------------------------------------------- #
# 소유자 확인 헬퍼 — project_id/test_id/run_id로 여는 자리는 전부 이걸 거친다.
# 존재는 하는데 남의 것이어도 404다 — "있는데 못 봄"과 "아예 없음"을 구분해 주면
# 남의 프로젝트 id가 유효한지 캐는 데 쓰인다.
# --------------------------------------------------------------------------- #

def _owned_project(project_id: uuid.UUID, user: User, session: Session) -> Project:
    project = session.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    return project


def _owned_test(test_id: uuid.UUID, user: User, session: Session) -> Test:
    test = _load_test(test_id, session)
    _owned_project(test.project_id, user, session)
    return test


def _owned_run(run_id: uuid.UUID, user: User, session: Session) -> Run:
    run = _load_run(run_id, session)
    _owned_test(run.test_id, user, session)
    return run


# --------------------------------------------------------------------------- #
# [화면] 프로젝트 상세
# --------------------------------------------------------------------------- #

@router.get("/projects/{project_id}")
def get_project(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    project = _owned_project(project_id, user, session)

    stats = session.execute(
        select(
            func.count(func.distinct(Test.id)).label("test_count"),
            func.count(Journey.id).label("journeys"),
            func.count(Journey.id).filter(Journey.goal_achieved.is_(True)).label("achieved"),
            func.count(Journey.id)
            .filter(Journey.termination_reason.in_(DROP_REASONS))
            .label("dropped"),
        )
        .select_from(Test)
        .outerjoin(Run, Run.test_id == Test.id)
        .outerjoin(Journey, Journey.run_id == Run.id)
        .where(Test.project_id == project_id)
    ).one()

    journeys = stats.journeys or 0
    return {
        "id": str(project.id),
        "name": project.name,
        "category": project.category,
        "device_preset": project.device_preset,
        "viewport": {"w": project.viewport_w, "h": project.viewport_h},
        "preview_url": project.preview_url,
        "preview_embeddable": project.preview_embeddable,
        "test_count": stats.test_count or 0,
        # 여정이 하나도 없으면 비율은 0이 아니라 '아직 없음'이다. null 로 보내야
        # 화면이 "0.0%"라는 거짓 수치를 그리지 않는다.
        "success_rate": round(100 * stats.achieved / journeys, 1) if journeys else None,
        "drop_rate": round(100 * stats.dropped / journeys, 1) if journeys else None,
        "variants": [
            {"key": v.key, "label": v.label, "base_url": v.base_url, "is_control": v.is_control}
            for v in project.variants
        ],
    }


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    """이 자리에서 만든 프로젝트를 지운다.

    데모용 "지울 수 없는 프로젝트" 개념은 프론트 목업에만 있었고 서버 쪽엔 애초에
    없다(확인함) — 그래서 여기선 항상 지운다. `Project`의 자식 관계가 전부
    `cascade="all, delete-orphan"`이라(`models.py`) 하나만 지우면 그 아래
    SiteVariant/Test/Mission/Goal/Persona/Run/Journey/Step 까지 같이 지워진다.
    """
    project = _owned_project(project_id, user, session)
    session.delete(project)
    session.commit()
    return {"ok": True}


@router.get("/projects/{project_id}/tests", response_model=list[TestStats])
def list_tests(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> list[TestStats]:
    _owned_project(project_id, user, session)
    rows = session.execute(
        select(
            Test.id.label("test_id"),
            Test.name,
            Test.created_at,
            func.count(Journey.id).label("persona_count"),
            (
                100.0
                * func.count(Journey.id).filter(Journey.goal_achieved.is_(True))
                / func.nullif(func.count(Journey.id), 0)
            ).label("success_rate"),
            # 이탈률 = 포기 + 맴돌다 중단. 예산 상한으로 우리가 끊은 것은 세지 않는다
            # (기획서 4장: 그것을 '포기'로 적으면 통계가 오염된다).
            (
                100.0
                * func.count(Journey.id).filter(
                    Journey.termination_reason.in_(DROP_REASONS)
                )
                / func.nullif(func.count(Journey.id), 0)
            ).label("drop_rate"),
        )
        .outerjoin(Run, Run.test_id == Test.id)
        .outerjoin(Journey, Journey.run_id == Run.id)
        .where(Test.project_id == project_id)
        .group_by(Test.id)
        .order_by(Test.created_at.desc())
    ).all()

    return [TestStats.model_validate(row._mapping) for row in rows]


# --------------------------------------------------------------------------- #
# [화면] 새 테스트 · 미션 · 페르소나
# --------------------------------------------------------------------------- #

@router.post("/projects/{project_id}/tests", status_code=201)
def create_test(
    project_id: uuid.UUID,
    body: TestIn,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    _owned_project(project_id, user, session)
    test = Test(project_id=project_id, **body.model_dump())
    session.add(test)
    session.commit()
    return {"id": test.id}


@router.put("/tests/{test_id}/mission")
def upsert_mission(
    test_id: uuid.UUID,
    body: MissionIn,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    _owned_test(test_id, user, session)
    mission = session.scalar(select(Mission).where(Mission.test_id == test_id))
    if mission is None:
        mission = Mission(test_id=test_id, **body.model_dump())
        session.add(mission)
    else:
        for key, value in body.model_dump().items():
            setattr(mission, key, value)
    session.flush()  # mission.id 확보

    # Goal은 미션당 정확히 1개(idx=0)다. 페르소나마다 다른 목표를 주지 않는다 —
    # 100명 전원이 이 미션 문장 하나를 좇고, 서로 다른 결과는 특성 조합에서 나온다.
    # idx!=0 삭제는 옛 방식(목표 11개)의 잔여 행이 남아 있어도 정리되도록 하는 방어책이다.
    session.execute(delete(Goal).where(Goal.mission_id == mission.id, Goal.idx != 0))
    goal = session.scalar(select(Goal).where(Goal.mission_id == mission.id, Goal.idx == 0))
    if goal is None:
        session.add(Goal(mission_id=mission.id, idx=0, prompt=mission.prompt))
    else:
        goal.prompt = mission.prompt

    session.commit()
    return {"id": mission.id}


@router.put("/tests/{test_id}/persona-specs")
def replace_persona_specs(
    test_id: uuid.UUID,
    body: list[PersonaSpecIn],
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    _owned_test(test_id, user, session)
    existing = {
        s.age_band: s
        for s in session.scalars(select(PersonaSpec).where(PersonaSpec.test_id == test_id))
    }
    for item in body:
        row = existing.get(item.age_band)
        if row is None:
            session.add(PersonaSpec(test_id=test_id, **item.model_dump()))
        else:
            for key, value in item.model_dump().items():
                setattr(row, key, value)

    session.commit()
    return {"total": sum(i.total for i in body if i.enabled)}


@router.post("/tests/{test_id}/personas/assemble")
def build_personas(
    test_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    _owned_test(test_id, user, session)
    try:
        personas = assemble(session, test_id)
    except PersonaBuildError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    session.commit()
    return {
        "count": len(personas),
        # 이 수가 0이면 D-26(10초 팝업)은 '못 잡은 것'이 아니라 '마주친 적 없는 것'이 된다.
        "popup_reachable": popup_reachable_count(personas),
    }


# --------------------------------------------------------------------------- #
# [화면] 확인
# --------------------------------------------------------------------------- #

@router.get("/tests/{test_id}/review")
def review(
    test_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    test = _owned_test(test_id, user, session)

    mission = session.scalar(select(Mission).where(Mission.test_id == test_id))
    specs = list(session.scalars(select(PersonaSpec).where(PersonaSpec.test_id == test_id)))
    persona_count = session.scalar(
        select(func.count(Persona.id)).where(Persona.test_id == test_id)
    ) or sum(s.total for s in specs if s.enabled)

    # 답사가 확인한 화면 수가 있으면 그 값으로, 없으면 기본값으로 추정한다.
    page_count = session.scalar(
        select(SiteMap.screens_found)
        .join(SiteVariant, SiteVariant.id == SiteMap.site_variant_id)
        .where(SiteVariant.project_id == test.project_id)
        .order_by(SiteMap.created_at.desc())
        .limit(1)
    )

    est = estimate(persona_count, page_count or DEFAULT_PAGE_COUNT)
    return {
        "project": {"id": str(test.project_id)},
        "test": {"id": str(test.id), "name": test.name, "device": test.device},
        "mission": None if mission is None else {
            "prompt": mission.prompt,
            "success_criteria": mission.success_criteria,
            "expect": mission.expect,
        },
        "personas": {
            "total": persona_count,
            "breakdown": [
                {"age_band": s.age_band, "total": s.total, **s.split()}
                for s in specs
                if s.enabled and s.total > 0
            ],
        },
        "estimate": {
            "minutes": est.minutes,
            "tokens": est.tokens,
            "page_count": est.page_count,
            "vision_calls": est.vision_calls,
            "usd": est.usd,
            # 화면에서 '약'을 붙일지 결정하는 값. 실측 전에는 추정치임을 밝혀야 한다.
            "measured": est.measured,
            "formula": est.formula,
        },
    }


# --------------------------------------------------------------------------- #
# 실행
# --------------------------------------------------------------------------- #

@router.post("/tests/{test_id}/runs", status_code=201)
def start_run(
    test_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    """[화면] 확인의 '테스트 하기'.

    실행 한 건을 열고 페르소나별 여정 자리를 만든 뒤, 별도 스레드에서 실제 탐색
    파이프라인(agent-ux/run.py)을 돌린다(`orchestrate.start_pipeline_run`) — 진행률은
    그 스레드가 채우는 Journey들로 `/runs/active`에 드러난다. 응답은 파이프라인이
    끝나길 기다리지 않고 바로 나간다.
    """
    test = _owned_test(test_id, user, session)

    try:
        personas = assemble(session, test_id)
    except PersonaBuildError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    flawed = session.scalar(
        select(SiteVariant).where(
            SiteVariant.project_id == test.project_id, SiteVariant.is_control.is_(False)
        )
    )
    if flawed is None:
        raise HTTPException(status_code=422, detail="결함판 변형이 없습니다")
    clean = session.scalar(
        select(SiteVariant).where(
            SiteVariant.project_id == test.project_id, SiteVariant.is_control.is_(True)
        )
    )

    # 화면에서 시작하는 실행은 A(결함판)다. B(정상판)는 대조군 — 같은 100명을
    # 그대로 다시 돌려서, 결과 화면의 baseline(정상판)/compare(결함판)를 채운다.
    # 같은 팔을 두 번 열면 어느 쪽이 발표 수치인지 알 수 없어서 arm은 고정한다.
    run_a = _open_run(session, test_id, "A", flawed.id, personas)
    run_b = _open_run(session, test_id, "B", clean.id, personas) if clean else None

    session.commit()

    threading.Thread(target=orchestrate.start_pipeline_run, args=(run_a.id,), daemon=True).start()
    if run_b is not None:
        threading.Thread(
            target=orchestrate.start_pipeline_run, args=(run_b.id,), daemon=True
        ).start()

    return {"run_id": str(run_a.id), "persona_count": run_a.persona_count, "status": run_a.status}


def _open_run(
    session: Session, test_id: uuid.UUID, arm: str, site_variant_id: uuid.UUID,
    personas: list[Persona],
) -> Run:
    """arm 하나를 열고(있으면 재사용) 페르소나별 여정 자리를 만든다. 커밋은 호출부가 한다."""
    run = session.scalar(select(Run).where(Run.test_id == test_id, Run.arm == arm))
    if run is None:
        run = Run(test_id=test_id, site_variant_id=site_variant_id, arm=arm, map_enabled=False)
        session.add(run)

    run.persona_count = len(personas)
    run.status = "running"
    run.started_at = dt.datetime.now(dt.timezone.utc)
    # 기획서 7장: 2명 이상은 예상 호출 수를 보여준 뒤 확인을 받는다.
    # 확인 화면을 거쳐 눌린 버튼이므로 그 사실을 여기 남긴다.
    run.confirmed_at = dt.datetime.now(dt.timezone.utc)
    session.flush()

    existing = {
        j.persona_id for j in session.scalars(select(Journey).where(Journey.run_id == run.id))
    }
    for persona in personas:
        if persona.id not in existing:
            session.add(Journey(run_id=run.id, persona_id=persona.id))

    return run


@router.get("/runs/active")
def active_run(
    session: Session = Depends(get_session), user: User = Depends(auth.get_current_user)
) -> dict | None:
    """[화면] 진행중 배너. 돌고 있는 실행이 없으면 null 을 준다.

    내가 소유한 프로젝트에서 도는 실행만 본다 — 안 그러면 남이 지금 뭘 테스트
    중인지가 진행률 배너로 새어 나간다.
    """
    row = session.execute(
        select(Run, Test, Project)
        .join(Test, Test.id == Run.test_id)
        .join(Project, Project.id == Test.project_id)
        .where(Run.status == "running", Project.user_id == user.id)
        .order_by(Run.started_at.desc())
        .limit(1)
    ).first()

    if row is None:
        return None

    run, test, project = row

    # clean(A)/flawed(B) 실행이 거의 동시에 돈다 — 같은 test의 running 행을 다
    # 합쳐서 보여준다. 안 그러면 나중에 시작한 쪽 진행률만 반쪽으로 보인다.
    running_runs = list(
        session.scalars(select(Run).where(Run.test_id == test.id, Run.status == "running"))
    )
    run_ids = [r.id for r in running_runs]
    done = session.scalar(
        select(func.count(Journey.id)).where(
            Journey.run_id.in_(run_ids), Journey.finished_at.is_not(None)
        )
    ) or 0
    total = sum(r.persona_count for r in running_runs)

    return {
        "run_id": str(run.id),
        "project_id": str(project.id),
        "project_name": project.name,
        "test_name": test.name,
        "done": done,
        "total": total,
    }


# --------------------------------------------------------------------------- #
# [화면] 테스트 상세 — 미션 경로 · 다이어그램 · 페르소나
# --------------------------------------------------------------------------- #

def _load_test(test_id: uuid.UUID, session: Session) -> Test:
    test = session.get(Test, test_id)
    if test is None:
        raise HTTPException(status_code=404, detail="테스트를 찾을 수 없습니다")
    return test


def _primary_run(test_id: uuid.UUID, session: Session) -> Run | None:
    """이 테스트의 '탐색 대상' 실행(결함판, arm A). 화면이 기본으로 보는 결과다."""
    return session.scalar(select(Run).where(Run.test_id == test_id, Run.arm == "A"))


def _control_run(test_id: uuid.UUID, session: Session) -> Run | None:
    """이 테스트의 대조군 실행(정상판, arm B). 아직 안 돌렸으면 None."""
    return session.scalar(select(Run).where(Run.test_id == test_id, Run.arm == "B"))


@router.get("/tests/{test_id}")
def test_detail(
    test_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    """상단 제목 · 미션 문장 · 지표 세 칸.

    A(결함판) 실행 하나만 본다 — B(정상판)까지 합치면 두 변형의 여정이 섞여
    성공률·다이어그램이 다 틀어진다(정상판은 대조군일 뿐 탐색 대상이 아니다).
    """
    test = _owned_test(test_id, user, session)
    project = session.get(Project, test.project_id)
    mission = session.scalar(select(Mission).where(Mission.test_id == test_id))
    primary = _primary_run(test_id, session)

    stats = (
        session.execute(
            select(
                func.count(Journey.id).label("journeys"),
                func.count(Journey.id).filter(Journey.goal_achieved.is_(True)).label("achieved"),
                func.count(Journey.id)
                .filter(Journey.termination_reason.in_(DROP_REASONS))
                .label("dropped"),
                func.avg(Journey.step_count)
                .filter(Journey.goal_achieved.is_(True))
                .label("success_steps"),
            )
            .select_from(Journey)
            .where(Journey.run_id == primary.id)
        ).one()
        if primary is not None
        else None
    )

    journeys = stats.journeys if stats else 0
    persona_total = session.scalar(
        select(func.count(Persona.id)).where(Persona.test_id == test_id)
    ) or 0

    return {
        "id": str(test.id),
        "name": test.name,
        "device": test.device,
        "created_at": _as_utc(test.created_at),
        "project": {
            "id": str(test.project_id),
            "name": project.name if project else "",
            "preview_url": project.preview_url if project else None,
        },
        "mission": None if mission is None else {
            "prompt": mission.prompt,
            "success_criteria": mission.success_criteria,
            "expect": mission.expect,
        },
        "persona_total": persona_total,
        "journey_count": journeys,
        # 여정이 없으면 0% 가 아니라 '아직 없음'이다 — 프로젝트 상세와 같은 규칙.
        "success_rate": round(100 * stats.achieved / journeys, 1) if journeys else None,
        "drop_rate": round(100 * stats.dropped / journeys, 1) if journeys else None,
        "avg_success_steps": round(float(stats.success_steps), 2) if stats and stats.success_steps else None,
    }


@router.get("/tests/{test_id}/paths")
def test_paths(
    test_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    """'경로' 보기. 성공/이탈 두 묶음을 한 번에 준다 — 탭을 눌러도 다시 부르지 않는다."""
    _owned_test(test_id, user, session)
    primary = _primary_run(test_id, session)
    walks = load_walks(session, None, run_id=primary.id) if primary else []
    counts = outcome_counts(walks)
    total = len(walks)

    def share(kind: str) -> dict:
        count = counts.get(kind, 0)
        return {"count": count, "percent": round(100 * count / total) if total else 0}

    return {
        "total": total,
        "success": share("success"),
        "drop": share("drop"),
        "paths": {
            "success": group_paths(walks, "success"),
            "drop": group_paths(walks, "drop"),
        },
    }


@router.get("/tests/{test_id}/diagram")
def test_diagram(
    test_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    """'다이어그램' 보기. 같은 여정을 단계 × 화면으로 펼친다."""
    _owned_test(test_id, user, session)
    primary = _primary_run(test_id, session)
    return build_diagram(load_walks(session, None, run_id=primary.id) if primary else [])


@router.get("/tests/{test_id}/personas")
def test_personas(
    test_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    """사이드바 '페르소나' 탭. 정상판(baseline)과 결함판(compare)을 나란히 준다."""
    _owned_test(test_id, user, session)
    primary = _primary_run(test_id, session)
    if primary is None:
        return {"total": 0, "items": []}
    control = _control_run(test_id, session)
    return compared_persona_rows(session, control, primary)


@router.get("/tests/{test_id}/steps")
def test_steps(
    test_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    """막대를 눌렀을 때 뜨는 스텝 상세 + 필름스트립."""
    test = _owned_test(test_id, user, session)
    primary = _primary_run(test_id, session)
    walks = load_walks(session, None, run_id=primary.id) if primary else []
    replay = build_replay(session, primary) if primary else {}
    return build_steps_payload(walks, test.name, replay)


# --------------------------------------------------------------------------- #
# 방금 로컬에서 돌린 실행(run_id 기준) — 테스트로 저장되기 전에도 결과를 본다
# --------------------------------------------------------------------------- #

def _load_run(run_id: uuid.UUID, session: Session) -> Run:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="실행을 찾을 수 없습니다")
    return run


def _sibling_run(run: Run, session: Session) -> Run | None:
    """짝인 반대 변형 실행. A(결함판)면 B(정상판)를, B면 A를 찾는다."""
    other_arm = "B" if run.arm == "A" else "A"
    return session.scalar(select(Run).where(Run.test_id == run.test_id, Run.arm == other_arm))


@router.get("/live/{run_id}")
def live_detail(
    run_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    run = _owned_run(run_id, user, session)
    return test_detail(run.test_id, session, user)


@router.get("/live/{run_id}/paths")
def live_paths(
    run_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    run = _owned_run(run_id, user, session)
    walks = load_walks(session, None, run_id=run.id)
    counts = outcome_counts(walks)
    total = len(walks)

    def share(kind: str) -> dict:
        count = counts.get(kind, 0)
        return {"count": count, "percent": round(100 * count / total) if total else 0}

    return {
        "total": total,
        "success": share("success"),
        "drop": share("drop"),
        "paths": {"success": group_paths(walks, "success"), "drop": group_paths(walks, "drop")},
    }


@router.get("/live/{run_id}/diagram")
def live_diagram(
    run_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    run = _owned_run(run_id, user, session)
    return build_diagram(load_walks(session, None, run_id=run.id))


@router.get("/live/{run_id}/personas")
def live_personas(
    run_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    run = _owned_run(run_id, user, session)
    sibling = _sibling_run(run, session)
    if run.arm == "A":
        return compared_persona_rows(session, sibling, run)
    if sibling is None:
        return {"total": 0, "items": []}
    return compared_persona_rows(session, run, sibling)


@router.get("/live/{run_id}/steps")
def live_steps(
    run_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    run = _owned_run(run_id, user, session)
    test = _load_test(run.test_id, session)
    return build_steps_payload(
        load_walks(session, None, run_id=run.id), test.name, build_replay(session, run)
    )


@router.post("/runs/{run_id}/score")
async def score_run(
    run_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    """정적 분석 채점기(20건)를 돌려 Finding/FindingMatch를 채우고 집계한다.

    화면 계약은 아직 없다 — `/tests/{id}/ablation`이 이미 RunScore를 읽으므로,
    채점이 끝나면 그 화면에 자동으로 숫자가 뜬다.
    """
    _owned_run(run_id, user, session)
    summary = await static_scan.run_static_scan(session, run_id)
    score = summary.score
    session.commit()
    return {
        "findings": summary.hits,
        "matched": summary.matched,
        "unmatched": summary.unmatched,
        "defects_found": score.defects_found,
        "defects_total": score.defects_total,
        "recall": float(score.recall) if score.recall is not None else None,
        "precision": float(score.precision) if score.precision is not None else None,
        "fp_rate": float(score.fp_rate) if score.fp_rate is not None else None,
    }


# --------------------------------------------------------------------------- #
# 검증 계획 A/B/C/D
# --------------------------------------------------------------------------- #

@router.get("/tests/{test_id}/ablation")
def ablation(
    test_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> list[dict]:
    _owned_test(test_id, user, session)
    rows = session.execute(
        select(Run.arm, SiteVariant.key, Run.map_enabled, Run.status, RunScore)
        .join(SiteVariant, SiteVariant.id == Run.site_variant_id)
        .outerjoin(RunScore, RunScore.run_id == Run.id)
        .where(Run.test_id == test_id)
        .order_by(Run.arm)
    ).all()

    return [
        {
            "arm": arm,
            "variant": variant,
            "map_enabled": map_enabled,
            "status": status,
            "recall": float(score.recall) if score and score.recall is not None else None,
            "precision": float(score.precision) if score and score.precision is not None else None,
            "fp_rate": float(score.fp_rate) if score and score.fp_rate is not None else None,
        }
        for arm, variant, map_enabled, status, score in rows
    ]


# --------------------------------------------------------------------------- #
# 계정 인증 (회원가입 / 로그인)
#
# 1단계: 인증 자체만. Project/Test를 사용자별로 나누는 것(소유권)은 다음 단계 —
# 그래서 여기서 발급한 토큰을 기존 화면들이 아직 쓰지는 않는다.
# --------------------------------------------------------------------------- #

@router.post("/auth/signup", status_code=201)
def signup(body: auth.SignupIn, session: Session = Depends(get_session)) -> dict:
    existing = session.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise HTTPException(status_code=400, detail="이미 가입된 이메일입니다.")

    user = User(email=body.email, password_hash=auth.hash_password(body.password), name=body.name)
    session.add(user)
    session.commit()
    return {"token": auth.create_token(user.id), "user": auth.user_out(user)}


@router.post("/auth/login")
def login(body: auth.LoginIn, session: Session = Depends(get_session)) -> dict:
    user = session.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is None or not auth.verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    return {"token": auth.create_token(user.id), "user": auth.user_out(user)}


@router.get("/auth/me")
def me(user: User = Depends(auth.get_current_user)) -> dict:
    return auth.user_out(user)


# --------------------------------------------------------------------------- #
# 계정 · 플랜 · 크레딧 (설정 / 크레딧 및 플랜 화면)
#
# 결제 시스템은 이 저장소엔 없다(deploy/README.md도 이미 인정한 부분). 없는 걸
# 있는 척 흉내 내지 않고, 고정값만 정직하게 돌려준다. /account는 이제 실제
# 로그인한 사용자를 돌려주고(1단계에서 미뤄뒀던 부분), 크레딧 잔액은
# "이 사용자 소유 프로젝트에서 지금까지 만든 페르소나 총합"으로 채운다 —
# 시스템 전체가 아니라 내 것만 세야 소유권 분리와 앞뒤가 맞는다.
# --------------------------------------------------------------------------- #

def _account_out(user: User) -> dict:
    return {
        "name": user.name, "initial": user.name[:1], "workspace": user.workspace,
        "email": user.email, "plan_label": "무료",
    }


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    workspace: str = Field(min_length=1, max_length=100)
    email: str

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return auth.normalize_email(value)


@router.get("/account")
def get_account(user: User = Depends(auth.get_current_user)) -> dict:
    return _account_out(user)


@router.put("/account")
def update_account(
    body: AccountIn,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    if body.email != user.email:
        existing = session.scalar(select(User).where(User.email == body.email))
        if existing is not None:
            raise HTTPException(status_code=400, detail="이미 사용 중인 이메일입니다.")

    user.name = body.name
    user.workspace = body.workspace
    user.email = body.email
    session.commit()
    return _account_out(user)


def _my_persona_count(session: Session, user: User) -> int:
    return session.scalar(
        select(func.count(Persona.id))
        .join(Test, Test.id == Persona.test_id)
        .join(Project, Project.id == Test.project_id)
        .where(Project.user_id == user.id)
    ) or 0


@router.get("/billing/plan")
def get_plan(
    session: Session = Depends(get_session), user: User = Depends(auth.get_current_user)
) -> dict:
    used = _my_persona_count(session, user)
    return {
        "current": {
            "name": "무료", "price_label": "₩0/월", "next_billing_at": "",
            "used": used, "quota": 0,
        },
        "features": [],
        "upgrade": {
            "badge": "", "title": "", "body": "결제 시스템이 아직 연결되지 않았습니다.",
            "cta": "", "note": "",
        },
    }


@router.get("/billing/credits")
def get_credits(
    session: Session = Depends(get_session), user: User = Depends(auth.get_current_user)
) -> dict:
    used = _my_persona_count(session, user)
    return {
        "balance": 0, "used_this_month": used, "rules": [], "packs": [], "history": [],
    }


@router.get("/billing/tiers")
def get_plan_tiers(user: User = Depends(auth.get_current_user)) -> dict:
    return {"tiers": [], "packs": []}


# --------------------------------------------------------------------------- #
# 두 프로젝트 비교(A/B)
# --------------------------------------------------------------------------- #

class AbIn(BaseModel):
    name: str
    a_project_id: uuid.UUID
    b_project_id: uuid.UUID


def _ab_card(row: AbTest, user: User, session: Session) -> dict | None:
    # 내 프로젝트끼리 짝지은 것만 보여준다 — a/b 둘 다 내 것이어야 한다.
    a_project = session.get(Project, row.a_project_id)
    b_project = session.get(Project, row.b_project_id)
    if a_project is None or b_project is None:
        return None
    if a_project.user_id != user.id or b_project.user_id != user.id:
        return None
    test_a = ab.latest_test_with_results(session, row.a_project_id)
    mission = session.scalar(select(Mission).where(Mission.test_id == test_a.id)) if test_a else None
    return {
        "id": str(row.id),
        "name": row.name,
        "mission": mission.prompt if mission else "",
        "created_at": _as_utc(row.created_at),
        "a": {"id": str(a_project.id), "name": a_project.name, "preview_url": a_project.preview_url},
        "b": {"id": str(b_project.id), "name": b_project.name, "preview_url": b_project.preview_url},
    }


@router.get("/ab")
def list_ab(
    session: Session = Depends(get_session), user: User = Depends(auth.get_current_user)
) -> dict:
    rows = list(session.scalars(select(AbTest).order_by(AbTest.created_at.desc())))
    items = [card for row in rows if (card := _ab_card(row, user, session)) is not None]
    return {"items": items}


@router.post("/ab")
def create_ab(
    body: AbIn,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    a_project = session.get(Project, body.a_project_id)
    b_project = session.get(Project, body.b_project_id)
    if a_project is None or b_project is None:
        return {"error": "비교할 프로젝트 두 개를 골라주세요."}
    if a_project.user_id != user.id or b_project.user_id != user.id:
        # 남의 프로젝트를 짝짓게 두지 않는다 — 존재 여부도 굳이 알려주지 않는다.
        return {"error": "비교할 프로젝트 두 개를 골라주세요."}

    row = AbTest(name=body.name, a_project_id=body.a_project_id, b_project_id=body.b_project_id)
    session.add(row)
    session.commit()
    return {"id": str(row.id)}


@router.get("/ab/{ab_id}")
def get_ab(
    ab_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(auth.get_current_user),
) -> dict:
    row = session.get(AbTest, ab_id)
    if row is None:
        raise HTTPException(status_code=404, detail="비교를 찾을 수 없습니다")

    a_project = session.get(Project, row.a_project_id)
    b_project = session.get(Project, row.b_project_id)
    if a_project is None or b_project is None:
        return {"ok": False, "message": "비교하던 프로젝트가 사라졌어요."}
    if a_project.user_id != user.id or b_project.user_id != user.id:
        raise HTTPException(status_code=404, detail="비교를 찾을 수 없습니다")

    test_a = ab.latest_test_with_results(session, row.a_project_id)
    test_b = ab.latest_test_with_results(session, row.b_project_id)
    mission = session.scalar(select(Mission).where(Mission.test_id == test_a.id)) if test_a else None

    return {
        "id": str(row.id),
        "name": row.name,
        "mission": mission.prompt if mission else "",
        "created_at": _as_utc(row.created_at),
        "a": ab.project_side(session, row.a_project_id, test_a),
        "b": ab.project_side(session, row.b_project_id, test_b),
        "compare": ab.compare_projects(session, test_a, test_b),
        "diagrams": ab.ab_diagrams(session, test_a, test_b),
        "steps": ab.ab_steps(session, test_a, test_b),
    }
