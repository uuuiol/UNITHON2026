-- =============================================================================
--  AI 페르소나 UX 테스트 — 백엔드 스키마 (PostgreSQL 15+)
--
--  기획서(2026-08-25)의 5단계 파이프라인과 Figma UI 화면을 한 스키마에 담는다.
--  기획서 4장의 "설계 결정"은 주석이 아니라 **제약조건**으로 넣었다.
--  주석으로만 적어두면 조용히 어겨지고, 조용히 틀린 숫자가 발표에 올라간다.
--
--  적재:  psql "$DATABASE_URL" -f db/schema.sql
-- =============================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()

-- -----------------------------------------------------------------------------
-- 0. 열거형
-- -----------------------------------------------------------------------------

CREATE TYPE source_type        AS ENUM ('web_link', 'github', 'apk');
CREATE TYPE severity           AS ENUM ('critical', 'high', 'medium');

-- 기획서 5장: 결함 난이도 4층 (22 / 10 / 16 / 20건)
CREATE TYPE defect_tier        AS ENUM ('static', 'render', 'interaction', 'semantic');

-- 기획서 6장: 변형 2종 × 지도 유무 2종 = 4회 실행
CREATE TYPE run_arm            AS ENUM ('A', 'B', 'C', 'D');
CREATE TYPE run_policy         AS ENUM ('mock', 'live');
CREATE TYPE run_status         AS ENUM ('draft', 'queued', 'running', 'done', 'failed', 'stopped');

-- 기획서 4장 "종료 사유를 여섯 가지로 나눈다":
--   포기 / 스텝 소진 / 맴돌다 중단 은 서로 다른 신호이고,
--   예산 상한에 걸려 우리가 끊은 것을 '포기'로 적으면 그 통계가 오염된다.
CREATE TYPE termination_reason AS ENUM (
    'goal_achieved',          -- 목표 달성
    'gave_up',                -- 페르소나가 스스로 포기
    'step_budget_exhausted',  -- 스텝 소진
    'loop_detected',          -- 맴돌다 중단
    'budget_cap',             -- 예산 상한 — 우리가 끊음
    'runtime_error'           -- 실행 오류
);

CREATE TYPE action_type        AS ENUM (
    'click', 'type', 'scroll', 'back', 'wait',
    'navigate_link', 'submit', 'key', 'other'
);

CREATE TYPE finding_verdict    AS ENUM ('true_positive', 'false_positive', 'duplicate', 'unmatched');
CREATE TYPE matched_by         AS ENUM ('rule', 'llm', 'human');
CREATE TYPE llm_stage          AS ENUM ('scout', 'persona_gen', 'explore', 'score');
CREATE TYPE llm_modality       AS ENUM ('text', 'vision');


-- =============================================================================
-- 0b. 계정 — project가 이걸 참조하므로 먼저 만든다.
-- =============================================================================

CREATE TABLE "user" (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email         text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    name          text NOT NULL,
    workspace     text NOT NULL DEFAULT '내 워크스페이스',
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- =============================================================================
-- 1. 제품 계층 — Figma 화면과 1:1
-- =============================================================================

-- [화면] 프로젝트 목록 / 새 프로젝트
CREATE TABLE project (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       uuid NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    name          text        NOT NULL,
    category      text        NOT NULL,
    source        source_type NOT NULL DEFAULT 'web_link',
    device_preset text        NOT NULL DEFAULT '16:9 데스크탑',
    -- 기획서 6장: 뷰포트가 1280×800 고정이라 375px에서만 드러나는 3건은 원리적으로 못 잡는다.
    -- 그 상한을 사후에 설명하려면 실제로 쓴 뷰포트가 남아 있어야 한다.
    viewport_w    integer     NOT NULL DEFAULT 1280,
    viewport_h    integer     NOT NULL DEFAULT 800,
    flow_map_path text,                     -- 유저 플로우 맵(sitemap.xml 등)
    -- 카드 썸네일에 실제 화면을 띄우기 위한 값.
    -- embeddable=false 면 iframe 이 빈 화면으로 뜨므로 대체 이미지를 쓴다.
    preview_url         text,
    preview_embeddable  boolean NOT NULL DEFAULT false,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT project_name_len CHECK (length(name) BETWEEN 1 AND 100)
);

-- 한 프로젝트의 변형. 기획서 5장: 같은 쇼핑몰을 정상판/결함판으로 만들어 뒀다.
-- clean 이 없으면 정밀도를 잴 수 없다 → 대조군을 스키마가 요구한다.
CREATE TABLE site_variant (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       uuid NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    key              text NOT NULL,          -- 'clean' | 'flawed'
    label            text NOT NULL,
    base_url         text NOT NULL,
    is_control       boolean NOT NULL,       -- clean = true
    -- 기획서 4장 "장바구니 키는 페르소나 파일에 넣지 않는다":
    -- 키가 변형마다 다른데(moji_cart_clean / moji_cart_flawed) 같은 페르소나 파일을
    -- 양쪽에 투입한다. 키를 페르소나에 박으면 한쪽이 조용히 빈 장바구니가 된다.
    -- 그래서 키의 소유자는 페르소나가 아니라 변형이다.
    cart_storage_key text NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),

    UNIQUE (project_id, key),
    UNIQUE (project_id, cart_storage_key)
);

-- [화면] 새 테스트 생성
CREATE TABLE test (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  uuid NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    name        text NOT NULL,
    device      text NOT NULL,
    target_url  text NOT NULL,
    status      text NOT NULL DEFAULT 'draft',
    created_at  timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT test_name_len CHECK (length(name) BETWEEN 1 AND 100)
);
CREATE INDEX ON test (project_id, created_at DESC);

-- [화면] 미션 설정
CREATE TABLE mission (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id          uuid NOT NULL UNIQUE REFERENCES test(id) ON DELETE CASCADE,
    prompt           text NOT NULL,
    success_criteria text NOT NULL,
    auto_detect      boolean NOT NULL DEFAULT true,   -- UI의 "자동" 배지
    expect           text NOT NULL DEFAULT '',        -- "달성으로 인정할 근거 문구" (run.py --expect)
    created_at       timestamptz NOT NULL DEFAULT now(),

    -- UI 카운터가 200자다. 잘린 미션이 조용히 저장되면 100명이 다른 일을 한다.
    CONSTRAINT mission_prompt_len CHECK (length(prompt) BETWEEN 1 AND 200)
);


-- =============================================================================
-- 2. 페르소나 계층
-- =============================================================================

-- [화면] 페르소나 설정 — 연령대 × 성별 인원표
-- UI가 받는 것은 "분포"고, 파이프라인이 필요한 것은 "개인 100명"이다. 둘을 분리한다.
CREATE TABLE persona_spec (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id         uuid NOT NULL REFERENCES test(id) ON DELETE CASCADE,
    age_band        text NOT NULL,                   -- '10s' … '60s+'
    total           integer NOT NULL DEFAULT 0,      -- 이 연령대의 총 인원
    -- 화면이 성별 3칸 입력에서 "총원 + 비율 슬라이더"로 바뀌었다.
    -- 성별 인원은 비율에서 파생되는 값이라 저장하지 않는다 —
    -- 둘 다 저장하면 언젠가 반드시 어긋나고, 어느 쪽이 맞는지 알 수 없어진다.
    female_percent  smallint NOT NULL DEFAULT 50,
    gender_agnostic boolean NOT NULL DEFAULT false,  -- 성별 무작위 배정
    enabled         boolean NOT NULL DEFAULT true,

    UNIQUE (test_id, age_band),
    CONSTRAINT persona_spec_total_nonneg CHECK (total >= 0),
    CONSTRAINT persona_spec_ratio_range CHECK (female_percent BETWEEN 0 AND 100),
    -- 꺼진 연령대에 인원이 남아 있으면 총원과 실제 생성 수가 어긋난다.
    CONSTRAINT persona_spec_disabled_is_zero CHECK (enabled OR total = 0)
);

-- 기획서 4장 "성격마다 화면에 머무는 시간이 다르다":
-- 자동 팝업(D-26)은 로드 10초 후에 뜬다. 전원이 5초 만에 떠나면 그 Critical 결함은
-- '못 잡은 것'이 아니라 '마주친 적이 없는 것'이 된다. → 체류 시간은 특성이 정한다.
CREATE TABLE trait_combo (
    id             smallint PRIMARY KEY,        -- 1..16
    code           text NOT NULL UNIQUE,
    reading_style  text NOT NULL,               -- '정독' | '훑기'
    pace           text NOT NULL,               -- '여유' | '급함'
    tech_literacy  text NOT NULL,               -- '능숙' | '서툼'
    patience       text NOT NULL,               -- '높음' | '낮음'
    dwell_ms       integer NOT NULL,            -- 화면당 체류 시간
    max_steps      integer NOT NULL DEFAULT 30,

    CONSTRAINT trait_combo_dwell_pos CHECK (dwell_ms > 0)
);

-- 기획서 4장 "목표는 10개가 아니라 11개":
-- 특성 조합이 16개다. 10개면 최소공배수가 80이라 81번째부터 앞 20명과 조건이 겹친다.
-- 11은 16과 서로소라 100명 전원이 서로 다른 (조합, 목표) 쌍을 받는다.
CREATE TABLE goal (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    mission_id         uuid NOT NULL REFERENCES mission(id) ON DELETE CASCADE,
    idx                smallint NOT NULL,       -- 0..10
    prompt             text NOT NULL,
    requires_cart_seed boolean NOT NULL DEFAULT false,   -- '중단·재개' 계열 목표

    UNIQUE (mission_id, idx),
    CONSTRAINT goal_idx_range CHECK (idx BETWEEN 0 AND 10)
);

-- 조립된 개인 100명
CREATE TABLE persona (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id        uuid NOT NULL REFERENCES test(id) ON DELETE CASCADE,
    code           text NOT NULL,                        -- 'P001' … 'P100'
    trait_combo_id smallint NOT NULL REFERENCES trait_combo(id),
    goal_id        uuid NOT NULL REFERENCES goal(id),
    age_band       text NOT NULL,
    gender         text NOT NULL,
    dwell_ms       integer NOT NULL,
    max_steps      integer NOT NULL,

    UNIQUE (test_id, code)
    -- (trait_combo_id, goal_id) 고유 제약은 없앴다 — goal이 미션당 1개로 고정되면서
    -- 특성 조합이 100명 안에서 반복되는 게 정상 동작이 됐다 (server/app/personas.py 참고).
);
CREATE INDEX ON persona (test_id);


-- =============================================================================
-- 3. 답사(scout) 계층 — 기획서 3장 1단계
-- =============================================================================

CREATE TABLE site_map (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    site_variant_id  uuid NOT NULL REFERENCES site_variant(id) ON DELETE CASCADE,
    version          integer NOT NULL DEFAULT 1,
    screens_found    integer NOT NULL,
    screens_expected integer NOT NULL,
    -- 기획서 6장: flawed는 결제가 완주되지 않아 답사가 5/6에서 멈춘다.
    -- 완료 화면은 '없는 것'이 아니라 unreached에 **사실로** 기록된다.
    unreached        jsonb   NOT NULL DEFAULT '[]'::jsonb,
    scout_steps      integer NOT NULL DEFAULT 0,
    is_placeholder   boolean NOT NULL DEFAULT false,  -- 크레딧 붙기 전 자리표시자 지도
    created_at       timestamptz NOT NULL DEFAULT now(),

    UNIQUE (site_variant_id, version)
);

CREATE TABLE site_map_screen (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    site_map_id uuid NOT NULL REFERENCES site_map(id) ON DELETE CASCADE,
    screen_key  text NOT NULL,
    title       text NOT NULL,
    url         text NOT NULL,
    -- 기획서 4장 "지도는 서술만, 수치는 코드가 잰다":
    -- 스크린샷을 본 LLM이 지어낸 대비·좌표가 지도에 박히면 100명에게 그대로 배포된다.
    -- 그래서 서술(LLM)과 수치(코드)를 **다른 테이블**에 둔다. 같은 칸에 섞으면 출처가 사라진다.
    narrative   text NOT NULL,
    reached_by  text NOT NULL DEFAULT 'link',   -- 'link' | 'interaction'
    step_index  integer,

    UNIQUE (site_map_id, screen_key),
    CONSTRAINT screen_reached_by CHECK (reached_by IN ('link', 'interaction'))
);

-- 코드가 잰 수치만 들어간다. 기획서 5장의 탐지기 기준선 표가 그대로 이 테이블이다.
CREATE TABLE screen_measurement (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    site_map_screen_id  uuid REFERENCES site_map_screen(id) ON DELETE CASCADE,
    step_id             uuid,                   -- 탐색 중 측정분 (아래 step 테이블, 순환참조라 FK는 뒤에)
    metric_key          text NOT NULL,          -- 'contrast_ratio' | 'font_size_px'
                                                -- 'occluded_count' | 'keyboard_unreachable_count'
                                                -- 'low_contrast_count' | 'scroll_width_overflow'
    value_num           numeric,
    value_json          jsonb,
    source_selector     text,
    measured_at_ms      integer,                -- 로드 후 경과 ms. 팝업(10초)은 0초와 값이 다르다.
    -- 출처를 컬럼으로 못박는다. LLM이 지어낸 숫자가 이 테이블에 들어올 경로를 없앤다.
    measured_by         text NOT NULL DEFAULT 'code',

    CONSTRAINT measurement_by_code_only CHECK (measured_by = 'code'),
    CONSTRAINT measurement_has_owner
        CHECK (num_nonnulls(site_map_screen_id, step_id) = 1),
    CONSTRAINT measurement_has_value
        CHECK (num_nonnulls(value_num, value_json) >= 1)
);
CREATE INDEX ON screen_measurement (metric_key, measured_at_ms);


-- =============================================================================
-- 4. 실행(run) 계층 — 기획서 3장 3단계 + 6장 검증 계획
-- =============================================================================

CREATE TABLE run (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id          uuid NOT NULL REFERENCES test(id) ON DELETE CASCADE,
    site_variant_id  uuid NOT NULL REFERENCES site_variant(id),
    -- 지도 없음 조건(B·D)에서는 NULL이다.
    site_map_id      uuid REFERENCES site_map(id),
    arm              run_arm     NOT NULL,
    map_enabled      boolean     NOT NULL,
    policy           run_policy  NOT NULL DEFAULT 'mock',
    model            text,
    persona_count    integer     NOT NULL DEFAULT 1,
    status           run_status  NOT NULL DEFAULT 'draft',

    -- 기획서 7장: 실행기 기본값은 한 명. 100명은 명시적으로 요청해야 하고
    -- 예상 호출 수를 보여준 뒤 한 번 더 묻는다 → 그 확인이 실제로 있었는지 남긴다.
    confirmed_at     timestamptz,
    budget_limit_usd numeric(10,4),
    budget_spent_usd numeric(10,4) NOT NULL DEFAULT 0,
    stopped_by_budget boolean NOT NULL DEFAULT false,

    started_at       timestamptz,
    finished_at      timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),

    -- 지도 유무는 하나의 사실이다. 플래그와 실제 참조가 어긋나면 A/B 비교가 무의미해진다.
    CONSTRAINT run_map_flag_matches_ref
        CHECK (map_enabled = (site_map_id IS NOT NULL)),
    -- 2명 이상은 반드시 확인을 거친다.
    CONSTRAINT run_bulk_needs_confirm
        CHECK (persona_count <= 1 OR confirmed_at IS NOT NULL),
    CONSTRAINT run_persona_count_pos CHECK (persona_count > 0),
    -- 같은 테스트에서 같은 팔(arm)을 두 번 만들면 어느 쪽이 발표 수치인지 알 수 없다.
    UNIQUE (test_id, arm)
);
CREATE INDEX ON run (test_id, created_at DESC);

CREATE TABLE journey (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id             uuid NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    persona_id         uuid NOT NULL REFERENCES persona(id),
    termination_reason termination_reason,
    goal_achieved      boolean NOT NULL DEFAULT false,
    step_count         integer NOT NULL DEFAULT 0,
    log_path           text,                  -- logs/{run_id}/P0xx.json
    started_at         timestamptz,
    finished_at        timestamptz,

    UNIQUE (run_id, persona_id),
    -- 종료 사유와 달성 여부가 어긋나면 성공률이 조용히 틀린다.
    CONSTRAINT journey_achieved_matches_reason
        CHECK (goal_achieved = (termination_reason = 'goal_achieved')
               OR termination_reason IS NULL),
    -- 끝난 여정에는 반드시 사유가 있다. NULL은 '아직 안 끝남'만을 뜻한다.
    CONSTRAINT journey_finished_has_reason
        CHECK ((finished_at IS NULL) = (termination_reason IS NULL))
);
CREATE INDEX ON journey (run_id, termination_reason);

CREATE TABLE step (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    journey_id      uuid NOT NULL REFERENCES journey(id) ON DELETE CASCADE,
    idx             integer NOT NULL,
    -- 기획서 2장 차별점 ③: 스텝마다 생각·행동·그 순간 화면을 통째로 저장한다.
    thought         text,
    action          action_type NOT NULL,
    action_target   text,
    action_value    text,
    -- 기획서 4장 "허용 행동 목록을 러너가 실제로 강제한다":
    -- 서툰 사람에게 주소창 입력을 허용하면 결제 페이지로 순간이동해 길찾기 마찰이
    -- 통째로 측정에서 사라진다. 목록 밖 행동은 **실행하지 않고 기록만 남긴다.**
    allowed         boolean NOT NULL DEFAULT true,
    executed        boolean NOT NULL DEFAULT true,
    url             text,
    screen_key      text,
    dwell_ms        integer,
    -- 31MB/100명. 큰 것은 파일로 두고 경로만 든다.
    screenshot_path text,
    dom_digest_path text,
    created_at      timestamptz NOT NULL DEFAULT now(),

    UNIQUE (journey_id, idx),
    CONSTRAINT step_denied_not_executed CHECK (allowed OR NOT executed)
);
CREATE INDEX ON step (journey_id, idx);
CREATE INDEX ON step (screen_key);

ALTER TABLE screen_measurement
    ADD CONSTRAINT screen_measurement_step_fk
    FOREIGN KEY (step_id) REFERENCES step(id) ON DELETE CASCADE;

-- 기획서 4장 "답사자는 성격은 있어도 판단은 하지 않는다":
-- 답사자가 "여기 불편함"이라 적으면 100명 전원이 그 문제를 '발견'한다.
-- 적중률 100%는 1명이 찾은 것을 100번 복사한 값이다.
-- 금칙어를 코드가 검사하고, 걸리면 그 화면 기록만 버린다 — 버린 사실을 남긴다.
CREATE TABLE guard_hit (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    site_map_screen_id uuid REFERENCES site_map_screen(id) ON DELETE CASCADE,
    step_id            uuid REFERENCES step(id) ON DELETE CASCADE,
    rule               text NOT NULL,
    matched_text       text NOT NULL,
    action_taken       text NOT NULL DEFAULT 'discard_screen',
    created_at         timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT guard_hit_has_owner
        CHECK (num_nonnulls(site_map_screen_id, step_id) = 1)
);


-- =============================================================================
-- 5. 정답지 & 채점 — 기획서 4장 "탐색 중에는 결함 분석을 시키지 않는다"
--    채점은 실행이 다 끝난 뒤 별개 단계에서 한다. 그래서 테이블도 분리돼 있다.
-- =============================================================================

CREATE TABLE defect (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       uuid NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    code             text NOT NULL,          -- 'D-05', 'D-05b'
    category         text NOT NULL,          -- 'A. 색 대비 · 타이포그래피'
    title            text NOT NULL,
    location         text,
    severity         severity    NOT NULL,
    tier             defect_tier NOT NULL,
    detection_method text,
    -- 기획서 6장: 375px에서만 드러나는 3건은 1280 뷰포트에서 원리적으로 못 잡는다.
    -- '못 잡음'과 '잡을 수 없음'을 구분해야 재현율이 정직해진다.
    requires_viewport_w integer,

    UNIQUE (project_id, code)
);
CREATE INDEX ON defect (project_id, tier, severity);

-- 채점기가 기록에서 뽑아낸 '지적' 한 건. 실행 중에는 절대 만들어지지 않는다.
CREATE TABLE finding (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id         uuid NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    journey_id     uuid REFERENCES journey(id) ON DELETE CASCADE,
    step_id        uuid REFERENCES step(id) ON DELETE CASCADE,
    screen_key     text,
    raw_text       text NOT NULL,
    scorer_version text NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON finding (run_id, scorer_version);

CREATE TABLE finding_match (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id uuid NOT NULL REFERENCES finding(id) ON DELETE CASCADE,
    -- 정답지에 없는 지적 = 오탐. clean 실행(C·D)에서 나온 것은 전부 여기로 떨어진다.
    defect_id  uuid REFERENCES defect(id),
    verdict    finding_verdict NOT NULL,
    confidence numeric(4,3),
    matched_by matched_by NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),

    UNIQUE (finding_id),
    -- 정답지에 붙는 판정(적중·중복)에는 결함 ID가 반드시 있고,
    -- 오탐·미매칭에는 반드시 없다. 섞이면 재현율 분자가 오염된다.
    CONSTRAINT match_verdict_defect_consistency
        CHECK ((verdict IN ('true_positive', 'duplicate')) = (defect_id IS NOT NULL))
);

-- 발표에 올릴 수치는 재계산 때마다 흔들리면 안 된다. 채점기 버전과 함께 고정해 둔다.
CREATE TABLE run_score (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id         uuid NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    scorer_version text NOT NULL,
    defects_total  integer NOT NULL,
    defects_found  integer NOT NULL,
    findings_total integer NOT NULL,
    true_positives integer NOT NULL,
    false_positives integer NOT NULL,
    recall         numeric(5,4),
    precision      numeric(5,4),
    fp_rate        numeric(6,4),
    computed_at    timestamptz NOT NULL DEFAULT now(),

    UNIQUE (run_id, scorer_version),
    CONSTRAINT score_found_le_total CHECK (defects_found <= defects_total)
);


-- =============================================================================
-- 6. 비용 — 기획서 7장 표를 집계로 자동 산출한다
--    "페르소나 100명의 이미지 호출 0회"를 주장이 아니라 쿼리로 증명한다.
-- =============================================================================

CREATE TABLE llm_call (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id     uuid REFERENCES run(id) ON DELETE CASCADE,
    journey_id uuid REFERENCES journey(id) ON DELETE CASCADE,
    step_id    uuid REFERENCES step(id) ON DELETE CASCADE,
    stage      llm_stage    NOT NULL,
    modality   llm_modality NOT NULL,
    model      text NOT NULL,
    tokens_in  integer NOT NULL DEFAULT 0,
    tokens_out integer NOT NULL DEFAULT 0,
    cost_usd   numeric(10,6) NOT NULL DEFAULT 0,
    latency_ms integer,
    created_at timestamptz NOT NULL DEFAULT now(),

    -- 탐색 단계에서 비전 호출이 생기면 기획서 7장의 비용 구조가 무너진다.
    -- 실수로 스텝마다 이미지를 넣는 코드가 들어오면 여기서 즉시 터진다.
    CONSTRAINT explore_is_text_only
        CHECK (stage <> 'explore' OR modality = 'text')
);
CREATE INDEX ON llm_call (run_id, stage, modality);

-- ─────────────────────────────────────────────────────────────────────────
-- 7. 두 프로젝트 비교(A/B) — 한 프로젝트 안의 clean/flawed 변형과는 다르다.
-- 예: 리뉴얼 전 사이트(a) vs 리뉴얼 후 사이트(b). 비교 시점의 결과는 그때그때
-- 각 프로젝트의 가장 최근 실행에서 읽는다 — 이 표는 짝짓기만 기억한다.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE ab_test (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name         text NOT NULL,
    a_project_id uuid NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    b_project_id uuid NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON ab_test (a_project_id);
CREATE INDEX ON ab_test (b_project_id);


-- =============================================================================
-- 7. 화면용 뷰
-- =============================================================================

-- [화면] 프로젝트 상세 — 테스트 행의 성공률 / 이탈률
CREATE VIEW v_test_stats AS
SELECT
    t.id                                                   AS test_id,
    t.project_id,
    t.name,
    t.created_at,
    count(j.id)                                            AS persona_count,
    round(100.0 * count(*) FILTER (WHERE j.goal_achieved)
          / nullif(count(j.id), 0), 1)                     AS success_rate,
    -- 이탈률은 '포기 + 맴돌다 중단'이다. 예산 상한으로 우리가 끊은 것은 제외한다.
    round(100.0 * count(*) FILTER (
              WHERE j.termination_reason IN ('gave_up', 'loop_detected'))
          / nullif(count(j.id), 0), 1)                     AS drop_rate
FROM test t
LEFT JOIN run     r ON r.test_id = t.id
LEFT JOIN journey j ON j.run_id  = r.id
GROUP BY t.id;

-- [화면] 프로젝트 목록 — 카드의 "진행한 테스트 N개 / N시간 전"
CREATE VIEW v_project_cards AS
SELECT
    p.id,
    p.name,
    p.category,
    count(t.id)                        AS test_count,
    coalesce(max(t.created_at), p.created_at) AS last_activity_at
FROM project p
LEFT JOIN test t ON t.project_id = p.id
GROUP BY p.id;

-- 기획서 6장 판정 기준: 지도가 재현율만 올렸으면 채택,
-- 재현율과 오탐이 같이 올랐으면 기각. A/B/C/D를 한 줄로 붙여 본다.
CREATE VIEW v_ablation_matrix AS
SELECT
    r.test_id,
    r.arm,
    sv.key          AS variant,
    r.map_enabled,
    s.recall,
    s.precision,
    s.fp_rate,
    s.scorer_version
FROM run r
JOIN site_variant sv ON sv.id = r.site_variant_id
LEFT JOIN run_score s ON s.run_id = r.id
ORDER BY r.test_id, r.arm;

COMMIT;
