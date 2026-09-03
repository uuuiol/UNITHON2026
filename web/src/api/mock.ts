/**
 * 백엔드 없이 도는 데모용 응답.
 *
 * 이 MVP 의 목적은 "이런 식으로 작동합니다"를 보여주는 것이라, 서버·DB 없이
 * 프론트 하나로 완결되게 만든다. 그래야 시연 중에 죽지 않고 정적 호스팅에도 올라간다.
 *
 * **숫자는 지어내지 않는다.** `mock-data.ts` 는 실제 파이프라인 실행 기록에서
 * 뽑아 넣은 값이고(agent-ux/export_web_mock.py), 여기서는 그것을 화면이 기대하는
 * 모양으로 옮기기만 한다. 실행을 다시 하면 내보내기만 다시 돌리면 된다.
 *
 * **주소 하나에 분석 하나.** 사이트 두 벌(clean/flawed)은 우리 실험용 사정이지
 * 사용자의 사정이 아니다. 사용자는 주소 하나를 넣었으므로 프로젝트 안에서는
 * 그 주소의 결과만 보여준다. 두 사이트를 견주는 일은 별도의 비교 화면에서만 한다.
 *
 * 끄려면 web/.env 에 VITE_MOCK=0 을 넣고 진짜 백엔드를 띄운다.
 */
import { MOCK_DATA } from './mock-data'

/**
 * 실행만 진짜 파이프라인에 맡길지.
 *
 * 배포본에는 돌릴 파이프라인이 없어서, 실행 요청에 "이미 끝난 실행"이라고 답하고
 * 미리 돌려 둔 결과로 보낸다. 그게 시연 중에 죽지 않는 유일한 방법이다.
 *
 * 그런데 로컬에서 `python server.py` 를 띄워놓고 진짜로 돌려 보고 싶을 때도 그
 * 지름길로 새서, 진행 화면이 아예 안 뜨고 곧장 결과로 튀었다. 그때만 이 스위치를
 * 켠다 — 나머지 화면(프로젝트·결과·재생)은 그대로 목업이 답하므로 데모는 살아 있다.
 *
 *     web/.env.local:  VITE_LIVE_RUN=1
 */
const LIVE_RUN = import.meta.env.VITE_LIVE_RUN === '1' 

type Json = Record<string, unknown>

/**
 * 데모에 들어 있는 사이트 두 벌.
 *
 * 같은 쇼핑몰의 **고치기 전과 고친 뒤**로 세운다 — 비교 화면이 하려는 일이
 * 바로 그것이고, '결함판/정상판'은 우리 실험실 말이라 밖에서는 안 통한다.
 * `variant` 는 mock-data 안에서 어느 실행 기록을 꺼낼지 고르는 열쇠다.
 */
/**
 * 테스트베드가 배포된 곳. 예전에는 `http://localhost:8000` 을 가리켰는데,
 * 배포본에는 그 서버가 없어서 썸네일도 미리보기도 열리지 않았다.
 */
const TESTBED = 'https://lsb1022.github.io/UNITHON2026-MOJI/ux-testbed/'

const SITES = [
  {
    id: 'moji-before',
    testId: 'moji-before-test',
    variant: 'buggy',
    name: 'MOJI STORE (개선 전)',
    url: `${TESTBED}flawed/index.html`,
  },
  {
    id: 'moji-after',
    testId: 'moji-after-test',
    variant: 'clean',
    name: 'MOJI STORE (개선 후)',
    url: `${TESTBED}clean/index.html`,
  },
  // 우리 테스트베드가 아닌 **진짜 공개 사이트**. 이 도구가 남의 사이트에도
  // 붙는다는 증거라 데모에 넣어 둔다. 기록은 실제로 위키백과에서 여섯 명을
  // 돌린 것이다 (agent-ux/logs/wiki_all).
  {
    id: 'wikipedia',
    testId: 'wikipedia-test',
    variant: 'wiki',
    name: '위키백과 (공개 사이트)',
    url: 'https://ko.wikipedia.org/',
  },
] as const

type Site = {
  id: string
  testId: string
  variant: string
  name: string
  url: string
}

/** 사이트마다 실제로 준 미션. 실행 기록에 남은 목표 그대로다. */
const MISSION: Record<string, { name: string; goal: string; criteria: string }> = {
  buggy: {
    name: '코튼 셔츠 주문 완주',
    goal: '코튼 셔츠를 장바구니에 담아 주문까지 마친다',
    criteria: '주문 완료 화면에 도달하면 성공',
  },
  clean: {
    name: '코튼 셔츠 주문 완주',
    goal: '코튼 셔츠를 장바구니에 담아 주문까지 마친다',
    criteria: '주문 완료 화면에 도달하면 성공',
  },
  wiki: {
    name: '숭실대학교 표어 확인',
    goal: '숭실대학교를 검색해서 숭실대학교의 표어가 무엇인지 파악한다',
    // 본인이 "찾았다"고 말하는 것만으로는 달성으로 세지 않는다. 이 글자가 그
    // 사람 화면에 실제로 떴는지 코드가 대조한다 — 모델이 자기 지식으로 답을
    // 메우면 '근거 없음'으로 남는다.
    criteria: '화면에 "역사로 미래를 여는 대학"이 실제로 보였을 때만 달성으로 셉니다',
  },
}

const missionOf = (variant: string) => MISSION[variant] ?? MISSION.buggy

/** 주소가 어느 실행 기록에 해당하는지. 데모에 담긴 기록은 두 벌뿐이다. */
function variantOf(url: string): string {
  return url.includes('/clean/') ? 'clean' : 'buggy'
}

/**
 * 데모에 들어 있는 두 벌 + 사용자가 이 자리에서 만든 프로젝트.
 *
 * 사용자가 만든 것은 **따로 쌓는다**. 예전에는 주소가 겹치면 데모 프로젝트의
 * 이름을 갈아 끼웠는데, 새 프로젝트를 하나 만들었더니 원래 있던
 * 'MOJI STORE (개선 전)' 의 이름이 통째로 바뀌어 버렸다. 사용자가 만든 것이
 * 원래 있던 것을 건드리면 안 된다.
 */
function allSites(): Site[] {
  return [...(SITES as readonly Site[]), ...state.created]
}

/** 미리 돌려 둔 기록이 있는 사이트인가. 사용자가 방금 만든 프로젝트에는 없다. */
const hasRecord = (site: Site) => (SITES as readonly Site[]).some((x) => x.id === site.id)

const siteById = (id: string) => allSites().find((s) => s.id === id)
const siteByTest = (id: string) => allSites().find((s) => s.testId === id)

/**
 * 만든 프로젝트를 이 브라우저에 남긴다.
 *
 * 서버가 없으니 메모리에만 두면 새로고침 한 번에 방금 만든 프로젝트가 사라진다 —
 * 만들자마자 없어지는 건 데모라기보다 고장으로 보인다. 이 브라우저에만 남고
 * 다른 사람에게는 안 간다.
 *
 * 저장이 막힌 환경(사생활 보호 창, 사이트 데이터 차단)에서는 조용히 메모리만
 * 쓴다. 저장이 안 된다고 화면이 죽으면 안 된다.
 */
const STORE_KEY = 'moji.demo.projects'

function loadCreated(): Site[] {
  try {
    const raw = localStorage.getItem(STORE_KEY)
    const list = raw ? (JSON.parse(raw) as Site[]) : []
    return Array.isArray(list) ? list.filter((s) => s && s.id && s.url) : []
  } catch {
    return []
  }
}

function saveCreated(list: Site[]): void {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(list))
  } catch {
    // 저장 못 해도 이번 세션에서는 동작한다.
  }
}

/** 마법사가 앞뒤로 오가도 값이 남아 있어야 한다. 새로고침하면 초기화된다. */
const state = {
  missionPrompt: MOCK_DATA.goal as string,
  successCriteria: '화면에 아래 문구가 실제로 보였을 때만 달성으로 셉니다',
  expect: '',
  personaTotal: 10,
  /**
   * 이 자리에서 만든 프로젝트. 새로고침하면 사라진다 — 데모라 서버가 없다.
   * 결과는 주소에 맞는 실행 기록을 빌려 보여준다. 없는 숫자를 지어내는 것이
   * 아니라, 그 주소가 우리가 실제로 돌려본 두 사이트 중 하나이기 때문이다.
   */
  created: loadCreated(),
  targetUrl: SITES[0].url as string,
  /** 마법사에서 사용자가 붙인 테스트 이름. 없으면 사이트의 기본 미션 이름을 쓴다. */
  testName: '',
}

const nameOf = (site: Site) => site.name

const runs = MOCK_DATA.runs as Record<
  string,
  {
    runId: string
    variant: string
    usage: { calls?: number; tokens_in?: number; tokens_out?: number; cost_usd?: number }
    personas: {
      id: string
      label: string
      steps: number
      end: string
      endLabel: string
      firstThought: string
      lastThought: string
    }[]
  }
>

function rate(variant: string): number | null {
  const run = runs[variant]
  if (!run || run.personas.length === 0) return null
  const ok = run.personas.filter((p) => p.end === 'goal_reached').length
  return Math.round((ok / run.personas.length) * 1000) / 10
}

function dropRate(variant: string): number | null {
  const r = rate(variant)
  return r === null ? null : Math.round((100 - r) * 10) / 10
}

const cleanMap = MOCK_DATA.maps.clean as { pages: { path: string; title: string }[] }

/**
 * 입력창 앞의 "https://" 는 화면 장식일 뿐이라 값에 포함되지 않는다.
 * 그래서 사용자가 무엇을 치든(프로토콜 있든 없든) 열리는 주소로 맞춰준다.
 * localhost 는 http 다 — https 를 붙이면 연결이 안 된다.
 */
function normalizeUrl(raw: string): string {
  const t = raw.trim()
  if (!t) return ''
  if (/^https?:\/\//i.test(t)) return t
  const isLocal = /^(localhost|127\.0\.0\.1)(:|\/|$)/i.test(t)
  return (isLocal ? 'http://' : 'https://') + t
}

function projectCard(site: Site): Json {
  return {
    id: site.id,
    name: nameOf(site),
    category: '커머스',
    test_count: hasRecord(site) ? 1 : 0,
    last_activity_at: MOCK_DATA.generatedAt,
    preview_url: site.url,
    preview_embeddable: true,
    removable: !hasRecord(site),
  }
}

const measured = MOCK_DATA.measured as {
  calls: number
  tokensIn: number
  tokensOut: number
  usd: number
  usdPerPersona: number
}

const byVariant = MOCK_DATA.viewsByVariant as Record<
  string,
  {
    detail: Json
    paths: Json
    diagram: Json
    personas: Json
    steps: Json
    filmstrip: unknown[]
    replay: Json
  }
>

/**
 * 흉내 내지 않는 경로를 나타내는 표식.
 * `null` 을 그 뜻으로 쓰면 "실행 중인 것이 없다(null)"는 **정상 응답**과 구별되지 않아,
 * 그 응답이 진짜 서버로 새어 나간다 (실제로 /api/runs/active 가 그렇게 샜다).
 */
export const MOCK_MISS = Symbol('mock-miss')


/**
 * 주소가 진짜 열리는지 **실제로 확인한다.**
 *
 * 예전에는 무엇을 넣든 "연결할 수 있어요 / HTTP 200 / 미리보기 가능"이라고
 * 답했다. 있지도 않은 `ㅗㅗㅗ.com` 도 통과했다. 확인해준다고 해놓고 확인하지
 * 않는 것은 없는 기능보다 나쁘다 — 사용자가 그 말을 믿고 다음 단계로 간다.
 *
 * 브라우저에서 남의 주소의 **상태 코드**까지는 알 수 없다(CORS). 하지만
 * `no-cors` 로 던져보면 **닿는지 안 닿는지**는 알 수 있다: 없는 도메인이나
 * 죽은 서버는 예외를 던지고, 살아 있으면 내용은 못 읽어도 성공으로 돌아온다.
 * 알 수 있는 것만 말하고 나머지는 모른다고 말한다.
 */
// 느린 사이트는 이 정도까지 걸린다 (실측: news.ycombinator.com 24~60초).
// 8초로 두었을 때는 살아 있는 사이트가 '닿지 못했어요' 로 떨어졌다.
const PROBE_MS = 15000

async function checkUrl(url: string) {
  if (!url) {
    return {
      ok: false, url, final_url: null, status: null, title: null,
      embeddable: false, embed_block_reason: null, link_count: null,
      error_kind: 'empty', message: '주소를 입력해 주세요.',
    }
  }

  let host = ''
  try {
    host = new URL(url).hostname
  } catch {
    return {
      ok: false, url, final_url: null, status: null, title: null,
      embeddable: false, embed_block_reason: null, link_count: null,
      error_kind: 'malformed', message: '주소 형식이 올바르지 않아요.',
    }
  }
  if (!host.includes('.') && host !== 'localhost') {
    return {
      ok: false, url, final_url: null, status: null, title: null,
      embeddable: false, embed_block_reason: null, link_count: null,
      error_kind: 'malformed',
      message: `"${host}" 는 주소로 보이지 않아요. 예) www.example.com`,
    }
  }

  // 주소 제한은 두지 않는다.
  //
  // 예전에는 미리 돌려 둔 두 곳으로 좁혀 두었다. 아무 주소나 받으면 화면이
  // 남의 실행 기록을 그 주소의 결과인 것처럼 보여줬기 때문이다. 지금은 그쪽을
  // 고쳤다 — 직접 만든 프로젝트에는 기록이 없다고 정직하게 말한다(hasRecord).
  // 그래서 새 사이트를 넣어 보는 것을 막을 이유가 없어졌다.

  // '화면 N종을 찾았습니다' 는 **우리 테스트베드**를 답사한 결과다(cleanMap).
  // 예전에는 데모 사이트 아무거나에 이 수를 붙였는데, 그러면 위키백과를 넣어도
  // 쇼핑몰의 화면 수를 찾았다고 말하게 된다. 아는 것만 말한다.
  const known = url.startsWith(TESTBED)
  const started = Date.now()
  // catch 에서도 봐야 한다 — try 안에 두면 시간 초과인지 알 수 없다.
  let timedOut = false
  try {
    const ctl = new AbortController()
    const timer = setTimeout(() => {
      timedOut = true
      ctl.abort()
    }, PROBE_MS)
    // no-cors 라 내용을 못 읽는다. 우리가 얻는 것은 '닿았다'는 사실 하나뿐이다.
    await fetch(url, { mode: 'no-cors', signal: ctl.signal, cache: 'no-store' })
    clearTimeout(timer)
  } catch {
    // **시간이 모자란 것과 주소가 틀린 것은 다르다.** 둘을 같은 말로 뭉치면
    // 살아 있는데 느린 사이트를 '없는 주소' 라고 말하게 된다.
    return {
      ok: false, url, final_url: null, status: null, title: null,
      embeddable: false, embed_block_reason: null, link_count: null,
      error_kind: timedOut ? 'timeout' : 'unreachable',
      message: timedOut
        ? `${host} 가 ${PROBE_MS / 1000}초 안에 응답하지 않았어요. 느린 것뿐일 수 있어요 — 주소가 맞다면 그대로 진행해도 됩니다.`
        : `${host} 에 닿지 못했어요. 주소가 맞는지, 사이트가 열려 있는지 확인해 주세요.`,
      /** 확인은 못 했지만 사용자가 주소를 안다면 넘어갈 수 있다. */
      proceed_anyway: Boolean(timedOut),
    }
  }

  return {
    ok: true,
    url,
    final_url: url,
    // 상태 코드는 브라우저에서 읽을 수 없다. 200 이라고 적으면 거짓말이 된다.
    status: null,
    title: known ? 'MOJI STORE' : null,
    // 미리보기(iframe) 가 되는지는 브라우저에서 알 수 없다 — 프레임을 막는
    // 헤더(X-Frame-Options / CSP frame-ancestors)를 no-cors 응답에서 읽을 수
    // 없기 때문이다. 그래서 일단 띄워 보고, 빈 화면이면 찍어 둔 사진으로
    // 떨어진다. 확인한 사실이 아니라 '해보겠다' 는 뜻이다.
    embeddable: true,
    embed_block_reason: null,
    // 링크 수는 답사를 돌려야 나온다. 아는 사이트만 말한다.
    link_count: known ? cleanMap.pages.length : null,
    error_kind: null,
    elapsed_ms: Date.now() - started,
    message: known
      ? `연결됐습니다. 화면 ${cleanMap.pages.length}종을 찾았습니다.`
      : `${host} 에 닿았습니다. 화면이 몇 종인지는 답사를 돌려야 알 수 있어요.`,
  }
}

// --------------------------------------------------------------------------- //
// 계정 · 플랜 · 크레딧
//
// 서버에 이 표들이 아직 없다(결제도 붙지 않았다). 숫자를 지어내지 않는다는 원칙은
// **실행 결과**에 대한 것이고, 여기 값은 결과가 아니라 **디자인이 정한 상품 정보**다.
// 그래서 Figma(311:21271 · 336:28072 · 311:21384 · 311:21197)에 적힌 값을 그대로 옮긴다.
//
// /account는 결제와 무관하게 이미 진짜라 먼저 뗐다(위 mockResponse의
// '/api/account' 분기 참고). 진짜 결제가 붙으면 아래 세 경로도 MOCK_MISS로
// 바꾸면 된다.
// --------------------------------------------------------------------------- //

const PLAN = {
  current: {
    name: '스탠다드',
    price_label: '월 ₩14,900',
    next_billing_at: '2026. 09. 26',
    used: 12,
    quota: 30,
  },
  features: [
    'AI 페르소나 최대 30명',
    'Navigation Flow · Replay',
    '감정 및 내면 독백 분석',
    '팀원 3명',
    'CSV/PDF 리포트 내보내기',
  ],
  upgrade: {
    badge: 'PRO',
    title: '더 많은 테스트가 필요하신가요?',
    body: '월 120회 테스트와 최대 100명의 AI 페르소나로 더 큰 규모의 검증을 진행할 수 있어요.',
    cta: '프로 플랜 살펴보기',
    note: '다음 결제 전까지 언제든 변경 가능',
  },
}

const CREDITS = {
  balance: 180,
  used_this_month: 42,
  rules: [
    { label: '기본 테스트 실행', value: '1 credit / persona', highlight: false },
    { label: 'Replay + 행동 로그', value: '포함', highlight: true },
    { label: '고급 감정 분석', value: '+1 credit / persona', highlight: false },
  ],
  packs: [
    { credits: 50, price: '₩11,000', featured: false },
    { credits: 100, price: '₩19,800', featured: true },
    { credits: 300, price: '₩42,800', featured: false },
  ],
  history: [
    { at: '오늘 01:14', label: '결제 화면 테스트', delta: -18 },
    { at: '08.25 22:03', label: '검색 UX 테스트', delta: -12 },
    { at: '08.24 19:40', label: '크레딧 충전', delta: 100 },
  ],
}

const PLAN_TIERS = [
  // 표에 있는 것만 적는다. 요금제 화면의 목록은 약속으로 읽히고,
  // 없는 기능을 채워 두면 눌러본 사람이 바로 알아챈다.
  {
    id: 'free',
    name: '무료',
    tagline: '작게 시작하고 기능을 확인해보세요.',
    price: '₩0',
    cta: '무료로 시작하기',
    badge: null,
    credits: 3,
    features: ['3크레딧'],
    limits: ['로그 확인 불가'],
    featured: false,
  },
  {
    id: 'standard',
    name: '스탠다드',
    tagline: '팀의 반복 UX 테스트를 자동화해요.',
    price: '₩14,900',
    cta: '스탠다드 시작하기',
    badge: '가장 많이 선택해요',
    credits: 100,
    features: ['100크레딧', 'A/B 테스트 기능 오픈'],
    limits: [],
    featured: true,
  },
  {
    id: 'pro',
    name: '프로',
    tagline: '고인도 테스트와 상세 분석이 필요한 팀.',
    price: '₩39,900',
    cta: '프로 시작하기',
    badge: null,
    credits: 300,
    features: ['300크레딧', '감정내면 독백 분석'],
    limits: [],
    featured: false,
  },
]

/** 추가로 살 수 있는 크레딧. */
const CREDIT_PACKS = [
  { credits: 50, price: '11,000원' },
  { credits: 100, price: '19,800원' },
  { credits: 300, price: '42,800원' },
]

// --------------------------------------------------------------------------- //
// A/B 테스트
//
// 두 프로젝트를 같은 페르소나로 견준 결과다. 표와 다이어그램은 지어내지 않는다 —
// 이미 돌려 둔 실행 기록(viewsByVariant)에서 A 쪽과 B 쪽을 각각 꺼내 온다.
// 비교 자체(어느 둘을 견줄지)만 이 브라우저에 남는다.
// --------------------------------------------------------------------------- //

type AbRow = { id: string; name: string; a: string; b: string; createdAt: string }

const AB_STORE_KEY = 'moji.demo.ab'

/** 씨앗 한 건 — 우리가 실제로 돌린 '개선 전 / 개선 후' 두 실행. */
const AB_SEED: AbRow = {
  id: 'ab-moji',
  name: '쇼핑몰 결제 UX 비교',
  a: 'moji-before',
  b: 'moji-after',
  createdAt: MOCK_DATA.generatedAt as string,
}

function loadAb(): AbRow[] {
  try {
    const raw = localStorage.getItem(AB_STORE_KEY)
    const list = raw ? (JSON.parse(raw) as AbRow[]) : []
    return Array.isArray(list) ? list.filter((r) => r && r.id && r.a && r.b) : []
  } catch {
    return []
  }
}

function saveAb(list: AbRow[]): void {
  try {
    localStorage.setItem(AB_STORE_KEY, JSON.stringify(list))
  } catch {
    // 저장 못 해도 이번 세션에서는 동작한다.
  }
}

const abState = { rows: [AB_SEED, ...loadAb()] }

/**
 * 그 사람이 밟은 화면을 단계 순서로 편다.
 *
 * 페르소나별 경로를 따로 내보내지는 않았지만, 화면마다 남은 클릭 기록에 누가
 * 눌렀는지가 붙어 있다. 그것을 모으면 경로가 나온다 — 지어내는 것이 아니라
 * 이미 있는 기록을 다시 세는 것이다.
 *
 * 마지막에 도착만 하고 아무것도 누르지 않은 화면은 여기 안 잡힌다.
 */
function pathOf(variant: string, personaCode: string): string[] {
  const steps = byVariant[variant]?.steps as
    | Record<string, { step: number; title: string; clicks?: { persona?: string }[] }>
    | undefined
  if (!steps) return []
  return Object.values(steps)
    .filter((s) => (s.clicks ?? []).some((c) => c.persona === personaCode))
    .sort((a, b) => a.step - b.step)
    .map((s) => s.title)
}

/** 목록 카드 한 장. 양쪽 프로젝트가 아직 있는 것만 추린다. */
function abCard(row: AbRow): Json | null {
  const a = siteById(row.a)
  const b = siteById(row.b)
  if (!a || !b) return null
  return {
    id: row.id,
    name: row.name,
    mission: missionOf(a.variant).goal,
    created_at: row.createdAt,
    a: { id: a.id, name: nameOf(a), preview_url: a.url },
    b: { id: b.id, name: nameOf(b), preview_url: b.url },
  }
}

/**
 * 미션 문장 검토 — **규칙으로 확인할 수 있는 것만.**
 *
 * 예전에는 무엇을 넣든 "주문 완료 화면에 도달하면 성공"을 돌려주고 '자동으로
 * 감지해요' 라고 적었다. 감지하는 코드는 없었다. 확인해준다고 해놓고 확인하지
 * 않는 것은 없는 기능보다 나쁘다 — 사용자가 그 말을 믿고 다음 단계로 간다.
 *
 * 브라우저 안에서는 모델을 부를 수 없다(키가 번들에 실린다). 그래서 낱말로
 * 확실히 걸리는 것만 걸러내고, **성공 기준은 사용자가 정한다.** 그 문구가 그
 * 사람 화면에 실제로 떴을 때만 달성으로 센다(run.py 의 --expect 와 같은 값이다).
 */
function analyzeMissionText(promptText: string) {
  const text = promptText.trim()
  const issues: { kind: string; message: string; fix: string }[] = []

  // ① 결함을 미리 알려주는 표현. 이게 들어가면 전원이 그것을 찾으러 가고,
  //    적중률이 '우리가 알려준 답을 세는 값'이 된다.
  const banned = ['작동하지', '안 됨', '안됨', '문제', '오류', '불편', '이상하',
                  '헷갈', '어렵', '느리', '복잡', '개선']
  for (const w of banned) {
    if (text.includes(w)) {
      issues.push({
        kind: 'judgement',
        message: `"${w}" 는 결함을 미리 알려주는 표현이에요.`,
        fix: '무엇을 하려는지만 적어주세요. 예) 코튼 셔츠를 장바구니에 담아 주문까지 마친다',
      })
      break
    }
  }

  // ② 너무 막연하면 끝났는지 판정할 수 없다.
  const vague = ['둘러본다', '살펴본다', '구경', '탐색한다', '이것저것']
  if (vague.some((w) => text.includes(w)) || (text.length > 0 && text.length < 8)) {
    issues.push({
      kind: 'vague',
      message: '무엇을 하면 끝인지 알 수 없어요.',
      fix: '도착점이 있는 일 하나로 적어주세요. 예) 배송비 정책을 확인한다',
    })
  }

  // ③ 할 일이 여러 개면 어디서 실패했는지 갈리지 않는다.
  if (/그리고|,\s*그다음|한 뒤에|한 다음/.test(text)) {
    issues.push({
      kind: 'multi',
      message: '할 일이 여러 개로 보여요.',
      fix: '한 번에 하나씩 나눠서 돌려주세요.',
    })
  }

  // ④ 길이. 스텝마다 다시 보내는 문장이라 길면 값이 비싸다.
  if (text.length > 60) {
    issues.push({
      kind: 'length',
      message: `${text.length}자예요. 60자 이내로 줄여주세요.`,
      fix: '페르소나마다 스텝마다 다시 보내는 문장이라 길수록 비용이 늘어요.',
    })
  }

  if (!text) {
    return { status: 'idle', success_criteria: null, expect: '', issues: [],
             generated_by: 'rule' }
  }
  if (issues.length) {
    return { status: 'invalid', success_criteria: null, expect: '', issues,
             generated_by: 'rule' }
  }
  return {
    status: 'warning',
    // 규칙이 통과했다고 '검증됐다'가 아니다. 남은 한 가지를 사용자에게 묻는다.
    success_criteria: '화면에 아래 문구가 실제로 보였을 때만 달성으로 셉니다',
    expect: '',
    issues: [{
      kind: 'need_evidence',
      message: '달성을 인정할 근거 문구를 정해주세요.',
      fix: '그 글자가 화면에 뜬 적이 없으면 달성으로 세지 않아요. ' +
           '비워두면 페르소나가 스스로 "다 했다"고 말하는 것만으로 달성이 됩니다.',
    }],
    generated_by: 'rule',
  }
}

/** 경로별 응답. 흉내 낼 수 없으면 MOCK_MISS 를 돌려 호출부가 진짜 서버로 넘기게 한다. */
export function mockResponse(rawPath: string, init?: RequestInit): unknown {
  const method = (init?.method ?? 'GET').toUpperCase()
  const body = init?.body ? (JSON.parse(String(init.body)) as Json) : null
  const [path, query = ''] = rawPath.split('?')
  const params = new URLSearchParams(query)

  if (path === '/api/connectivity/check') {
    const url = normalizeUrl(String(body?.url ?? ''))
    if (url) state.targetUrl = url
    return checkUrl(url)
  }

  if (path === '/api/missions/analyze') return analyzeMissionText(String(body?.prompt ?? ''))

  // ── 프로젝트 ──────────────────────────────────────────────────
  if (path === '/api/projects' && method === 'GET') return allSites().map(projectCard)

  // 이 자리에서 만든 프로젝트 지우기. 목록이 지저분해지면 치울 수 있어야 한다.
  // 데모에 딸려 오는 세 개는 기록이 코드에 들어 있어서 지울 대상이 아니다 —
  // 지운 척하고 다음 새로고침에 되살아나면 그게 더 나쁘다.
  if (path.startsWith('/api/projects/') && method === 'DELETE') {
    const id = path.split('/')[3] ?? ''
    if (!state.created.some((s) => s.id === id)) {
      return { ok: false, message: '데모에 들어 있는 프로젝트는 지울 수 없어요.' }
    }
    state.created = state.created.filter((s) => s.id !== id)
    saveCreated(state.created)
    return { ok: true }
  }
  if (path === '/api/projects' && method === 'POST') {
    // **새 항목으로 쌓는다.** 원래 있던 데모 프로젝트는 건드리지 않는다.
    const url = normalizeUrl(String(body?.target_url ?? state.targetUrl))
    state.targetUrl = url
    // 지운 뒤 다시 만들어도 id 가 겹치지 않도록 지금 있는 것 중 가장 큰 번호 다음을 쓴다.
    const used = state.created
      .map((s) => Number(s.id.replace('made-', '')))
      .filter((n) => Number.isFinite(n))
    const n = (used.length ? Math.max(...used) : 0) + 1
    const site: Site = {
      id: `made-${n}`,
      testId: `made-${n}-test`,
      variant: variantOf(url),
      name: String(body?.name || `새 프로젝트 ${n}`),
      url,
    }
    state.created.push(site)
    saveCreated(state.created)
    return projectCard(site)
  }

  const project = allSites().find((s) => path === `/api/projects/${s.id}`)
  if (project) {
    return {
      ...projectCard(project),
      device_preset: 'desktop',
      viewport: { w: 1280, h: 800 },
      // 돌린 적이 없으면 성공률도 없다. 0% 로 적으면 '전원 실패'로 읽힌다.
      success_rate: hasRecord(project) ? rate(project.variant) : null,
      drop_rate: hasRecord(project) ? dropRate(project.variant) : null,
    }
  }

  const listing = allSites().find((s) => path === `/api/projects/${s.id}/tests`)
  if (listing) {
    if (method === 'POST') {
      // 사용자가 붙인 이름을 버리면 진행 화면과 검토 화면이 엉뚱한 미션 이름을
      // 띄운다 — "위치 찾기"로 만들었는데 "표어 확인"이 뜨는 식이다.
      if (body?.name) state.testName = String(body.name)
      return { id: listing.testId }
    }
    // **방금 만든 프로젝트에는 기록이 없다.**
    // 예전에는 주소가 같은 데모 사이트의 결과를 그대로 빌려줘서, 아무것도 안
    // 돌린 프로젝트에 "코튼 셔츠 주문 완주 · 성공률 70%" 가 떴다. 남의 결과를
    // 내 것처럼 보여주는 것은 이 도구가 하지 말아야 할 일 그 자체다.
    if (!hasRecord(listing)) return []
    return [
      {
        test_id: listing.testId,
        name: missionOf(listing.variant).name,
        created_at: MOCK_DATA.generatedAt,
        persona_count: runs[listing.variant]?.personas.length ?? 0,
        success_rate: rate(listing.variant),
        drop_rate: dropRate(listing.variant),
      },
    ]
  }

  // ── 결과 화면 ────────────────────────────────────────────────
  // 숫자는 전부 실제 실행 기록에서 뽑은 것이다 (agent-ux/export_web_mock.py).
  // 프로젝트 하나는 사이트 하나다 — 어느 쪽을 볼지 고르는 스위치는 없다.
  const site = siteByTest(path.split('/')[3] ?? '')
  if (site) {
    const base = `/api/tests/${site.testId}`
    const views = byVariant[site.variant]

    // 마법사가 저장하는 것들. 데모라 받아만 두고 흘려보낸다.
    if (path === `${base}/mission`) {
      state.missionPrompt = String(body?.prompt ?? state.missionPrompt)
      state.successCriteria = String(body?.success_criteria ?? state.successCriteria)
      state.expect = String(body?.expect ?? state.expect)
      return { id: 'demo-mission' }
    }
    if (path === `${base}/persona-specs`) {
      const specs = (body as unknown as { total?: number }[]) ?? []
      state.personaTotal = specs.reduce((sum, s) => sum + (s.total ?? 0), 0) || state.personaTotal
      return { total: state.personaTotal }
    }
    if (path === `${base}/personas/assemble`) return { total: state.personaTotal }

    if (path === `${base}/review`) {
      const n = state.personaTotal
      return {
        project: { id: site.id },
        test: {
          id: site.testId,
          // 검토 화면은 **지금 돌리려는 것**을 보여준다. 결과 화면은 그 기록을
          // 만든 미션을 보여준다 — 둘을 같은 값으로 묶으면 한쪽이 반드시 거짓이 된다.
          name: state.testName || missionOf(site.variant).name,
          device: 'desktop',
        },
        mission: { prompt: state.missionPrompt,
                   success_criteria: state.successCriteria,
                   expect: state.expect },
        personas: {
          total: n,
          // 화면은 연령대 표를 그리지만 우리 페르소나는 특성 축으로 나뉜다.
          // 없는 값을 지어내지 않고, 축 이름을 그대로 칸 이름으로 쓴다.
          breakdown: Object.entries(MOCK_DATA.axisDistribution).map(([axis, dist]) => {
            const counts = Object.values(dist as Record<string, number>)
            const low = (counts[0] ?? 0) + (counts[1] ?? 0)
            const high = (counts[3] ?? 0) + (counts[4] ?? 0)
            return {
              age_band: (MOCK_DATA.axes as Record<string, string>)[axis] ?? axis,
              total: counts.reduce((a, b) => a + b, 0),
              male: low,
              female: high,
              any: counts[2] ?? 0,
            }
          }),
        },
        estimate: {
          // 화면과 같은 공식을 쓴다 (web/src/lib/estimate.ts).
          minutes: Math.max(1, Math.round(n * 2 * 1.2 * 0.88)),
          credits: n,
          tokens: measured.tokensIn + measured.tokensOut,
          page_count: cleanMap.pages.length,
          vision_calls: (MOCK_DATA.maps.clean as { shots: number }).shots,
          usd: Math.round(measured.usdPerPersona * n * 10000) / 10000,
          measured: true,
          formula: `실측 1인당 $${measured.usdPerPersona} × ${n}명 (답사는 1회만, 이미지 ${(MOCK_DATA.maps.clean as { shots: number }).shots}장)`,
        },
      }
    }

    if (views) {
      if (path === base) {
        const m = missionOf(site.variant)
        return {
          id: site.testId,
          name: m.name,
          device: 'desktop',
          created_at: MOCK_DATA.generatedAt,
          project: { id: site.id, name: nameOf(site), preview_url: site.url },
          mission: { prompt: m.goal, success_criteria: m.criteria },
          ...views.detail,
        }
      }
      if (path === `${base}/paths`) return views.paths
      if (path === `${base}/diagram`) return views.diagram
      if (path === `${base}/personas`) return views.personas
      // 막대를 눌렀을 때 뜨는 단계 상세. 성격 문장은 페르소나 규격의
      // 원문을 그대로 내려보낸다 — 화면이 사람 성격을 지어내지 않도록.
      if (path === `${base}/steps`) {
        return {
          steps: views.steps,
          filmstrip: views.filmstrip,
          sentences: MOCK_DATA.axisSentences,
          axes: MOCK_DATA.axes,
          test_name: missionOf(site.variant).name,
          replay: views.replay,
        }
      }
    }
  }

/** 단계 상세 묶음. 테스트 상세와 A/B 결과가 같은 것을 쓴다. */
function stepsPayload(variant: string) {
  const v = byVariant[variant]
  if (!v) return null
  return {
    steps: v.steps,
    filmstrip: v.filmstrip,
    replay: v.replay,
    sentences: MOCK_DATA.axisSentences,
    axes: MOCK_DATA.axes,
    test_name: missionOf(variant).name,
  }
}

  // ── 두 프로젝트 견주기 ────────────────────────────────────────
  // 프로젝트 안에서는 자기 결과만 보여주고, 두 사이트를 나란히 놓는 일은
  // 여기서만 한다. 같은 사람 열 명을 양쪽에 똑같이 투입했기 때문에 성립한다.
  if (path === '/api/compare/projects') {
    return allSites().map((s) => ({
      id: s.id,
      name: nameOf(s),
      url: s.url,
      success_rate: rate(s.variant),
    }))
  }

  if (path === '/api/compare') {
    const left = siteById(params.get('base') ?? '')
    const right = siteById(params.get('against') ?? '')
    if (!left || !right || left.id === right.id) {
      return { ok: false, message: '서로 다른 프로젝트 두 개를 골라주세요.', items: [] }
    }
    // 내보낸 표에서 baseline 은 대조군, compare 는 그 실행 자신이다.
    // 그래서 '비교 사이트' 기준의 표를 꺼내면 baseline 이 곧 '기준 사이트'가 된다.
    const table = byVariant[right.variant]?.personas as
      | { items?: unknown[]; total?: number; changed?: number; exhausted?: number; axes?: Json }
      | undefined
    if (!table) return { ok: false, message: '아직 비교할 기록이 없어요.', items: [] }
    return {
      ok: true,
      base: { id: left.id, name: nameOf(left), url: left.url, success_rate: rate(left.variant) },
      against: {
        id: right.id,
        name: nameOf(right),
        url: right.url,
        success_rate: rate(right.variant),
      },
      ...table,
    }
  }

  if (path === '/api/ab' && method === 'GET') {
    return { items: abState.rows.map(abCard).filter(Boolean) }
  }

  if (path === '/api/ab' && method === 'POST') {
    const a = siteById(String(body?.a_project_id ?? ''))
    const b = siteById(String(body?.b_project_id ?? ''))
    if (!a || !b) return { error: '비교할 프로젝트 두 개를 골라주세요.' }
    const row: AbRow = {
      id: `ab-${abState.rows.length + 1}-${a.id}-${b.id}`,
      name: String(body?.name || `${nameOf(a)} vs ${nameOf(b)}`),
      a: a.id,
      b: b.id,
      createdAt: new Date().toISOString(),
    }
    // 최근 것이 위로 오게 앞에 넣는다. 씨앗은 그대로 뒤에 남는다.
    abState.rows = [row, ...abState.rows]
    saveAb(abState.rows.filter((r) => r.id !== AB_SEED.id))
    return { id: row.id }
  }

  const ab = abState.rows.find((r) => path === `/api/ab/${r.id}`)
  if (ab) {
    const a = siteById(ab.a)
    const b = siteById(ab.b)
    if (!a || !b) return { ok: false, message: '비교하던 프로젝트가 사라졌어요.' }

    // 표는 B(비교 사이트) 기준으로 뽑는다 — 그 표의 baseline 이 곧 A 가 된다.
    const raw = byVariant[b.variant]?.personas as
      | { items?: { code?: string; baseline?: Json; compare?: Json }[] }
      | undefined
    // 사람마다 양쪽에서 밟은 화면을 붙여 준다. 상세 패널이 이것으로 경로를 그린다.
    const table = raw
      ? {
          ...raw,
          items: (raw.items ?? []).map((row) => ({
            ...row,
            baseline: row.baseline
              ? { ...row.baseline, screens: pathOf(a.variant, String(row.code ?? '')) }
              : row.baseline,
            compare: row.compare
              ? { ...row.compare, screens: pathOf(b.variant, String(row.code ?? '')) }
              : row.compare,
          })),
        }
      : undefined
    return {
      id: ab.id,
      name: ab.name,
      mission: missionOf(a.variant).goal,
      created_at: ab.createdAt,
      a: { id: a.id, name: nameOf(a), preview_url: a.url, success_rate: rate(a.variant) },
      b: { id: b.id, name: nameOf(b), preview_url: b.url, success_rate: rate(b.variant) },
      compare: table
        ? { ok: true, ...table }
        : { ok: false, message: '아직 비교할 기록이 없어요.', items: [] },
      diagrams: {
        a: byVariant[a.variant]?.diagram ?? null,
        b: byVariant[b.variant]?.diagram ?? null,
      },
      // 흐름도 막대를 눌렀을 때 뜨는 단계 상세와 여정 재생. 테스트 상세 화면과
      // 같은 자료를 그대로 쓴다 — 여기만 안 눌리면 같은 그림인데 한쪽만
      // 죽어 있는 것처럼 보인다.
      steps: {
        a: stepsPayload(a.variant),
        b: stepsPayload(b.variant),
      },
    }
  }

  // /account는 서버에 실제 구현돼 있다(로그인한 사용자의 진짜 이름·이메일을
  // 돌려준다) — 여기서 ACCOUNT로 흉내내면 누가 가입해도 화면엔 항상 "영찬"만
  // 보인다. billing/*은 아직 결제가 없다는 정직한 스텁뿐이라(빈 tiers 등)
  // 그대로 흉내낸다 — 화면이 갑자기 휑해지는 것보다는 낫다.
  if (path === '/api/account') return MOCK_MISS
  if (path === '/api/billing/plan') return PLAN
  if (path === '/api/billing/credits') return CREDITS
  if (path === '/api/billing/tiers') return { tiers: PLAN_TIERS, packs: CREDIT_PACKS }

  // 실행 시작.
  //
  // 예전에는 이 요청을 진짜 서버로 넘겼다. 그런데 데모의 테스트 id 는 UUID 가
  // 아니라서(`moji-before-test`) FastAPI 가 경로 변수를 파싱하다 **422** 를 냈다.
  // 화면에는 "요청이 실패했어요 (HTTP 422)" 만 떴고, 사용자는 무엇이 잘못됐는지
  // 알 수 없었다.
  //
  // 데모에는 돌릴 파이프라인이 없다. 대신 이 사이트들은 **이미 돌려 둔 실행 기록**이
  // 있다. 그래서 새로 시작한 척하지 않고, 이미 끝난 실행이라고 사실대로 답한다 —
  // 화면은 그 결과로 데려간다.
  if (path.endsWith('/runs') && method === 'POST') {
    // 진짜로 돌리기로 했으면 여기서 답하지 않는다. 서버가 파이프라인을 띄운다.
    if (LIVE_RUN) return MOCK_MISS
    const testId = path.split('/')[3] ?? ''
    const site = siteByTest(testId)
    if (!site) {
      // 사용자가 직접 만든 프로젝트다. 재생할 기록도, 돌릴 파이프라인도 없다.
      throw new Error(
        '배포된 데모에는 실행할 서버가 붙어 있지 않아요. ' +
          '새로 만든 프로젝트는 로컬에서 돌려야 합니다.',
      )
    }
    const run = runs[site.variant]
    const total = run?.personas.length ?? state.personaTotal
    replay = {
      runId: run?.runId ?? `${site.testId}-run`,
      testId: site.testId,
      projectId: site.id,
      projectName: site.name,
      testName: MISSION[site.variant]?.name ?? site.name,
      total,
      startedAt: Date.now(),
      durationMs: Math.min(30_000, 11_000 + total * 320),
    }
    return {
      run_id: replay.runId,
      persona_count: total,
      status: 'running',
      test_id: site.testId,
      project_id: site.id,
    }
  }

  if (path === '/api/runs/active') {
    if (LIVE_RUN) return MOCK_MISS
    return activeReplay()
  }

  // 썸네일은 <img src> 로 직접 불려서 이 경로를 타지 않는다. 흉내 내지 않는다.
  return MOCK_MISS
}

/**
 * 배포본의 "돌리는 중" 화면.
 *
 * 배포된 데모에는 파이프라인이 붙어 있지 않다. 예전에는 그래서 시작 버튼이
 * 곧바로 결과로 튕겼는데, 누른 사람 눈에는 테스트가 순식간에 끝난 것처럼 보였다.
 *
 * 대신 **이미 돌려 둔 실행을 다시 재생한다.** 인원 수와 도착 순서는 그 기록에
 * 있는 실제 값이고, 재생되는 것은 시간뿐이다. 화면에도 재생 중이라고 적는다 —
 * 지금 새로 도는 것처럼 보이게 두면 그건 없는 실행을 지어내는 것이다.
 */
type Replay = {
  runId: string
  testId: string
  projectId: string
  projectName: string
  testName: string
  total: number
  startedAt: number
  durationMs: number
}

let replay: Replay | null = null

/** 답사가 앞의 30%, 페르소나가 나머지 70%. 서버가 실제로 쓰는 배분과 같다. */
function activeReplay() {
  if (!replay) return null
  const elapsed = Date.now() - replay.startedAt
  const ratio = Math.min(1, elapsed / replay.durationMs)
  const percent = Math.round(ratio * 100)
  // 답사(0~30%) 동안에는 아직 아무도 끝나지 않았다.
  const done =
    ratio <= 0.3 ? 0 : Math.min(replay.total, Math.floor(((ratio - 0.3) / 0.7) * replay.total))
  return {
    percent,
    run_id: replay.runId,
    project_id: replay.projectId,
    project_name: replay.projectName,
    test_name: replay.testName,
    test_id: replay.testId,
    done,
    total: replay.total,
    replay: true,
  }
}

/** 화면이 결과를 더 자세히 보여주고 싶을 때 쓰라고 열어둔다. */
export const demoRuns = { runs, measured, maps: MOCK_DATA.maps, sites: SITES }
