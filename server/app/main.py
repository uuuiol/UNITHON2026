import datetime as dt
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from . import thumbnails
from .api import router
from .db import session_scope
from .models import Run

log = logging.getLogger(__name__)


def _fail_orphaned_runs() -> None:
    """서버가 막 떴다는 것은 파이프라인 스레드가 전부 죽었다는 뜻이다.

    파이프라인은 `orchestrate.start_pipeline_run`을 도는 daemon 스레드가 끝날 때
    Run.status를 done/failed로 옮긴다(orchestrate.py). 그런데 그 전에 프로세스가
    재시작되면(배포, `systemctl restart moji-api`, 키 갱신 등) 스레드만 사라지고
    DB의 Run 행은 "running"에 박제된 채 남는다 — 그 뒤로는 아무도 다시 손대지
    않으므로 `/api/runs/active`가 이 죽은 실행을 "지금 도는 실행"으로 계속
    보여준다. 진행률은 그 순간 그대로 멈춰 있어 영원히 0%(또는 임의의 값)로
    고정된 것처럼 보인다. 새 프로세스가 뜰 때 이런 좀비를 failed로 정리한다.
    """
    with session_scope() as session:
        orphaned = list(session.scalars(select(Run).where(Run.status == "running")))
        for run in orphaned:
            run.status = "failed"
            run.finished_at = dt.datetime.now(dt.timezone.utc)
        if orphaned:
            log.warning("시작 시 정리한 좀비 실행 %d건: %s",
                        len(orphaned), [str(r.id) for r in orphaned])


@asynccontextmanager
async def lifespan(_: FastAPI):
    _fail_orphaned_runs()
    yield
    # 썸네일용 Chromium 이 떠 있으면 같이 내린다. 안 내리면 프로세스가 안 죽는다.
    await thumbnails.shutdown()

app = FastAPI(title="AI 페르소나 UX 테스트 API", version="0.1.0", lifespan=lifespan)

# 기본값은 로컬 Vite 개발 서버. 배포판(프론트가 다른 오리진 — 예: Amplify)에서는
# CORS_ORIGINS 환경변수(콤마 구분)로 실제 프론트 주소를 넣는다.
_default_origins = "http://localhost:5173,http://localhost:5180"
allow_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", _default_origins).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
