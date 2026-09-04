"""전역 설정 상수.

모델 이름은 자주 바뀌므로 여기에만 두고, 콘솔에서 확인 후 교체한다.
프로바이더는 PROVIDER 하나로 갈아끼운다 (gemini <-> qwen).
"""
import os

# ── 프로바이더 선택 ────────────────────────────────────────────────
# "gemini" | "qwen". 둘 다 OpenAI 호환 엔드포인트라 SDK는 openai 하나로 끝난다.
PROVIDER = os.environ.get("UXAGENT_PROVIDER", "gemini")

PROVIDERS = {
    # Google AI Studio. OpenAI 호환 레이어.
    # 2026-08-25 실측: /v1beta/models 로 확인한 실제 가용 목록에서 고른 이름이다.
    #   gemini-2.5-* 계열은 "no longer available to new users"(404)라 쓰면 안 된다.
    #   별칭(gemini-pro-latest, gemini-flash-latest)은 조용히 바뀌므로 실험
    #   재현성을 위해 버전을 못박은 이름을 쓴다.
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        # 한 모델이 과부하(503)면 같은 등급의 다른 모델로 넘어간다.
        # 답사는 40스텝을 이어 달려야 해서 한 번의 일시 장애로 죽으면 안 된다.
        # 2026-08-25 실측 지연: 3.6-flash 3.8초 / 3.5-flash 3.1초 /
        # 3.1-flash-lite 2.7초 / **3.7-flash 176초(혼잡)** / 2.5 계열은 이 키에서 404.
        # 같은 등급이라도 그날 혼잡한 모델이 있다. 대체 목록의 값어치가 여기 있다.
        "fallbacks": {
            "survey":  ["gemini-3.5-flash", "gemini-3.1-flash-lite"],
            "explore": ["gemini-3.5-flash", "gemini-3.1-flash-lite"],
            "goals":   ["gemini-3.5-flash", "gemini-3.1-flash-lite"],
            "analyze": ["gemini-3.5-flash", "gemini-3.1-flash-lite"],
        },
        # 답사(비전). pro 는 이미지 한 장에 약 47초라 41스텝이면 30분이 넘고,
        # 실측 서술 품질도 flash 가 오히려 더 자세했다 (2026-08-25 비교).
        # 답사는 스텝마다 이미지를 보내므로 속도가 곧 실행 가능성이다.
        "model_survey":  "gemini-3.6-flash",
        "model_goals":   "gemini-3.6-flash",        # 목표 생성. 호출 3회 미만
        "model_explore": "gemini-3.6-flash",        # 탐색 루프. 스텝마다 호출 → 저가
        "model_analyze": "gemini-3.1-pro-preview",  # 사후 분석. 실행당 1회
        # 100만 토큰당 USD. 2026-08-25 웹 조사 기준이며 **콘솔 확인 전**이다.
        # Gemini 3.1 Pro 가 $2/$12 로 조사돼 탐색 루프에 쓰면 안 되는 단가다
        # (1만 호출이면 $58). 탐색은 반드시 flash 계열로 둘 것.
        # 100만 토큰당 USD. 2026-08-25 웹 조사 기준이며 **콘솔 확인 전**이다.
        # 3.6-flash 는 2026-12-31 까지 프로모션가이고 2027-01-01 에 2배가 된다.
        "prices": {
            "gemini-3.6-flash":       {"input": 0.75, "output": 3.75},
            "gemini-3.5-flash":       {"input": 0.75, "output": 3.75},
            "gemini-3.1-flash-lite":  {"input": 0.10, "output": 0.40},
            "gemini-3.7-flash":       {"input": 0.75, "output": 3.75},
            "gemini-3.1-pro-preview": {"input": 2.00, "output": 12.00},
        },
        "price": {"input": 0.75, "output": 3.75},   # 목록에 없는 모델의 기본값
    },
    # Alibaba Cloud Model Studio.
    # '-intl'이 빠지면 중국 본토 계정으로 붙어 401이 난다.
    "qwen": {
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "key_env": "DASHSCOPE_API_KEY",
        # 2026-05 에 3티어로 재편되어 3.6-plus / 3.6-flash 가 권장 기본이 됐다.
        # 이름은 자주 바뀌므로 `python check-llm.py --list` 로 이 키에서 실제로
        # 보이는지 확인하고 고칠 것. 목록에 없으면 404가 난다.
        "model_survey":  "qwen3-vl-plus",    # 비전. 답사 전용
        "model_goals":   "qwen3.6-plus",
        "model_explore": "qwen3.6-flash",    # 스텝마다 호출 → 반드시 flash 등급
        "model_analyze": "qwen3.6-plus",
        # 2026-08-25 웹 조사: qwen3.5-plus $0.40/$2.40, qwen3.5-flash $0.10/$0.40.
        # 더 싼 등급(qwen3.7-flash $0.03/$0.13)도 있으나 한국어 품질 미확인.
        "prices": {
            "qwen3.6-plus":  {"input": 0.40, "output": 2.40},
            "qwen3.6-flash": {"input": 0.10, "output": 0.40},
            "qwen3-vl-plus": {"input": 0.40, "output": 2.40},
        },
        "price": {"input": 0.40, "output": 2.40},
    },
    # Groq. 오픈웨이트 모델을 호스팅한다. OpenAI 호환.
    # 2026-09-03 check-llm.py --list 로 이 키에서 실제 접근되는 모델만 확인 후
    # 고름 — 웹에서 조사했던 llama-3.1-8b-instant/llama-3.3-70b-versatile은
    # 이 계정에서 404였다(계정마다 열린 모델이 다를 수 있음. 바뀌면
    # `python check-llm.py --list`로 다시 확인할 것).
    # ⚠ `openai/` 접두어가 실제로 필요하다 — /v1/models 목록·check-llm.py의
    #   요약 표시는 접두어 없이 "gpt-oss-20b"로 보여주지만, 접두어 없이
    #   호출하면 그대로 404다(curl로 직접 재현·확인함, 2026-09-03).
    #   gpt-oss-20b  : OpenAI가 공개한 오픈웨이트 모델. 100만 토큰당 $0.075/$0.30
    #   gpt-oss-120b : 같은 계열 대형판. 100만 토큰당 $0.15/$0.60
    # explore는 스텝마다 불려서 저가 20b, goals/analyze는 실행당 소수 호출이라
    # 120b. Groq는 신용카드 없이 가입되고 무료 티어 요청·토큰 한도가 있지만
    # (여기 적힌 단가는 그 한도를 넘는 유료 구간 기준), 이 한도의 정확한 값은
    # 계정마다 달라 콘솔에서 직접 확인 전이다.
    # ⚠ price를 0이 아니라 실제 단가로 채워야 run.py의 --max-usd 예산 상한이
    #   제대로 걸린다 — 0으로 두면 이 상한이 죽는다(이전 버전의 실수).
    # ⚠ 비전(답사/survey)용 모델은 이 목록에 없다 — 지금은 --no-map(답사
    #   미연결)이라 안 쓰이지만, 답사를 나중에 연결하면 model_survey를 다른
    #   프로바이더로 갈아끼워야 한다.
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "fallbacks": {
            "explore": ["openai/gpt-oss-120b"],
        },
        "model_survey":  "openai/gpt-oss-120b",  # 비전 아님 — 답사 연결 전까지 미사용
        "model_goals":   "openai/gpt-oss-120b",
        "model_explore": "openai/gpt-oss-20b",
        "model_analyze": "openai/gpt-oss-120b",
        "prices": {
            "openai/gpt-oss-20b":  {"input": 0.075, "output": 0.30},
            "openai/gpt-oss-120b": {"input": 0.15,  "output": 0.60},
        },
        "price": {"input": 0.075, "output": 0.30},
    },
}


def role_provider(role: str) -> str:
    """역할별 프로바이더. 없으면 전역 PROVIDER 를 쓴다.

    비용 구조가 역할마다 완전히 다르기 때문에 열어둔다.
      답사(survey)  — 호출 50회인데 그 결과를 **100명이 읽는다.** 품질 우선.
      탐색(explore) — 호출 1만 회. 값 우선.
    한쪽은 좋은 모델, 한쪽은 싼 모델로 갈라 쓰는 것이 합리적이다.

        setx UXAGENT_PROVIDER_SURVEY  gemini
        setx UXAGENT_PROVIDER_EXPLORE qwen
    """
    return os.environ.get("UXAGENT_PROVIDER_%s" % role.upper(), PROVIDER)


def provider(name: str | None = None) -> dict:
    name = name or PROVIDER
    if name not in PROVIDERS:
        raise ValueError(f"알 수 없는 프로바이더: {name} (가능: {list(PROVIDERS)})")
    return PROVIDERS[name]


def api_key(name: str | None = None) -> str | None:
    """API 키는 환경변수에서만 읽는다. 하드코딩 금지."""
    return os.environ.get(provider(name)["key_env"])


def model(role: str, name: str | None = None) -> str:
    return provider(name)[f"model_{role}"]


def models(role: str, name: str | None = None) -> list[str]:
    """1순위 모델 + 대체 모델들. 앞에서부터 시도한다."""
    p = provider(name)
    return [p[f"model_{role}"]] + list((p.get("fallbacks") or {}).get(role, []))


# 역할별 온도. 답사·분석은 사실 기술이라 0.0, 탐색은 행동 다양성으로 1.0.
TEMP_SURVEY = 0.0
TEMP_GOALS = 0.7
TEMP_EXPLORE = 1.0
TEMP_ANALYZE = 0.0

# 429(잔액)·503(과부하)·타임아웃이 잦다. 503 은 몇 초 뒤면 풀리는 경우가 많아
# 짧은 백오프로 포기하면 멀쩡한 실행이 통째로 죽는다 (2026-08-25 실제로 겪음).
# 대체 모델이 여러 개이므로 한 모델에 오래 매달릴 이유가 없다.
# 재시도 5회 x 백오프 45초 x 모델 4개면 한 스텝에 최악 40분이 나온다
# (2026-08-25 실제로 겪음 — 답사가 15분간 멈춰 있었다).
MAX_RETRIES = 3
RETRY_BACKOFF = (2, 5, 12)   # 초. 인덱스가 시도 횟수
# 비전 호출은 텍스트보다 오래 걸리지만, 120초는 '망이 끊겼는데 기다리는' 시간이
# 되기 쉽다. 스크린샷 한 장(약 120KB)은 정상이면 10초 안에 돌아온다.
REQUEST_TIMEOUT = 60.0


def price_of(model_name: str | None, name: str | None = None) -> dict:
    """모델별 단가. 모르는 모델이면 프로바이더 기본값을 쓴다."""
    p = provider(name)
    return (p.get("prices") or {}).get(model_name or "", p["price"])


def estimate_cost(tok_in: int, tok_out: int, name: str | None = None,
                  model_name: str | None = None) -> float:
    p = price_of(model_name, name)
    return round(tok_in / 1_000_000 * p["input"] + tok_out / 1_000_000 * p["output"], 6)


# ── 에이전트 루프 ──────────────────────────────────────────────────
MAX_STEPS = 30
# 프롬프트에 넣을 최근 스텝 수. 전체 누적은 금지지만 3은 너무 짧았다.
# 장바구니에 담은 사실이 3스텝 만에 창 밖으로 밀려나 "아직 안 담았나?" 하고
# 되돌아가는 맴돌이가 clean 사이트에서 2건 나왔다 (P011, P016).
# 한 줄이 약 40토큰이라 6줄이어도 프롬프트의 15% 안쪽이다.
HISTORY_WINDOW = 6
# 항상 남기는 맨 앞 스텝 수. 뒤에서만 자르면 목표를 이룬 결정적 행동이
# 먼저 사라진다 (explore.history_block 주석 참고).
HISTORY_HEAD = 2
# 프롬프트에 싣는 요소 개수. 실측상 프롬프트의 3분의 2가 이 목록이다.
# 접힘선 위부터 정렬되므로 자르면 안 보이는 것(푸터·관련상품)부터 빠진다.
# 45 -> 25 로 줄이면 호출당 약 25% 절감된다.
PROMPT_ELEMENT_LIMIT = 25
# 프롬프트에 싣는 '지금 화면에 보이는 글자' 길이.
#
# 300자였을 때 페르소나가 본문을 못 읽었다. 위키백과 문서에서 찾으려던 표어가
# 321~604자 자리에 있어서 매번 잘렸고, 여섯 명 전원이 못 찾았다. 쇼핑몰은
# 필요한 정보가 요소 이름(버튼·링크 글자)에 다 있어서 티가 안 났지만, 글이
# 본문인 사이트에서는 이 값이 곧 '읽을 수 있느냐'다.
#
# 700자면 한 화면 분량의 요지가 들어온다. 스텝당 입력이 약 25% 늘어난다.
PROMPT_TEXT_CHARS = 700
LOOP_THRESHOLD = 3       # 같은 URL이 이 횟수 이상이면 loop_detected
STEP_TIMEOUT_MS = 15000

# ── 브라우저 ──────────────────────────────────────────────────────
# 1280x800으로 고정한 이유 (2026-08-25 결정):
#  - 레이아웃이 .wrap{width:1180px} 고정이라 1280이든 1440이든 렌더 결과가 같다.
#    폭은 자유롭고, 1280이 여백이 덜 남아 설계 의도에 가깝다.
#  - 높이 800이 900보다 접힘선이 위여서 below_fold 마찰이 더 드러난다.
#    결함을 놓치는 쪽이 아니라 잡는 쪽으로 기울인다.
#  - 값이 두 군데 있으면 반드시 어긋나므로 여기가 유일한 출처다.
#    persona의 build_params()도 이 상수를 읽어야 한다.
#  ⚠ 데스크톱 전용이므로 375px에서만 드러나는 D-28/D-29/D-30 3건은
#    페르소나가 원리적으로 못 잡는다. 채점 시 상한으로 명시할 것.
VIEWPORT = {"width": 1280, "height": 800}
DEFAULT_PARALLEL = 5     # 크롬 1개당 100~200MB + API 분당 제한

# ── 답사(survey) ──────────────────────────────────────────────────
SURVEY_MAX_PAGES = 15        # 템플릿 정규화 후 기준
SURVEY_MAX_DEPTH = 3
SURVEY_SHOTS_PER_PAGE = 3    # 뷰포트 높이만큼 스크롤하며 최대 N장
SURVEY_VALIDATE_RETRIES = 3  # 판단 표현 검출 시 재생성 횟수
MAPS_DIR = "maps"

# ── 페르소나 생성(generate) ────────────────────────────────────────
# 목표는 10개가 아니라 11개다. 조합 16과 서로소(gcd=1)라 100명 전원이
# 서로 다른 (조합, 목표) 쌍을 받는다. 10개면 LCM이 80이라 뒤 20명이
# 앞 20명을 그대로 반복한다.
N_PERSONAS = 100
# 페르소나 배분의 난수 씨앗. 같은 씨앗이면 같은 100명이 나온다.
# 실행 간 비교를 하려면 사람이 같아야 한다.
PERSONA_SEED = 20260825
N_GOALS = 11
GOAL_TYPES = ("A", "B", "C")     # A=구매 완수 / B=정보 확인 후 이탈 / C=중단·재개
GOAL_MIX = {"A": 5, "B": 3, "C": 3}
# 페르소나 프롬프트 길이 상한. 배경 서사를 넣으면 바로 넘는다.
# 길어질수록 스텝마다 같은 토큰을 30번 다시 보낸다.
PROMPT_MAX_CHARS = 200
PERSONAS_DIR = "personas"

# 장바구니 localStorage 키는 변형마다 다르다.
# 페르소나 파일은 clean/buggy 양쪽에 동일하게 투입되므로(결정 6) 키를
# 페르소나에 박으면 한쪽은 조용히 빈 장바구니가 되고 유형 C가 무력화된다.
# seed_state 는 '무엇을 담아둔 상태인가'만 담고, 키는 러너가 여기서 읽는다.
CART_KEYS = {"clean": "moji_cart_clean", "buggy": "moji_cart_flawed",
             "flawed": "moji_cart_flawed"}


def cart_key(variant: str) -> str:
    if variant not in CART_KEYS:
        raise ValueError(f"알 수 없는 변형: {variant} (가능: {list(CART_KEYS)})")
    return CART_KEYS[variant]

# ── 대상 사이트 ────────────────────────────────────────────────────
# 스펙에서 부르는 'buggy'가 저장소의 flawed/ 폴더다.
# 포트 분리 없음: 정적 파일이라 서버 하나로 두 버전이 동시에 뜬다.
SITE_DIRS = {"clean": "clean", "buggy": "flawed", "flawed": "flawed"}
DEFAULT_BASE = "http://localhost:8000/ux-testbed"
# python -m http.server 를 띄운 디렉터리. 로컬 정적 사이트일 때
# 링크 추적이 못 간 페이지를 파일시스템에서 직접 찾는 데 쓴다.
DEFAULT_SERVE_ROOT = r"C:\Users\kamdo\AI_Testing"


def site_url(variant: str, base: str = DEFAULT_BASE) -> str:
    if variant not in SITE_DIRS:
        raise ValueError(f"알 수 없는 변형: {variant} (가능: {list(SITE_DIRS)})")
    return f"{base.rstrip('/')}/{SITE_DIRS[variant]}/index.html"


def site_root(variant: str, base: str = DEFAULT_BASE) -> str:
    if variant not in SITE_DIRS:
        raise ValueError(f"알 수 없는 변형: {variant} (가능: {list(SITE_DIRS)})")
    return f"{base.rstrip('/')}/{SITE_DIRS[variant]}"


def origin_of(url: str) -> str:
    """주소에서 출처(스킴+호스트)만. 페르소나가 남의 사이트로 새지 않게 막는 데 쓴다."""
    from urllib.parse import urlsplit
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}" if p.netloc else ""


def resolve_target(variant: str | None, url: str | None,
                   base: str = DEFAULT_BASE) -> dict:
    """무엇을 검사할지 하나로 정리한다.

    두 갈래가 있다.

    * **우리 테스트베드의 한 벌** (`--variant clean|buggy`) — 결과를 서로 견주려고
      만든 쌍이라 장바구니 씨앗을 심고 지도 파일도 이름이 정해져 있다.
    * **남의 주소 하나** (`--url https://…`) — 씨앗도 지도 이름도 없다. 대신
      **출처를 벗어나지 못하게** 묶는다. 페르소나가 광고나 외부 링크를 눌러
      다른 사이트로 가버리면 그 뒤 기록은 이 사이트에 대한 것이 아니게 된다.

    `scope` 는 같은 사이트로 볼 범위다. 주소에 경로가 있으면 그 경로 아래로
    좁힌다 — 큰 포털의 한 코너만 검사하고 싶을 때 나머지로 새지 않는다.
    """
    if url:
        clean = url.strip()
        if not clean:
            raise ValueError("주소가 비어 있습니다")
        if "://" not in clean:
            clean = "https://" + clean
        origin = origin_of(clean)
        if not origin:
            raise ValueError(f"주소를 알아볼 수 없습니다: {url}")
        root = clean.rsplit("/", 1)[0] if clean.count("/") > 2 else origin
        return {
            "kind": "url",
            # 호스트만 쓰면 같은 호스트의 서로 다른 페이지(예: 우리 테스트베드의
            # clean/flawed, 같은 사이트의 다른 코너)가 지도·스크린샷 캐시 파일명을
            # 공유해 서로 덮어써 버린다(2026-09-03 실측: ux-testbed의 clean과
            # flawed가 정확히 이 문제로 스크린샷을 나눠 가졌다). scope와 똑같이
            # root(경로 포함)로 키를 잡아야 서로 다른 페이지가 서로 다른 캐시를 쓴다.
            "name": root.split("//", 1)[-1],
            "start": clean,
            "root": root,
            "origin": origin,
            "scope": root,
            "cart_key": None,
            "map_name": None,
            "serve_root": None,
            # 남의 사이트가 무엇을 파는 곳인지 우리는 모른다. 커머스라고 알려주면
            # (--site-kind commerce) 그때만 검색 제한을 건다. SEARCH_RULE 참고.
            "site_kind": "general",
        }

    v = variant or "buggy"
    root = site_root(v, base)
    return {
        "kind": "variant",
        "name": v,
        "start": f"{root}/index.html",
        "root": root,
        "origin": origin_of(root),
        "scope": root,
        "cart_key": cart_key(v),
        "map_name": v,
        "serve_root": DEFAULT_SERVE_ROOT,
        "site_kind": "commerce",
    }


# ── 검색을 누구에게 허용할 것인가 ──────────────────────────────────
#
# 숙련도가 낮은 사람에게는 검색을 막아둔다. 다만 그 근거는 **쇼핑몰 전용**이다:
# 검색창에 상품명을 그대로 치는 것은 길을 찾은 것이 아니라 길찾기를 건너뛴
# 것이라, 그러면 메뉴·분류·목록에서 겪었을 마찰이 통째로 측정에서 사라진다.
#
# 위키·문서·포털에서는 사정이 정반대다. 검색이 **정상적인 첫 번째 길**이고,
# 미션 자체가 "검색해서 …"인 경우도 있다. 거기서 검색을 막으면 숙련도 1~2인
# 사람(전체의 40%)은 미션을 구조적으로 수행할 수 없게 된다 — 실제로 나무위키
# 에서 P002 가 검색창에 세 번 입력을 시도하다 전부 차단당하고 끝났다.
#
# 그래서 **커머스에만** 제한을 건다.
SEARCH_RULE = {"commerce": "숙련도에 따라 제한", "general": "전원 허용"}


def search_allowed_for(person: dict, site_kind: str) -> bool:
    """이 사람에게 이 사이트에서 검색을 허용할지."""
    if site_kind != "commerce":
        return True
    return bool(person.get("search_allowed", True))


#: map_stem()이 만드는 파일명 길이 상한. server/app/orchestrate.py의 _map_stem()·
#: web/src/lib/mapStem.ts의 mapStem()과 반드시 같은 값이어야 한다 — 셋 중 하나만
#: 다르게 자르면 셋이 서로 다른 캐시 파일을 가리키게 된다.
MAP_STEM_MAX_LEN = 150


def map_stem(target: dict) -> str:
    """지도·기록 파일에 쓸 짧은 이름. 주소를 파일명으로 쓸 수 없어 안전한 문자만 남긴다.

    호스트만 쓰던 시절엔 같은 사이트의 서로 다른 페이지(우리 테스트베드의
    clean/flawed 등)가 캐시를 공유해 서로 덮어썼다 — 그래서 target["name"]에
    경로(root)까지 담겨 온다(resolve_target() 참고). 여기서는 그걸 파일명으로
    쓸 수 있는 문자로만 바꿀 뿐이다.
    """
    if target.get("map_name"):
        return target["map_name"]
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in target["name"])
    return (safe.strip("_") or "site")[:MAP_STEM_MAX_LEN]


#: 이 접미사로 끝나는 호스트는 서브도메인 하나하나가 완전히 남의 사이트다
#: (우리 테스트베드 자체가 그중 하나인 lsb1022.github.io다) — _registrable_domain()이
#: 이런 호스트를 등록 도메인 단위로 넓히면 안 된다. 완전한 공개접미사목록(PSL)이
#: 아니라 이 프로젝트가 실제로 마주치는 흔한 것들만 담은 근사치다.
_MULTI_TENANT_SUFFIXES = {
    "github.io", "vercel.app", "netlify.app", "pages.dev", "web.app",
    "firebaseapp.com", "herokuapp.com", "workers.dev", "glitch.me", "repl.co",
    "blogspot.com", "tistory.com", "wordpress.com", "s3.amazonaws.com",
}
#: .kr/.jp 등 "2단짜리 TLD"처럼 보이지만 실제 등록 단위는 3단인 경우
#: (example.co.kr — "co.kr"이 아니라 "example.co.kr"이 한 사이트).
_TWO_PART_TLDS = {"kr", "jp", "uk", "au", "nz", "br", "cn", "in", "za"}
_TWO_PART_SECOND_LEVEL = {"co", "or", "go", "ac", "ne", "pe", "re"}


def _registrable_domain(host: str) -> str:
    """등록 도메인 근사치. 완전한 PSL이 아니다 — 한국 사이트(.co.kr 등)와
    이 프로젝트가 실제로 만나는 멀티테넌트 호스팅만 다룬다."""
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    last_two = ".".join(labels[-2:])
    last_three = ".".join(labels[-3:])
    if last_two in _MULTI_TENANT_SUFFIXES or last_three in _MULTI_TENANT_SUFFIXES:
        return host  # 이미 최대로 구체적인 "사이트"다 — 더 넓히지 않는다.
    if labels[-1] in _TWO_PART_TLDS and labels[-2] in _TWO_PART_SECOND_LEVEL:
        return last_three
    return last_two


def in_scope(url: str, target: dict) -> bool:
    """이 주소가 검사 범위 안인가. 벗어나면 페르소나를 되돌린다.

    범위는 **사용자가 준 주소의 경로 아래**다. 같은 호스트 전체가 아니다 —
    쇼핑 코너를 검사하라고 줬는데 회사 소개나 블로그를 헤매면 그 기록은
    검사 대상에 대한 것이 아니다. 로고를 눌러 첫 화면으로 가는 것만
    예외로 열어둔다. 사람도 길을 잃으면 로고부터 누른다.

    다만 호스트가 완전히 같아야만 통과시키면, 검색만 다른 서브도메인에서
    답하는 사이트(예: 네이버 www.naver.com → search.naver.com)에서는 검색
    자체가 막힌다(2026-09-04 실측: "일반(위키·포털)" 사이트에 검색이 정상
    행동인 미션인데도 전원이 "검사 범위 밖"으로 튕겨 포기함 — SEARCH_RULE이
    이미 이런 사이트는 검색을 열어두는데, in_scope가 그 결과 화면 자체를
    막고 있었다). 등록 도메인이 같으면 서브도메인이 달라도 통과시킨다 —
    단, github.io 같은 멀티테넌트 호스팅은 예외(_registrable_domain 참고).
    """
    if not url:
        return False
    scope = (target.get("scope") or "").rstrip("/")
    if scope and (url == scope or url.startswith(scope + "/")
                  or url.startswith(scope + "?")):
        return True
    origin = target.get("origin") or ""
    if origin and url.rstrip("/") == origin.rstrip("/"):
        return True

    from urllib.parse import urlsplit
    site_host = urlsplit(origin).netloc if origin else ""
    url_host = urlsplit(url).netloc
    return bool(site_host and url_host
                and _registrable_domain(site_host) == _registrable_domain(url_host))
