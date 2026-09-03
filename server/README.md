# 백엔드 — AI 페르소나 UX 테스트

기획서(2026-08-25)의 5단계 파이프라인과 Figma UI를 한 DB에 담는다.

핵심 방침 하나: **기획서 4장의 "설계 결정"을 주석이 아니라 제약조건으로 넣었다.**
기획서가 스스로 밝힌 위험이 "시끄럽게 실패하는 것보다 조용히 틀린 숫자가 나오는 쪽이
위험하다"이기 때문이다. 문서에만 적힌 규칙은 마감 전날 밤에 조용히 깨진다.

---

## 1. 지금 상태 — 실제로 돈다

| 항목 | 상태 |
|---|---|
| `db/schema.sql` | Postgres 정본 스키마 (Postgres 미설치라 **적재는 미검증**) |
| SQLite 기동 | **검증 완료** — 테이블 20개 생성, API 전 구간 통과 |
| `smoke.py` | **18/18 통과** (프로젝트→테스트→미션→페르소나→확인→연결검사) |
| `app/defects_parser.py` | 68건 · 25/30/13 · 22/10/16/20 재현 |
| `app/personas.py` | 100명 조립, **고유 쌍 100/100** 실측 |
| `app/scoring.py` | 재현율·정밀도·오탐률 (채점기 미연결) |

기본 DB는 SQLite다. 처음 켜는 사람이 Docker부터 설치해야 하면 백엔드는 영영 안 돌아간다.
같은 모델이 Postgres에서도 그대로 뜨도록 `app/types.py` 가 방언 차이를 흡수한다
(UUID↔CHAR(36), JSONB↔JSON, ENUM↔문자열).

---

## 2. 띄우기

```bash
cd server
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt

.venv/Scripts/python.exe -m app.bootstrap          # SQLite 테이블 생성
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

→ `http://localhost:8000/docs`

전 구간 확인:

```bash
.venv/Scripts/python.exe smoke.py     # 18 passed, 0 failed
```

정답지·특성 조합 적재 (프로젝트를 만든 뒤 그 id로):

```bash
.venv/Scripts/python.exe -m app.seed --project-id <uuid> --defects ../ux-testbed/DEFECTS.md
# 특성 조합 16개 적재
# 정답지 68건 적재 (68건 · 25/30/13 · 22/10/16/20 검증 통과)
```

DB 없이 정답지 파싱만 확인:

```bash
python -m app.defects_parser ../ux-testbed/DEFECTS.md
# 1280 뷰포트에서 잡을 수 없음: ['D-28', 'D-29', 'D-30']
```

### Postgres 로 바꿀 때

실측·발표용은 Postgres 를 쓴다. `db/schema.sql` 이 정본이고, 기획서의 불변식을 지키는
CHECK 제약이 거기 온전히 들어 있다.

```bash
docker compose up -d db      # 최초 기동 시 db/schema.sql 자동 적재
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/uxlab
```

---

## 3. 테이블 지도

```
project ─┬─ site_variant (clean / flawed)  ─── site_map ─── site_map_screen ─┐
         │                                                                   │
         ├─ defect (정답지 68건)                          screen_measurement ─┘
         │                                                (코드가 잰 수치만)
         └─ test ─┬─ mission ─── goal (11)
                  ├─ persona_spec (연령대×성별 인원표)
                  ├─ persona (100) ── trait_combo (16)
                  └─ run (A/B/C/D) ─── journey ─── step ─── guard_hit
                                          │
                              finding ─── finding_match ─── run_score
                                                    │
                                                 defect
llm_call ── run / journey / step
```

**5단계와의 대응**

| 기획서 단계 | 테이블 |
|---|---|
| 1 답사 | `site_map`, `site_map_screen`, `screen_measurement` |
| 2 페르소나 생성 | `trait_combo`, `goal`, `persona` |
| 3 탐색 | `run`, `journey`, `step` |
| 4 재생 | 위 3개를 그대로 읽는다 (`step.idx` 순서) |
| 5 채점 | `finding`, `finding_match`, `run_score` |

---

## 4. 설계 결정이 어디에 제약으로 들어갔나

기획서 4장 항목별로, 그 규칙을 깨는 INSERT가 어디서 막히는지.

| 기획서의 규칙 | 어긴 데이터가 막히는 곳 |
|---|---|
| 지도는 서술만, 수치는 코드가 잰다 | `screen_measurement.measured_by = 'code'` CHECK. LLM이 지어낸 대비·좌표가 들어올 컬럼 자체가 없다. 서술은 `site_map_screen.narrative` 로 분리. |
| 답사자는 판단하지 않는다 | `guard_hit` — 금칙어에 걸려 버린 화면을 **버렸다는 사실**로 남긴다. 조용히 사라지면 재현율을 설명할 수 없다. |
| 목표는 10개가 아니라 11개 | `persona` 의 `UNIQUE (test_id, trait_combo_id, goal_id)` + `goal.idx BETWEEN 0 AND 10`. 조립 코드도 `gcd(16, 11) == 1` 을 검사한다. |
| 허용 행동 목록을 러너가 강제한다 | `step.allowed` / `step.executed` 를 별도 컬럼으로 두고 `CHECK (allowed OR NOT executed)`. 차단된 행동은 실행 없이 기록만 남는다. |
| 성격마다 체류 시간이 다르다 | `trait_combo.dwell_ms`. 10초 팝업(D-26)에 도달 가능한 인원을 `/personas/assemble` 응답이 돌려준다. 0이면 '못 잡음'이 아니라 '마주친 적 없음'이다. |
| 장바구니 키는 페르소나에 넣지 않는다 | `cart_storage_key` 의 소유자가 `site_variant`. 페르소나 테이블에는 그 컬럼이 없다. |
| 종료 사유를 여섯 가지로 나눈다 | `termination_reason` ENUM 6종 + `journey_achieved_matches_reason` CHECK. 예산 상한(`budget_cap`)은 이탈률 집계에서 빠진다. |
| 탐색 중에는 결함 분석을 시키지 않는다 | `finding` 은 `scorer_version` 을 필수로 받는다. 실행 경로에는 이 테이블에 쓰는 코드가 없다. |
| 정상판을 대조군으로 같이 돌린다 | `POST /api/projects` 가 clean/flawed 두 변형을 항상 함께 만든다. `run` 의 `UNIQUE (test_id, arm)` 이 A/B/C/D 를 한 벌로 고정한다. |
| 진행률은 사람 수로 세지, arm 수로 세지 않는다 | 대조군 설계상 페르소나 N명은 arm(결함판/정상판)마다 한 번씩, 실제로는 2N번 돈다. 하지만 "N명 설정 → 화면에 2N명"으로 보이면 두 배로 잘못 돈 것처럼 헷갈린다(2026-09-03 실측 — 3명 설정에 "0/6명"으로 보임). `GET /api/runs/active`(api.py::active_run)는 그래서 Journey를 persona_id로 묶어, 그 사람의 **모든** arm이 끝나야 그 사람을 "마쳤다"고 센다 — 총원도 N(사람 수)이지 2N이 아니다. |
| 이미지는 답사 한 번에만 | `llm_call` 의 `CHECK (stage <> 'explore' OR modality = 'text')`. 스텝마다 이미지를 넣는 코드가 들어오면 즉시 터진다. |
| 예상 호출 수를 보여준 뒤 한 번 더 묻는다 | `run` 의 `CHECK (persona_count <= 1 OR confirmed_at IS NOT NULL)`. 확인 없이 100명이 도는 경로가 없다. |
| 375px 3건은 원리적으로 못 잡는다 | `defect.requires_viewport_w`. `scoring.py` 가 재현율 분모에서 뺀다 — '못 잡음'과 '잡을 수 없음'을 섞지 않는다. |

---

## 5. 판단이 필요했던 지점 두 가지

### (1) UI의 페르소나와 기획서의 페르소나가 다른 모델이다

Figma 화면은 **연령대별 총원 + 성별 비율 슬라이더**를 받는다. 기획서는
**특성 조합 16 × 목표 11**로 100명을 조립한다. 둘은 같은 것이 아니다.

분포(`persona_spec`)와 개인(`persona`)을 **다른 테이블로 두고**, `app/personas.py`가
분포를 편 뒤 i번째 사람에게 `combo[i % 16]`, `goal[i % 11]`을 준다.
연령·성별은 인원표에서, 체류 시간·최대 스텝은 특성 조합에서 온다.

성별 인원은 `total × female_percent` 에서 **파생**되며 따로 저장하지 않는다.
둘 다 저장하면 한쪽만 갱신되는 순간 어느 쪽이 진실인지 알 수 없어진다.

### (2) 이탈률의 정의

화면에는 성공률·이탈률 두 숫자만 있다. 종료 사유는 여섯 가지다.
`gave_up + loop_detected` 만 이탈로 세고, `budget_cap`(우리가 끊음)과
`runtime_error`(우리 버그)는 제외했다. 기획서 4장이 정확히 이 오염을 경고한다.
`step_budget_exhausted`(스텝 소진)도 뺐다 — 포기와 다른 신호다.

바꾸려면 `v_test_stats` 뷰와 `api.list_tests` 두 곳만 고치면 된다.

---

## 6. 다음에 해야 할 것

1. **Postgres를 띄우고 `schema.sql` 적재를 실제로 확인** — 이 PC에는 Postgres도 Docker도
   없어서 DDL이 문법만 맞고 실행은 안 해봤다.
2. 파이프라인 스크립트(`scout.py` / `run.py`)가 JSON 대신 이 DB에 쓰도록 연결.
   `logs/{run_id}/P0xx.json` 은 지우지 말고 `journey.log_path` 로 함께 둘 것 —
   31MB를 DB에 넣을 이유가 없다.
3. 채점기(`scorer_version` 을 붙여서) 구현 → `run_score` 적재 → `/ablation` 이 A/B/C/D를
   한 표로 돌려준다. 기획서 6장의 채택/기각 판정이 이 표 하나로 끝난다.
4. `estimates.py` 의 단가·소요는 **추정치다.** 4회 실행 뒤 실측으로 갈아끼우고
   `measured=True` 로 바꿀 것. 화면은 이 값을 보고 '약'을 붙일지 정한다.
