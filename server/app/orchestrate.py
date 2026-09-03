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
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import exists, select

from . import ingest, pipeline_export, static_scan
from .db import session_scope
from .models import Defect, Journey, Mission, Persona, Run, SiteVariant, Test, TraitCombo

#: run.py가 살아있는 동안 결과 폴더를 다시 살펴보는 주기(초). RunningPage의
#: 폴링 주기(3초)보다 짧게 잡아야 화면이 갱신될 때 새 값이 이미 와 있다.
PROGRESS_POLL_SEC = 2.0

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


#: uxagent/config.py의 MAP_STEM_MAX_LEN과 반드시 같은 값이어야 한다 — 둘 중
#: 하나만 다르게 자르면 서버가 확인하는 캐시 파일명과 run.py가 실제로 쓰는
#: 캐시 파일명이 어긋난다.
_MAP_STEM_MAX_LEN = 150


def _map_stem(url: str) -> str:
    """uxagent.config.map_stem()의 --url 갈래를 그대로 옮긴 것.

    이 파일 위 설명대로 서버 프로세스는 agent-ux를 import하지 않는다
    (run.py를 subprocess로만 부른다) — 그래서 지도 캐시 여부를 먼저
    확인하려면 파일명 규칙을 여기서도 알아야 한다. uxagent/config.py의
    resolve_target(url=...)·map_stem()과 어긋나면 안 되니 로직을 바꿀 땐
    거기도 같이 고칠 것.

    호스트만 쓰던 예전 버전은 같은 호스트의 서로 다른 페이지(우리
    테스트베드의 clean/flawed 등)가 지도·스크린샷 캐시를 공유해 서로
    덮어썼다(2026-09-03 실측) — 그래서 경로까지 포함한 root를 키로 쓴다.
    """
    clean = url if "://" in url else "https://" + url
    parts = urlsplit(clean)
    origin = f"{parts.scheme}://{parts.netloc}" if parts.netloc else clean
    root = clean.rsplit("/", 1)[0] if clean.count("/") > 2 else origin
    raw_name = root.split("//", 1)[-1]
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in raw_name)
    return (safe.strip("_") or "site")[:_MAP_STEM_MAX_LEN]


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


def _mark_progress(run_id: uuid.UUID, log_dir: Path, seen: set[str]) -> None:
    """log_dir에 새로 나타난 <페르소나 코드>.json을 Journey.finished_at에 즉시 반영한다.

    trace.py의 Trace.finish()는 "한 명 끝날 때마다 즉시 저장한다"고 스스로 밝히듯
    페르소나 한 명이 끝나는 즉시 <code>.json을 쓴다 — index.json(전체 요약)만
    run.py가 전원 끝난 뒤 한 번에 쓴다. 그런데 지금까지는 ingest.ingest_run()이
    index.json이 있어야만 동작해서, run.py 서브프로세스가 끝날 때까지 DB의
    Journey.finished_at이 하나도 안 채워졌다 — 그 결과 "테스트 하기" 화면이 실제
    실행 내내(길면 수십 분) 0%에 멈춰 있는 것처럼 보였다. index.json을 기다리지
    않고 이미 도착한 개인 파일만으로 "끝났다"는 사실을 먼저 반영해 진행률이
    실시간으로 움직이게 한다. 스텝 상세 등 나머지 데이터는 여전히 프로세스 종료
    후 ingest_run()이 확정치로 덮어써 채운다.
    """
    if not log_dir.is_dir():
        return
    new_files = [p for p in log_dir.glob("*.json") if p.stem != "index" and p.stem not in seen]
    if not new_files:
        return
    with session_scope() as session:
        run = session.get(Run, run_id)
        if run is None:
            return
        for p in new_files:
            seen.add(p.stem)
            persona = session.scalar(
                select(Persona).where(Persona.test_id == run.test_id, Persona.code == p.stem)
            )
            if persona is None:
                continue
            journey = session.scalar(
                select(Journey).where(Journey.run_id == run_id, Journey.persona_id == persona.id)
            )
            if journey is None or journey.finished_at is not None:
                continue
            try:
                trace = json.loads(p.read_text(encoding="utf-8"))
                journey.finished_at = dt.datetime.fromisoformat(trace["ended_at"])
            except Exception:
                journey.finished_at = dt.datetime.now(dt.timezone.utc)


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

    log_dir = LOGS_DIR / str(run_id)
    seen: set[str] = set()
    # logs/ 자체는 첫 페르소나가 끝나야 trace.py가 만든다(Trace.finish()) —
    # stdout/stderr 로그 파일은 그보다 먼저 열어야 하니 여기서 미리 만든다.
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    # PIPE로 받으면 안 된다 — 진행 중엔 아무도 안 읽으니, run.py가 OS 파이프
    # 버퍼(보통 64KB)를 채우는 순간 자기 stdout/stderr 쓰기에서 멈춰버리고,
    # 이쪽은 time.sleep() 루프에서 그 죽은 프로세스가 끝나길 기다리며 같이
    # 멈춘다 — 서로를 막는 교착이다. 파일로 받으면 이 문제가 없다.
    with (LOGS_DIR / f"{run_id}.stdout.log").open("w+", encoding="utf-8") as out_f, \
         (LOGS_DIR / f"{run_id}.stderr.log").open("w+", encoding="utf-8") as err_f:
        proc = subprocess.Popen(args, cwd=AGENT_UX_DIR, stdout=out_f, stderr=err_f)
        while proc.poll() is None:
            time.sleep(PROGRESS_POLL_SEC)
            _mark_progress(run_id, log_dir, seen)
        returncode = proc.returncode
        # 막 끝난 마지막 몇 명은 poll() 루프가 끝난 뒤에야 파일이 도착했을 수 있다.
        _mark_progress(run_id, log_dir, seen)
        if returncode != 0:
            out_f.seek(0)
            err_f.seek(0)
            log.warning(
                "run.py 종료 코드 %s (run_id=%s)\nstdout:\n%s\nstderr:\n%s",
                returncode, run_id, out_f.read()[-2000:], err_f.read()[-2000:],
            )
    # 위 log.warning에 이미 꼬리를 남겼다 — 파일은 디스크에 계속 쌓일 이유가 없다.
    for suffix in (".stdout.log", ".stderr.log"):
        (LOGS_DIR / f"{run_id}{suffix}").unlink(missing_ok=True)

    with session_scope() as session:
        run = session.get(Run, run_id)
        if log_dir.exists():
            summary = ingest.ingest_run(session, run_id, log_dir)
            log.info("파이프라인 결과 적재: %s", summary)
            run.status = "done" if returncode == 0 else "failed"

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
