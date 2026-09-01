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
import subprocess
import sys
import uuid
from pathlib import Path

from sqlalchemy import exists, select

from . import ingest, pipeline_export, static_scan
from .db import session_scope
from .models import Defect, Mission, Persona, Run, SiteVariant, Test, TraitCombo

log = logging.getLogger(__name__)

AGENT_UX_DIR = Path(__file__).resolve().parent.parent.parent / "agent-ux"
LOGS_DIR = AGENT_UX_DIR / "logs"
PERSONAS_JSON_PATH = AGENT_UX_DIR / "personas" / "personas.json"


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

    args = [
        sys.executable, "run.py",
        "--url", target_url,
        "--goal", goal,
        "--run-id", str(run_id),
        "--all", "--yes",
        "--mock",       # 이 컴퓨터엔 LLM API 키가 없다. 키가 생기면 이 플래그만 뗀다.
        "--no-map",     # 답사(지도) 파이프라인은 아직 연결 전이다.
        "--quiet",
    ]
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
