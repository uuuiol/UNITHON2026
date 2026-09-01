import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import thumbnails
from .api import router


@asynccontextmanager
async def lifespan(_: FastAPI):
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
