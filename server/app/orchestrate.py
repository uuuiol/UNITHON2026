""""테스트 하기"를 실제 파이프라인 실행으로 잇는다.

`api.start_run`이 Run/Journey 자리를 만든 직후 별도 스레드에서 `start_pipeline_run`을
부른다. 이 스레드가: DB Persona -> personas.json 내보내기 -> agent-ux/run.py 서브프로세스
실행 -> ingest.py 재사용으로 결과 적재 -> Run.status 갱신, 순서로 끝까지 처리한다.

새 가상환경을 만들지 않는다 — server/.venv 에 playwright 가 이미 있어서(썸네일
캡처용) `sys.executable`(지금 이 프로세스의 파이썬)로 agent-ux/run.py를 그대로 돌릴 수
있다. `cwd`만 agent-ux/ 로 잡으면 그 안의 `uxagent` 패키지도 상대 임포트로 찾는다.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import exists, select

from . import ingest, pipeline_export, static_scan
from .db import session_scope
from .models import Defect, Mission, Persona, Run, SiteVariant, Test, TraitCombo

log = logging.getLogger(__name__)

# uxagent/config.py의 PROVIDERS 각 항목의 key_env를 그대로 옮긴 것 — 그쪽을
# import하지 않는 이유는 서버 프로세스가 agent-ux/를 sys.path에 안 두기
# 때문이다(run.py를 subprocess로만 부른다). 프로바이더를 추가하면 여기도
# 같이 늘릴 것.
_PROVIDER_KEY_ENV = {
    "gemini": "GEMINI_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "groq": "GROQ_API_KEY",
}


def _has_llm_key() -> bool:
    """지금 UXAGENT_PROVIDER로 실제 호출이 될 만큼 키가 있는가.

    없으면 --mock을 붙인다 — 로컬 개발이나 키를 아직 안 넣은 배포에서
    "테스트 하기"가 API 에러로 죽는 대신 조용히 mock으로 도는 편이 낫다.
    """
    provider = os.environ.get("UXAGENT_PROVIDER", "gemini")
    key_env = _PROVIDER_KEY_ENV.get(provider)
    return bool(key_env and os.environ.get(key_env))

AGENT_UX_DIR = Path(__file__).resolve().parent.parent.parent / "agent-ux"
LOGS_DIR = AGENT_UX_DIR / "logs"
MAPS_DIR = AGENT_UX_DIR / "maps"
SHOTS_DIR = AGENT_UX_DIR / "shots"
PERSONAS_JSON_PATH = AGENT_UX_DIR / "personas" / "personas.json"

#: 답사 페이지 수 상한. agent-ux/server.py(예전 로컬 브리지)가 쓰던 값을
#: 그대로 가져왔다 — 실행마다가 아니라 사이트마다 한 번만 도니 넉넉해도 된다.
SURVEY_MAX_PAGES = "6"


def _map_stem(url: str) -> str:
    """uxagent.config.map_stem()의 --url 갈래를 그대로 옮긴 것.

    이 파일 위 설명대로 서버 프로세스는 agent-ux를 import하지 않는다
    (run.py를 subprocess로만 부른다) — 그래서 지도 캐시 여부를 먼저
    확인하려면 파일명 규칙을 여기서도 알아야 한다. uxagent/config.py의
    resolve_target(url=...)·map_stem()과 어긋나면 안 되니 로직을 바꿀 땐
    거기도 같이 고칠 것.
    """
    clean = url if "://" in url else "https://" + url
    host = urlsplit(clean).netloc
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in host)
    return safe.strip("_") or "site"


def _ensure_site_map(target_url: str, run_id: uuid.UUID) -> bool:
    """이 사이트의 지도가 이미 있으면 그대로 쓰고, 없으면 답사부터 한 번 돌린다.

    지도가 있어야 페르소나가 "이 사이트에 어떤 화면·버튼이 있는지" 미리 알고
    움직인다 — 없으면 매 스텝 화면을 새로 읽으며 헤매다 첫 화면에서 포기하는
    비율이 크게 는다(실측: flawed 사이트 3명 전원 첫 화면 이탈).

    답사 자체가 실패해도(사이트 접근 실패, LLM 판단 표현 재생성 3회 초과 등)
    전체 테스트를 막지 않는다 — 지도 없이 도는 이전 동작으로 조용히 떨어진다.
    반환값은 "지도를 쓸 수 있는가"다.
    """
    stem = _map_stem(target_url)
    map_path = MAPS_DIR / f"site_map_{stem}.json"
    if map_path.exists():
        return True

    args = [
        sys.executable, "survey.py",
        "--url", target_url,
        "--yes",
        "--max-pages", SURVEY_MAX_PAGES,
        "--shots-dir", str(SHOTS_DIR / stem),
    ]
    if not _has_llm_key():
        # 답사는 페이지마다 LLM을 부른다 — 키가 없으면 어차피 run.py도
        # --mock으로 떨어지니 답사도 같이 mock으로 맞춘다. (mock 답사는
        # 스크린샷을 남기지 않는다 — uxagent/survey.py survey_page 참고.)
        args.append("--mock")

    log.info("사이트 지도가 없어 답사부터 시작합니다: %s (run_id=%s)", target_url, run_id)
    result = subprocess.run(
        args, cwd=AGENT_UX_DIR, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0 or not map_path.exists():
        log.warning(
            "답사 실패, 지도 없이 진행합니다 (run_id=%s, exit=%s)\nstdout:\n%s\nstderr:\n%s",
            run_id, result.returncode, result.stdout[-2000:], result.stderr[-2000:],
        )
        return False
    log.info("답사 완료, 지도 저장됨: %s (run_id=%s)", map_path, run_id)
    return True


def start_pipeline_run(run_id: uuid.UUID) -> None:
    """백그라운드 스레드 진입점. 예외를 여기서 다 삼킨다 — 스레드 안 예외는 아무도 못 받고,
    그 사실만으로 서버가 죽으면 안 된다. 실패는 Run.status="failed" 로 화면에 드러난다.
    """
    try:
        _run(run_id)
    except Exception:
        log.exception("파이프라인 실행 실패 (run_id=%s)", run_id)
        try:
            with session_scope() as session:
                run = session.get(Run, run_id)
                if run is not None:
                    run.status = "failed"
        except Exception:
            log.exception("Run.status=failed 기록도 실패 (run_id=%s)", run_id)


def _run(run_id: uuid.UUID) -> None:
    with session_scope() as session:
        run = session.get(Run, run_id)
        test = session.get(Test, run.test_id)
        mission = session.scalar(select(Mission).where(Mission.test_id == test.id))
        personas = list(
            session.scalars(select(Persona).where(Persona.test_id == test.id))
        )
        combos = {c.id: c for c in session.scalars(select(TraitCombo))}

        payload = pipeline_export.build_personas_json(test, mission, personas, combos)
        target_url = test.target_url
        goal = mission.prompt
        expect = mission.expect

    PERSONAS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    PERSONAS_JSON_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    has_map = _ensure_site_map(target_url, run_id)

    args = [
        sys.executable, "run.py",
        "--url", target_url,
        "--goal", goal,
        "--run-id", str(run_id),
        "--all", "--yes",
        "--quiet",
    ]
    if not has_map:
        args.append("--no-map")
    if not _has_llm_key():
        # UXAGENT_PROVIDER에 맞는 키가 /etc/moji-api.env에 없다 — API 에러로
        # 실행이 죽는 대신 mock으로 조용히 떨어진다.
        args.append("--mock")
        log.warning("LLM 키 없음(UXAGENT_PROVIDER=%s) — --mock으로 실행 (run_id=%s)",
                    os.environ.get("UXAGENT_PROVIDER", "gemini"), run_id)
    if expect:
        args += ["--expect", expect]

    result = subprocess.run(
        args, cwd=AGENT_UX_DIR, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        log.warning(
            "run.py 종료 코드 %s (run_id=%s)\nstdout:\n%s\nstderr:\n%s",
            result.returncode, run_id, result.stdout[-2000:], result.stderr[-2000:],
        )

    log_dir = LOGS_DIR / str(run_id)
    with session_scope() as session:
        run = session.get(Run, run_id)
        if log_dir.exists():
            summary = ingest.ingest_run(session, run_id, log_dir)
            log.info("파이프라인 결과 적재: %s", summary)
            run.status = "done" if result.returncode == 0 else "failed"

            # 정답지(Defect)가 로드된 프로젝트(ux-testbed 기반)에서만 채점을 돌린다 —
            # static_scan은 testbed의 고정 6페이지 경로를 그대로 찔러보는 전용
            # 스캐너라, 정답지 없는 일반 사이트에 돌리면 전부 404만 나고 낭비다.
            variant = session.get(SiteVariant, run.site_variant_id)
            has_defects = session.scalar(
                select(exists().where(Defect.project_id == variant.project_id))
            )
            if has_defects:
                try:
                    asyncio.run(static_scan.run_static_scan(session, run_id))
                except Exception:
                    log.exception("자동 채점 실패 (run_id=%s)", run_id)
        else:
            log.warning("결과 로그 폴더가 없습니다: %s (run_id=%s)", log_dir, run_id)
            run.status = "failed"
        run.finished_at = dt.datetime.now(dt.timezone.utc)
