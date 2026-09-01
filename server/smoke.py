"""API 전 구간 스모크 테스트.

화면 순서(프로젝트 → 테스트 → 미션 → 페르소나 → 확인) 그대로 HTTP 로 두드린다.
DB가 실제로 값을 받아 돌려주는지, 기획서의 불변식이 지켜지는지 한 번에 본다.

    python smoke.py
"""

from __future__ import annotations

import sys
import uuid

import httpx

BASE = "http://localhost:8000"
ok = 0
failed: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global ok
    if condition:
        ok += 1
        print(f"  PASS  {name}")
    else:
        failed.append(name)
        print(f"  FAIL  {name} {detail}")


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=20.0) as c:
        print("health")
        check("서버 응답", c.get("/health").json() == {"ok": True})

        print("\n로그인 없이 호출")
        anon = c.get("/api/projects")
        check("토큰 없으면 401", anon.status_code == 401, anon.status_code)

        print("\n[화면] 회원가입")
        signup = c.post(
            "/api/auth/signup",
            json={
                "email": f"smoke-{uuid.uuid4().hex[:8]}@example.com",
                "password": "smoke-test-password",
                "name": "스모크",
            },
        )
        check("회원가입", signup.status_code == 201, signup.text)
        token = signup.json()["token"]
        c.headers["Authorization"] = f"Bearer {token}"

        print("\n[화면] 새 프로젝트")
        project = c.post(
            "/api/projects",
            json={
                "name": f"쇼핑몰 v.{uuid.uuid4().hex[:4]}",
                "category": "쇼핑몰",
                "target_url": "http://localhost:8080",
            },
        ).json()
        pid = project["id"]
        check("프로젝트 생성", bool(pid))

        print("\n[화면] 프로젝트 목록")
        cards = c.get("/api/projects").json()
        check("목록에 나타남", any(row["id"] == pid for row in cards))
        card = next(row for row in cards if row["id"] == pid)
        check("테스트 0개로 시작", card["test_count"] == 0, card)

        print("\n[화면] 새 테스트")
        test = c.post(
            f"/api/projects/{pid}/tests",
            json={"name": "결제 화면 사용성 테스트", "device": "laptop-1280", "target_url": "http://localhost:8080/flawed/"},
        ).json()
        tid = test["id"]
        check("테스트 생성", bool(tid))

        print("\n[화면] 미션 설정")
        mission = c.put(
            f"/api/tests/{tid}/mission",
            json={
                "prompt": "원하는 네일 디자인을 선택하고 견적 요청까지 완료해 주세요.",
                "success_criteria": "견적 요청 완료 화면에 도착하면 성공으로 볼게요.",
            },
        )
        check("미션 저장", mission.status_code == 200, mission.text)

        too_long = c.put(
            f"/api/tests/{tid}/mission",
            json={"prompt": "가" * 201, "success_criteria": "x"},
        )
        # UI 카운터가 200자다. 잘린 미션이 조용히 저장되면 100명이 다른 일을 한다.
        check("200자 초과 미션 거부", too_long.status_code == 422, too_long.status_code)

        print("\n[화면] 페르소나 (총원 + 비율 슬라이더)")
        specs = [
            {"age_band": "10s", "total": 10, "female_percent": 50},
            {"age_band": "20s", "total": 40, "female_percent": 60},
            {"age_band": "30s", "total": 30, "female_percent": 30},
            {"age_band": "40s", "total": 15, "female_percent": 60},
            {"age_band": "50s", "total": 5, "gender_agnostic": True},
            {"age_band": "60s+", "total": 0, "enabled": False},
        ]
        saved = c.put(f"/api/tests/{tid}/persona-specs", json=specs)
        check("인원표 저장", saved.status_code == 200, saved.text)
        check("총원 100명", saved.json().get("total") == 100, saved.json())

        bad_ratio = c.put(
            f"/api/tests/{tid}/persona-specs",
            json=[{"age_band": "10s", "total": 10, "female_percent": 140}],
        )
        check("비율 0~100 밖은 거부", bad_ratio.status_code == 422, bad_ratio.status_code)

        print("\n[화면] 확인")
        review = c.get(f"/api/tests/{tid}/review").json()
        check("총원 100명", review["personas"]["total"] == 100, review["personas"])
        rows = {r["age_band"]: r for r in review["personas"]["breakdown"]}
        check("20대 여성 24 / 남성 16", rows["20s"]["female"] == 24 and rows["20s"]["male"] == 16, rows.get("20s"))
        check("50대는 상관없음 5", rows["50s"]["any"] == 5, rows.get("50s"))
        check("60대는 빠짐", "60s+" not in rows, list(rows))
        # 기획서 7장: 페르소나 100명의 이미지 호출은 0회다.
        check("비전 호출 0회", review["estimate"]["vision_calls"] == 0, review["estimate"])
        check("추정치임이 표시됨", review["estimate"]["measured"] is False)

        print("\n연결 검사")
        conn = c.post("/api/connectivity/check", json={"url": "example.com"}).json()
        check("도달 가능", conn["ok"] and conn["status"] == 200, conn)
        check("임베드 가능 여부 분리 보고", "embeddable" in conn)

    print(f"\n{ok} passed, {len(failed)} failed")
    for name in failed:
        print(f"  - {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
