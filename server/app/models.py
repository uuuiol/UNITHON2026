"""db/schema.sql 을 그대로 비추는 ORM 모델.

스키마의 정본은 SQL 쪽이다. 여기서 create_all 로 테이블을 만들지 않는다 —
기획서의 설계 결정을 지키는 CHECK 제약이 SQL에만 온전히 들어 있기 때문이다.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .types import GUID, enum_type, json_type


class Base(DeclarativeBase):
    pass


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(GUID(), primary_key=True, default=uuid.uuid4)


def _enum(name: str, *values: str):
    # Postgres에서는 ENUM, SQLite에서는 문자열로 떨어진다 (app/types.py 참고).
    return enum_type(name, *values)


SourceType = _enum("source_type", "web_link", "github", "apk")
Severity = _enum("severity", "critical", "high", "medium")
DefectTier = _enum("defect_tier", "static", "render", "interaction", "semantic")
RunArm = _enum("run_arm", "A", "B", "C", "D")
RunPolicy = _enum("run_policy", "mock", "live")
RunStatus = _enum("run_status", "draft", "queued", "running", "done", "failed", "stopped")
TerminationReason = _enum(
    "termination_reason",
    "goal_achieved",
    "gave_up",
    "step_budget_exhausted",
    "loop_detected",
    "budget_cap",
    "runtime_error",
)
ActionType = _enum(
    "action_type",
    "click", "type", "scroll", "back", "wait",
    "navigate_link", "submit", "key", "other",
)
FindingVerdict = _enum(
    "finding_verdict", "true_positive", "false_positive", "duplicate", "unmatched"
)
MatchedBy = _enum("matched_by", "rule", "llm", "human")
LlmStage = _enum("llm_stage", "scout", "persona_gen", "explore", "score")
LlmModality = _enum("llm_modality", "text", "vision")


# --------------------------------------------------------------------------- #
# 1. 제품 계층
# --------------------------------------------------------------------------- #

class Project(Base):
    __tablename__ = "project"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(SourceType, default="web_link")
    device_preset: Mapped[str] = mapped_column(Text, default="16:9 데스크탑")
    viewport_w: Mapped[int] = mapped_column(Integer, default=1280)
    viewport_h: Mapped[int] = mapped_column(Integer, default=800)
    flow_map_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: 카드 썸네일용. iframe 임베드가 막힌 사이트면 embeddable=False 로 대체 이미지를 쓴다.
    preview_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    preview_embeddable: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    variants: Mapped[list["SiteVariant"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    tests: Mapped[list["Test"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    defects: Mapped[list["Defect"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class SiteVariant(Base):
    __tablename__ = "site_variant"
    __table_args__ = (UniqueConstraint("project_id", "key"),)

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(Text)               # 'clean' | 'flawed'
    label: Mapped[str] = mapped_column(Text)
    base_url: Mapped[str] = mapped_column(Text)
    is_control: Mapped[bool] = mapped_column(Boolean)
    #: 기획서 4장 — 장바구니 키의 소유자는 페르소나가 아니라 변형이다.
    cart_storage_key: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="variants")


class Test(Base):
    __tablename__ = "test"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    device: Mapped[str] = mapped_column(Text)
    target_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="draft")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="tests")
    mission: Mapped["Mission | None"] = relationship(back_populates="test", uselist=False, cascade="all, delete-orphan")
    persona_specs: Mapped[list["PersonaSpec"]] = relationship(back_populates="test", cascade="all, delete-orphan")
    personas: Mapped[list["Persona"]] = relationship(back_populates="test", cascade="all, delete-orphan")
    runs: Mapped[list["Run"]] = relationship(back_populates="test", cascade="all, delete-orphan")


class Mission(Base):
    __tablename__ = "mission"
    __table_args__ = (CheckConstraint("length(prompt) BETWEEN 1 AND 200", name="mission_prompt_len"),)

    id: Mapped[uuid.UUID] = _pk()
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test.id", ondelete="CASCADE"), unique=True)
    prompt: Mapped[str] = mapped_column(Text)
    success_criteria: Mapped[str] = mapped_column(Text)
    auto_detect: Mapped[bool] = mapped_column(Boolean, default=True)
    #: [화면] "달성으로 인정할 근거 문구". 비어 있으면 페르소나 본인 주장만으로 달성 처리한다
    #: (run.py --expect). 화면엔 이미 입력창이 있었는데 저장할 컬럼이 없어서 버려지고 있었다.
    expect: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    test: Mapped[Test] = relationship(back_populates="mission")
    goals: Mapped[list["Goal"]] = relationship(back_populates="mission", cascade="all, delete-orphan")


# --------------------------------------------------------------------------- #
# 2. 페르소나 계층
# --------------------------------------------------------------------------- #

class PersonaSpec(Base):
    """[화면] 페르소나 설정 — 연령대별 총원 + 성별 비율. UI가 받는 '분포'.

    성별 인원은 total × female_percent 에서 파생된다. 파생값을 따로 저장하지 않는 이유는
    한쪽만 갱신되는 순간 어느 쪽이 진실인지 알 수 없어지기 때문이다.
    """

    __tablename__ = "persona_spec"
    __table_args__ = (
        UniqueConstraint("test_id", "age_band"),
        CheckConstraint("total >= 0", name="persona_spec_total_nonneg"),
        CheckConstraint("female_percent BETWEEN 0 AND 100", name="persona_spec_ratio_range"),
        CheckConstraint("enabled OR total = 0", name="persona_spec_disabled_is_zero"),
    )

    id: Mapped[uuid.UUID] = _pk()
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test.id", ondelete="CASCADE"))
    age_band: Mapped[str] = mapped_column(Text)
    total: Mapped[int] = mapped_column(Integer, default=0)
    female_percent: Mapped[int] = mapped_column(SmallInteger, default=50)
    gender_agnostic: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    test: Mapped[Test] = relationship(back_populates="persona_specs")

    def split(self) -> dict[str, int]:
        """총원과 비율에서 실제 인원을 만든다. 반올림 오차는 남성 쪽이 흡수한다."""
        if not self.enabled:
            return {"male": 0, "female": 0, "any": 0}
        if self.gender_agnostic:
            return {"male": 0, "female": 0, "any": self.total}
        female = round(self.total * self.female_percent / 100)
        return {"male": self.total - female, "female": female, "any": 0}


class TraitCombo(Base):
    """특성 조합 16개. dwell_ms 가 여기 있어야 팝업(10초)을 마주치는 인원이 결정된다."""

    __tablename__ = "trait_combo"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True)
    reading_style: Mapped[str] = mapped_column(Text)
    pace: Mapped[str] = mapped_column(Text)
    tech_literacy: Mapped[str] = mapped_column(Text)
    patience: Mapped[str] = mapped_column(Text)
    dwell_ms: Mapped[int] = mapped_column(Integer)
    max_steps: Mapped[int] = mapped_column(Integer, default=30)


class Goal(Base):
    """목표 11개. 16과 서로소라서 100명 전원이 서로 다른 (조합, 목표) 쌍을 받는다."""

    __tablename__ = "goal"
    __table_args__ = (UniqueConstraint("mission_id", "idx"),)

    id: Mapped[uuid.UUID] = _pk()
    mission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mission.id", ondelete="CASCADE"))
    idx: Mapped[int] = mapped_column(SmallInteger)
    prompt: Mapped[str] = mapped_column(Text)
    requires_cart_seed: Mapped[bool] = mapped_column(Boolean, default=False)

    mission: Mapped[Mission] = relationship(back_populates="goals")


class Persona(Base):
    __tablename__ = "persona"
    __table_args__ = (
        UniqueConstraint("test_id", "code"),
        # (trait_combo_id, goal_id) 고유 제약은 없앴다 — goal이 미션당 1개로 고정되면서
        # 특성 조합이 100명 안에서 반복되는 게 정상 동작이 됐다 (server/app/personas.py 참고).
    )

    id: Mapped[uuid.UUID] = _pk()
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(8))
    trait_combo_id: Mapped[int] = mapped_column(ForeignKey("trait_combo.id"))
    goal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("goal.id"))
    age_band: Mapped[str] = mapped_column(Text)
    gender: Mapped[str] = mapped_column(Text)
    dwell_ms: Mapped[int] = mapped_column(Integer)
    max_steps: Mapped[int] = mapped_column(Integer)

    test: Mapped[Test] = relationship(back_populates="personas")
    trait_combo: Mapped[TraitCombo] = relationship()
    goal: Mapped[Goal] = relationship()


# --------------------------------------------------------------------------- #
# 3. 답사 계층
# --------------------------------------------------------------------------- #

class SiteMap(Base):
    __tablename__ = "site_map"
    __table_args__ = (UniqueConstraint("site_variant_id", "version"),)

    id: Mapped[uuid.UUID] = _pk()
    site_variant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("site_variant.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    screens_found: Mapped[int] = mapped_column(Integer)
    screens_expected: Mapped[int] = mapped_column(Integer)
    #: 도달 못한 화면은 '없는 것'이 아니라 사실로 기록된다 (flawed 결제 완료 화면).
    unreached: Mapped[list] = mapped_column(json_type(), default=list)
    scout_steps: Mapped[int] = mapped_column(Integer, default=0)
    is_placeholder: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    variant: Mapped[SiteVariant] = relationship()
    screens: Mapped[list["SiteMapScreen"]] = relationship(back_populates="site_map", cascade="all, delete-orphan")


class SiteMapScreen(Base):
    """narrative 는 LLM 이 쓴 서술만 담는다. 수치는 ScreenMeasurement 로 간다."""

    __tablename__ = "site_map_screen"
    __table_args__ = (UniqueConstraint("site_map_id", "screen_key"),)

    id: Mapped[uuid.UUID] = _pk()
    site_map_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("site_map.id", ondelete="CASCADE"))
    screen_key: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    narrative: Mapped[str] = mapped_column(Text)
    reached_by: Mapped[str] = mapped_column(Text, default="link")
    step_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    site_map: Mapped[SiteMap] = relationship(back_populates="screens")


class ScreenMeasurement(Base):
    """코드가 잰 수치만. measured_by='code' 를 DB가 강제한다."""

    __tablename__ = "screen_measurement"

    id: Mapped[uuid.UUID] = _pk()
    site_map_screen_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("site_map_screen.id", ondelete="CASCADE"), nullable=True
    )
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("step.id", ondelete="CASCADE"), nullable=True
    )
    metric_key: Mapped[str] = mapped_column(Text)
    value_num: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    value_json: Mapped[dict | None] = mapped_column(json_type(), nullable=True)
    source_selector: Mapped[str | None] = mapped_column(Text, nullable=True)
    measured_at_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    measured_by: Mapped[str] = mapped_column(Text, default="code")


# --------------------------------------------------------------------------- #
# 4. 실행 계층
# --------------------------------------------------------------------------- #

class Run(Base):
    __tablename__ = "run"
    __table_args__ = (UniqueConstraint("test_id", "arm"),)

    id: Mapped[uuid.UUID] = _pk()
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test.id", ondelete="CASCADE"))
    site_variant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("site_variant.id"))
    site_map_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("site_map.id"), nullable=True)
    arm: Mapped[str] = mapped_column(RunArm)
    map_enabled: Mapped[bool] = mapped_column(Boolean)
    policy: Mapped[str] = mapped_column(RunPolicy, default="mock")
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    persona_count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(RunStatus, default="draft")
    #: 2명 이상은 확인 없이 시작되지 않는다 (기획서 7장).
    confirmed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    budget_limit_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    budget_spent_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    stopped_by_budget: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    test: Mapped[Test] = relationship(back_populates="runs")
    variant: Mapped[SiteVariant] = relationship()
    journeys: Mapped[list["Journey"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class Journey(Base):
    __tablename__ = "journey"
    __table_args__ = (UniqueConstraint("run_id", "persona_id"),)

    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id", ondelete="CASCADE"))
    persona_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("persona.id"))
    termination_reason: Mapped[str | None] = mapped_column(TerminationReason, nullable=True)
    goal_achieved: Mapped[bool] = mapped_column(Boolean, default=False)
    step_count: Mapped[int] = mapped_column(Integer, default=0)
    log_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped[Run] = relationship(back_populates="journeys")
    persona: Mapped[Persona] = relationship()
    steps: Mapped[list["Step"]] = relationship(back_populates="journey", cascade="all, delete-orphan")


class Step(Base):
    """스텝마다 생각·행동·화면. 허용되지 않은 행동은 executed=False 로 '기록만' 남는다."""

    __tablename__ = "step"
    __table_args__ = (UniqueConstraint("journey_id", "idx"),)

    id: Mapped[uuid.UUID] = _pk()
    journey_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journey.id", ondelete="CASCADE"))
    idx: Mapped[int] = mapped_column(Integer)
    thought: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(ActionType)
    action_target: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    executed: Mapped[bool] = mapped_column(Boolean, default=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    screen_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    dwell_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    dom_digest_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    journey: Mapped[Journey] = relationship(back_populates="steps")


class GuardHit(Base):
    """금칙어에 걸려 버린 화면 기록. 버렸다는 사실 자체가 남아야 재현율을 설명할 수 있다."""

    __tablename__ = "guard_hit"

    id: Mapped[uuid.UUID] = _pk()
    site_map_screen_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("site_map_screen.id", ondelete="CASCADE"), nullable=True
    )
    step_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("step.id", ondelete="CASCADE"), nullable=True)
    rule: Mapped[str] = mapped_column(Text)
    matched_text: Mapped[str] = mapped_column(Text)
    action_taken: Mapped[str] = mapped_column(Text, default="discard_screen")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --------------------------------------------------------------------------- #
# 5. 정답지 & 채점
# --------------------------------------------------------------------------- #

class Defect(Base):
    __tablename__ = "defect"
    __table_args__ = (UniqueConstraint("project_id", "code"),)

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(Severity)
    tier: Mapped[str] = mapped_column(DefectTier)
    detection_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: 375 가 들어 있으면 1280 뷰포트 실행에서는 '잡을 수 없음'으로 분모에서 뺄 수 있다.
    requires_viewport_w: Mapped[int | None] = mapped_column(Integer, nullable=True)

    project: Mapped[Project] = relationship(back_populates="defects")


class Finding(Base):
    """채점기가 기록에서 뽑은 지적. 실행 중에는 만들어지지 않는다."""

    __tablename__ = "finding"

    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id", ondelete="CASCADE"))
    journey_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journey.id", ondelete="CASCADE"), nullable=True)
    step_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("step.id", ondelete="CASCADE"), nullable=True)
    screen_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    scorer_version: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    match: Mapped["FindingMatch | None"] = relationship(back_populates="finding", uselist=False, cascade="all, delete-orphan")


class FindingMatch(Base):
    __tablename__ = "finding_match"
    __table_args__ = (UniqueConstraint("finding_id"),)

    id: Mapped[uuid.UUID] = _pk()
    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("finding.id", ondelete="CASCADE"))
    defect_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("defect.id"), nullable=True)
    verdict: Mapped[str] = mapped_column(FindingVerdict)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    matched_by: Mapped[str] = mapped_column(MatchedBy)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    finding: Mapped[Finding] = relationship(back_populates="match")
    defect: Mapped[Defect | None] = relationship()


class RunScore(Base):
    __tablename__ = "run_score"
    __table_args__ = (UniqueConstraint("run_id", "scorer_version"),)

    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run.id", ondelete="CASCADE"))
    scorer_version: Mapped[str] = mapped_column(Text)
    defects_total: Mapped[int] = mapped_column(Integer)
    defects_found: Mapped[int] = mapped_column(Integer)
    findings_total: Mapped[int] = mapped_column(Integer)
    true_positives: Mapped[int] = mapped_column(Integer)
    false_positives: Mapped[int] = mapped_column(Integer)
    recall: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    precision: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    fp_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[Run] = relationship()


# --------------------------------------------------------------------------- #
# 6. 비용
# --------------------------------------------------------------------------- #

class LlmCall(Base):
    """stage='explore' 에는 vision 이 못 들어간다 — 기획서 7장 비용 구조를 DB가 지킨다."""

    __tablename__ = "llm_call"

    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("run.id", ondelete="CASCADE"), nullable=True)
    journey_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journey.id", ondelete="CASCADE"), nullable=True)
    step_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("step.id", ondelete="CASCADE"), nullable=True)
    stage: Mapped[str] = mapped_column(LlmStage)
    modality: Mapped[str] = mapped_column(LlmModality)
    model: Mapped[str] = mapped_column(Text)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --------------------------------------------------------------------------- #
# 7. 두 프로젝트 비교(A/B)
# --------------------------------------------------------------------------- #

class AbTest(Base):
    """서로 다른 두 프로젝트를 통째로 견준다 (한 프로젝트 안의 clean/flawed 변형과는 다르다).

    예: 리뉴얼 전 사이트(a)와 리뉴얼 후 사이트(b). 비교 시점엔 각자의 가장 최근 실행
    결과를 그때그때 읽는다 — 이 테이블은 "무엇과 무엇을 짝지었는가"만 기억한다.
    """

    __tablename__ = "ab_test"

    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(Text)
    a_project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    b_project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id", ondelete="CASCADE"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    a_project: Mapped[Project] = relationship(foreign_keys=[a_project_id])
    b_project: Mapped[Project] = relationship(foreign_keys=[b_project_id])


# --------------------------------------------------------------------------- #
# 8. 계정
# --------------------------------------------------------------------------- #

class User(Base):
    __tablename__ = "user"

    id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    workspace: Mapped[str] = mapped_column(Text, default="내 워크스페이스")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
