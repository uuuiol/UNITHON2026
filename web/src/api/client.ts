import { clearToken, getToken } from '../lib/authToken'
import { MOCK_MISS, mockResponse } from './mock'
import { ApiError } from './errors'

const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

/**
 * 데모 모드. 백엔드 없이 프론트 하나로 돌린다 (MVP 광고용).
 * 진짜 백엔드에 붙이려면 web/.env 에 VITE_MOCK=0 을 넣는다.
 */
const USE_MOCK = (import.meta.env.VITE_MOCK ?? '1') !== '0'

/** fetch 를 거치지 않는 것(예: <img src>)도 서버 주소가 필요하다. */
export const API_BASE = BASE

// 서버가 돌려준 오류를 화면이 그대로 보여줄 수 있는 형태로 감싼다.
// 정의는 errors.ts에 있다(mock.ts도 같이 던져야 해서 — 순환 참조 설명은 그쪽에).
export { ApiError }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (USE_MOCK) {
    const canned = await mockResponse(path, init)
    // 흉내 낼 수 없는 경로만 진짜 서버로 넘긴다. null 은 그 자체가 정상 응답일 수 있다
    // (예: 실행 중인 것이 없으면 /api/runs/active 는 null 을 돌려준다).
    if (canned !== MOCK_MISS) {
      // 실제 호출처럼 보이도록 한 박자 쉰다. 로딩 상태가 화면에서 사라지지 않도록.
      await new Promise((r) => setTimeout(r, 180))
      return canned as T
    }
  }

  const token = getToken()
  const headers: Record<string, string> = {}
  if (init?.body) headers['Content-Type'] = 'application/json'
  if (token) headers['Authorization'] = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { ...headers, ...(init?.headers as Record<string, string> | undefined) },
    })
  } catch {
    // 서버가 안 떠 있는 경우와 서버가 에러를 준 경우는 사용자가 할 일이 다르다.
    throw new ApiError(`API 서버(${BASE})에 닿지 못했어요. 백엔드가 떠 있는지 확인해 주세요.`, 0)
  }

  if (response.status === 401) {
    // 토큰이 없거나 만료됐다. 지워 두면 라우트 가드가 알아서 로그인 화면으로 보낸다.
    clearToken()
  }

  if (!response.ok) {
    const detail = await response
      .json()
      .then((body) => (typeof body?.detail === 'string' ? body.detail : null))
      .catch(() => null)
    throw new ApiError(detail ?? `요청이 실패했어요 (HTTP ${response.status})`, response.status)
  }

  if (response.status === 204) return undefined as T
  return response.json()
}

// --------------------------------------------------------------------------- //
// 인증
// --------------------------------------------------------------------------- //

export type AuthResult = {
  token: string
  user: { id: string; email: string; name: string; workspace: string }
}

export const signup = (email: string, password: string, name: string) =>
  request<AuthResult>('/api/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ email, password, name }),
  })

export const login = (email: string, password: string) =>
  request<AuthResult>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })

// --------------------------------------------------------------------------- //
// 연결 검사
// --------------------------------------------------------------------------- //

export type ConnectivityResult = {
  ok: boolean
  url: string
  final_url: string | null
  status: number | null
  title: string | null
  /** 도달 가능 여부와 별개다. 열리지만 iframe 임베드만 막는 사이트가 흔하다. */
  embeddable: boolean | null
  embed_block_reason: string | null
  link_count: number | null
  error_kind: string | null
  message: string
  /** 확인은 못 했지만 넘어가도 되는 경우(시간 초과 등).
   *  느린 사이트를 '없는 주소' 취급해서 막아 두지 않는다. */
  proceed_anyway?: boolean
}

export function checkConnectivity(url: string) {
  return request<ConnectivityResult>('/api/connectivity/check', {
    method: 'POST',
    body: JSON.stringify({ url }),
  })
}

// --------------------------------------------------------------------------- //
// 미션 분석
// --------------------------------------------------------------------------- //

export type MissionIssue = { kind: string; message: string; fix: string }

export type MissionAnalysis = {
  /** ok = 그대로 써도 됨 · warning = 고치면 더 좋음 · invalid = 이대로는 못 돌림 */
  status: 'ok' | 'warning' | 'invalid'
  success_criteria: string | null
  issues: MissionIssue[]
  generated_by: string
}

export function analyzeMission(prompt: string) {
  return request<MissionAnalysis>('/api/missions/analyze', {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  })
}

// --------------------------------------------------------------------------- //
// 프로젝트
// --------------------------------------------------------------------------- //

export type ProjectCard = {
  id: string
  name: string
  category: string
  test_count: number
  last_activity_at: string
  /** 카드 썸네일에 띄울 실제 주소. 임베드가 막힌 사이트면 대체 이미지를 쓴다. */
  preview_url: string | null
  preview_embeddable: boolean
  /** 지울 수 있는가. 이 자리에서 직접 만든 프로젝트만 지운다 —
   *  데모에 딸려 오는 세 개는 기록이 코드에 들어 있어서 지울 대상이 아니다. */
  removable?: boolean
}

export type ProjectDetail = {
  id: string
  name: string
  category: string
  device_preset: string
  viewport: { w: number; h: number }
  test_count: number
  /** 여정이 하나도 없으면 null — 화면이 "0.0%"라는 거짓 수치를 그리지 않도록. */
  success_rate: number | null
  drop_rate: number | null
  preview_url: string | null
  preview_embeddable: boolean
  variants: { key: string; label: string; base_url: string; is_control: boolean }[]
}

export type TestStats = {
  test_id: string
  name: string
  created_at: string
  persona_count: number
  success_rate: number | null
  drop_rate: number | null
}

export const listProjects = () => request<ProjectCard[]>('/api/projects')

/** 이 자리에서 만든 프로젝트를 지운다. 데모 프로젝트는 지워지지 않는다. */
export const deleteProject = (id: string) =>
  request<{ ok: boolean; message?: string }>(`/api/projects/${id}`, { method: 'DELETE' })

export const getProject = (id: string) => request<ProjectDetail>(`/api/projects/${id}`)

export const listTests = (projectId: string) =>
  request<TestStats[]>(`/api/projects/${projectId}/tests`)

export function createProject(body: {
  name: string
  category: string
  target_url: string
  source?: string
  device_preset?: string
  flow_map_path?: string | null
  preview_embeddable?: boolean
}) {
  return request<ProjectCard>('/api/projects', { method: 'POST', body: JSON.stringify(body) })
}

// --------------------------------------------------------------------------- //
// 테스트 마법사
// --------------------------------------------------------------------------- //

export function createTest(
  projectId: string,
  body: { name: string; device: string; target_url: string },
) {
  return request<{ id: string }>(`/api/projects/${projectId}/tests`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function saveMission(
  testId: string,
  body: { prompt: string; success_criteria: string; auto_detect?: boolean;
          /** 달성을 인정할 근거 문구 */ expect?: string },
) {
  return request<{ id: string }>(`/api/tests/${testId}/mission`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

export type PersonaSpecPayload = {
  age_band: string
  total: number
  female_percent?: number
  gender_agnostic?: boolean
  enabled?: boolean
}

export function savePersonaSpecs(testId: string, specs: PersonaSpecPayload[]) {
  return request<{ total: number }>(`/api/tests/${testId}/persona-specs`, {
    method: 'PUT',
    body: JSON.stringify(specs),
  })
}

export type ReviewPayload = {
  project: { id: string }
  test: { id: string; name: string; device: string }
  mission: {
    prompt: string
    success_criteria: string
    /** 달성을 인정할 근거 문구. 사용자가 미션 화면에서 정한다. */
    expect?: string
  } | null
  personas: {
    total: number
    breakdown: { age_band: string; total: number; male: number; female: number; any: number }[]
  }
  estimate: {
    minutes: number
    /** 페르소나 1명 = 1크레딧. 예전에는 토큰을 보여줬는데 결제 단위가 아니라 뜻이 없었다. */
    credits?: number
    tokens: number
    page_count: number
    vision_calls: number
    usd: number
    measured: boolean
    formula: string
  }
}

export const getReview = (testId: string) => request<ReviewPayload>(`/api/tests/${testId}/review`)

/** 실행을 시작할 때 서버에 함께 넘기는 것. 비워 보내면 서버가 기본값(테스트베드)을
 *  돌아서, 어느 프로젝트에서 눌렀든 같은 결과가 나온다. */
export type RunRequest = {
  url?: string
  goal?: string
  /** 달성을 인정할 근거 문구. 이 글자가 화면에 뜬 적이 없으면 달성으로 세지 않는다. */
  expect?: string
  personas?: number
  test_name?: string
  /** 진행 화면이 "무엇을 돌리는 중"인지 말할 수 있게 함께 보낸다. */
  project_id?: string
  project_name?: string
  /** 연령대·성별 비율. 이걸 보내면 인원을 이 명세가 정한다. */
  persona_specs?: PersonaSpecPayload[]
}

export const startRun = (testId: string, req: RunRequest = {}) =>
  request<{
    run_id: string
    persona_count: number
    status: string
    /** 이미 끝난 실행이면 결과로 바로 보낼 수 있게 대상을 같이 준다. */
    test_id?: string
    project_id?: string
  }>(`/api/tests/${testId}/runs`, {
    method: 'POST',
    body: JSON.stringify(req),
  })

// --------------------------------------------------------------------------- //
// 실행중
// --------------------------------------------------------------------------- //

export type ActiveRun = {
  /** 두 단계를 합친 진행률. 답사가 앞의 30%, 페르소나가 나머지 70%.
   *  없으면 화면이 done/total 로 계산한다(옛 서버 호환). */
  percent?: number
  run_id: string
  project_id: string
  project_name: string
  test_name: string
  done: number
  total: number
  /** 끝났을 때 어느 결과로 데려갈지. */
  test_id?: string
  /** 결과를 읽어올 기록 폴더 이름 (agent-ux/logs/<run_log>).
   *  로컬에서 진짜로 돌렸을 때만 온다. */
  run_log?: string
  /** 지금 새로 도는 것이 아니라 **이미 돌려 둔 실행을 다시 재생**하는 중.
   *  배포본에는 파이프라인이 붙어 있지 않아 이 값이 켜진다. */
  replay?: boolean
}

export const getActiveRun = () => request<ActiveRun | null>('/api/runs/active')

// --------------------------------------------------------------------------- //
// 테스트 상세 — 미션 경로 · 다이어그램 · 페르소나
// --------------------------------------------------------------------------- //

export type TestDetail = {
  id: string
  name: string
  device: string
  created_at: string
  project: { id: string; name: string; preview_url: string | null }
  mission: {
    prompt: string
    success_criteria: string
    /** 달성을 인정할 근거 문구. 사용자가 미션 화면에서 정한다. */
    expect?: string
  } | null
  persona_total: number
  journey_count: number
  /** 여정이 없으면 null — 화면이 "0.0%"라는 거짓 수치를 그리지 않도록. */
  success_rate: number | null
  drop_rate: number | null
  avg_success_steps: number | null
}

export type PathScreen = { key: string; title: string; url: string | null }

export type MissionPath = {
  rank: number
  name: string
  label: string
  persona_count: number
  step_count: number
  screens: PathScreen[]
  /** 카드에 다 못 실은 화면 수. 0이면 "+n" 을 그리지 않는다. */
  more: number
}

export type PathsPayload = {
  total: number
  success: { count: number; percent: number }
  drop: { count: number; percent: number }
  paths: { success: MissionPath[]; drop: MissionPath[] }
}

export type DiagramNode = {
  id: string
  column: number
  key: string
  title: string
  count: number
  success: number
  drop: number
}

export type DiagramPayload = {
  /** 열 하나 = 한 스텝. 한 열에 여러 화면이 동시에 설 수 있다. */
  columns: { index: number; label: string; nodes: DiagramNode[] }[]
  links: { source: string; target: string; count: number; success: number; drop: number }[]
  total: number
  /** 열 상한을 넘겨 끝까지 그리지 못한 인원. 조용히 버리면 전수를 본 것처럼 읽힌다. */
  truncated?: number
  max_columns?: number
}

/** 하나의 클릭. 좌표는 페이지 절대좌표라 화면 사진 위에 그대로 얹혀진다. */
export type StepClick = {
  x: number
  y: number
  w: number
  h: number
  label: string
  /** 눌렀는데 화면이 아무런 반응도 하지 않았다 — 헛클릭. */
  wasted: boolean
  persona: string
}

export type StepDot = { x: number; y: number; wasted: boolean }

export type StepPersona = {
  id: string
  /** "P001" 형식 짧은 코드. "번호" 표시 모드는 id(UUID)가 아니라 이걸 쓴다. */
  code: string
  label: string
  traits: Record<string, number>
  /** 사용자가 화면에서 정하는 값. 행동 규칙은 traits 가 정한다. */
  age_band?: string | null
  gender?: string | null
  outcome: 'success' | 'drop'
  end_label: string
  total_steps: number
  /** 그 순간 이 사람이 무슨 생각으로 그것을 눌렀는지. */
  thought: string
  action: string
  target: string
  blocked: boolean
  /** 같은 단계에 다른 화면에 있었을 때만 채워진다. */
  screen?: string
  screen_title?: string
}

export type StepDetail = {
  id: string
  step: number
  screen: string
  title: string
  count: number
  shot: { src: string; w: number; h: number } | null
  clicks: StepClick[]
  /** 이 화면에서 벌어진 클릭 전부. 열지도의 바탕이 된다. */
  screen_clicks: StepDot[]
  wasted: number
  /** 이 단계에 이 화면에 있던 사람. */
  personas: StepPersona[]
  /** 같은 단계에 다른 화면에 있던 사람. */
  elsewhere: StepPersona[]
  /** 이 단계 전에 이미 끝난 사람. */
  finished: StepPersona[]
  /** 셋을 더하면 전체 인원이 된다. */
  total: number
}

export type FilmFrame = {
  step: number
  id: string
  title: string
  count: number
  shot: { src: string; w: number; h: number } | null
  /** 같은 단계에 다른 화면에 있었던 무리의 수. */
  others: number
}

export type PersonaOutcome = 'success' | 'drop' | 'other' | null

/** 한쪽 사이트에서의 결과. 기준(정상판)과 비교(결함판)를 나란히 놓기 위한 것. */
export type PersonaSideResult = {
  outcome: PersonaOutcome
  end_label: string
  step_count: number | null
  /** 그 사람이 밟은 화면 이름. A/B 상세 패널만 쓴다 — 없으면 경로를 그리지 않는다. */
  screens?: string[]
}

export type PersonaRow = {
  /** 사용자가 정한 값. 없던 시절 기록에는 비어 있다. */
  age_band_real?: string | null
  gender_real?: string | null
  id: string
  code: string
  name: string
  age_band: string
  gender: string
  outcome: PersonaOutcome
  step_count: number | null
  /** 테스트 중 만들어진 행동 특성. 축마다 2단계 문자열(예: "정독"/"훑기"). 사용자가 정하는 값이 아니다. */
  traits?: Record<string, string>
  /** 기준 사이트(정상판) 결과. 대조군이 없으면 null. */
  baseline?: PersonaSideResult | null
  /** 비교 사이트(결함판) 결과. */
  compare?: PersonaSideResult | null
  /** 두 사이트에서 결과가 갈렸는가. 이 사람들이 결함의 대가를 치른다. */
  changed?: boolean
}

/** 결과 화면이 어느 사이트 기준으로 볼지. 정상판(대조군) / 결함판. */
export type Variant = 'clean' | 'buggy'

/** ?variant= 를 붙인다. 고른 것이 없으면 서버가 기본값을 고른다. */
/**
 * 결과를 어디서 읽을지 정한다.
 *
 * `runId` 가 있으면 **방금 로컬에서 돌린 그 실행**(agent-ux/logs/<run_id>)을 읽는다.
 * 없으면 예전처럼 테스트 id 로 묻고, 데모에서는 번들된 기록이 답한다.
 */
const src = (runId: string | undefined, testId: string, tail = '') =>
  runId ? `/api/live/${runId}${tail}` : `/api/tests/${testId}${tail}`

const withVariant = (path: string, variant?: Variant) =>
  variant ? `${path}?variant=${variant}` : path

export const getTest = (testId: string, variant?: Variant, runId?: string) =>
  request<TestDetail>(withVariant(src(runId, testId), variant))

export const getTestPaths = (testId: string, variant?: Variant, runId?: string) =>
  request<PathsPayload>(withVariant(src(runId, testId, '/paths'), variant))

export const getTestDiagram = (testId: string, variant?: Variant, runId?: string) =>
  request<DiagramPayload>(withVariant(src(runId, testId, '/diagram'), variant))

export type PersonasPayload = {
  total: number
  items: PersonaRow[]
  /** 결과가 갈린 인원 · 스텝을 다 쓴 인원. 표 위 요약 칩에 쓴다. */
  changed?: number
  exhausted?: number
  baseline_run?: string | null
  compare_run?: string | null
  axes?: Record<string, string>
}

export const getTestPersonas = (testId: string, variant?: Variant, runId?: string) =>
  request<PersonasPayload>(withVariant(src(runId, testId, '/personas'), variant))

/** 한 사람의 여정 한 장면. 화면은 사진을 이 스크롤 위치로 밀고 표시만 얹는다. */
export type ReplayFrame = {
  step: number
  screen: string
  title: string
  shot: { src: string; w: number; h: number } | null
  scroll_y: number
  viewport: { w: number; h: number }
  thought: string
  action: string
  target: string
  /** 누른 자리 (문서 절대좌표). 스크롤·기다림처럼 짚은 곳이 없으면 null. */
  box: { x: number; y: number; w: number; h: number } | null
  changed: boolean
  note: string
  blocked: boolean
  elapsed_ms: number | null
}

export type PersonaReplay = {
  id: string
  label: string
  traits: Record<string, number>
  /** 사용자가 화면에서 정하는 값. 행동 규칙은 traits 가 정한다. */
  age_band?: string | null
  gender?: string | null
  outcome: 'success' | 'drop'
  end_label: string
  steps: number
  synthetic: boolean
  frames: ReplayFrame[]
}

export type StepsPayload = {
  /** 막대 id → 그 막대를 눌렀을 때 보여줄 것. */
  steps: Record<string, StepDetail>
  /** 아래 필름 띄. 단계마다 사람이 가장 많았던 화면을 대표로 세운다. */
  filmstrip: FilmFrame[]
  /** 성격 문장표. 페르소나 규격의 원문이라 화면이 지어낼 일이 없다. */
  sentences: Record<string, Record<string, string>>
  axes: Record<string, string>
  test_name: string
  /** 페르소나 id → 그 사람의 전체 여정. 어디서든 한 명을 골라 재생한다. */
  replay?: Record<string, PersonaReplay>
}

export const getTestSteps = (testId: string, variant?: Variant, runId?: string) =>
  request<StepsPayload>(withVariant(src(runId, testId, '/steps'), variant))


// --------------------------------------------------------------------------- //
// 두 프로젝트 견주기
//
// 프로젝트 안에서는 자기 사이트 결과만 보여준다. 고치기 전과 고친 뒤를 나란히
// 놓는 일은 여기서만 한다 — 같은 사람 열 명을 양쪽에 똑같이 투입했기 때문에
// "이 사람이 못한 게 사이트 탓인지 역량 탓인지"가 이 표에서만 갈린다.
// --------------------------------------------------------------------------- //

export type CompareSide = {
  id: string
  name: string
  url: string
  success_rate: number | null
}

export type ComparePayload = {
  ok: boolean
  message?: string
  base?: CompareSide
  against?: CompareSide
  items: PersonaRow[]
  total?: number
  changed?: number
  exhausted?: number
  axes?: Record<string, string>
}

export const listComparableProjects = () =>
  request<CompareSide[]>('/api/compare/projects')

export const compareProjects = (base: string, against: string) =>
  request<ComparePayload>(`/api/compare?base=${base}&against=${against}`)

// --------------------------------------------------------------------------- //
// 계정 · 플랜 · 크레딧 (설정 / 크레딧 및 플랜 화면)
// --------------------------------------------------------------------------- //

export type Account = {
  name: string
  initial: string
  workspace: string
  email: string
  plan_label: string
}

export type PlanPayload = {
  current: {
    name: string
    price_label: string
    next_billing_at: string
    used: number
    quota: number
  }
  features: string[]
  upgrade: { badge: string; title: string; body: string; cta: string; note: string }
}

export type CreditsPayload = {
  balance: number
  used_this_month: number
  rules: { label: string; value: string; highlight: boolean }[]
  packs: { credits: number; price: string; featured: boolean }[]
  history: { at: string; label: string; delta: number }[]
}

export type PlanTier = {
  id: string
  name: string
  /** 카드 제목 밑 한 줄 */
  tagline: string
  /** 월 요금 */
  price: string
  /** 버튼에 적히는 말 */
  cta: string
  /** 카드 오른쪽 위 딱지. 없으면 null */
  badge: string | null
  /** 이 요금제에 들어 있는 크레딧 */
  credits: number
  /** 체크 표시가 붙는 항목 — 이 요금제에서 되는 것 */
  features: string[]
  /** 체크가 아니라 빗금이 붙는 항목 — 이 요금제에서 안 되는 것.
   *  못 하는 것에 파란 체크를 달면 되는 것처럼 읽힌다. */
  limits: string[]
  featured: boolean
}

/** 추가로 살 수 있는 크레딧 묶음 */
export type CreditPack = { credits: number; price: string }

export const getAccount = () => request<Account>('/api/account')

export function updateAccount(body: { name: string; workspace: string; email: string }) {
  return request<Account>('/api/account', { method: 'PUT', body: JSON.stringify(body) })
}
export const getPlan = () => request<PlanPayload>('/api/billing/plan')
export const getCredits = () => request<CreditsPayload>('/api/billing/credits')
export const getPlanTiers = () =>
  request<{ tiers: PlanTier[]; packs: CreditPack[] }>('/api/billing/tiers')

// --------------------------------------------------------------------------- //
// A/B 테스트
// --------------------------------------------------------------------------- //

export type AbSide = {
  id: string
  name: string
  preview_url: string | null
  success_rate?: number | null
}

export type AbCard = {
  id: string
  name: string
  mission: string
  created_at: string
  a: AbSide
  b: AbSide
}

export type AbResult = {
  id: string
  name: string
  mission: string
  created_at: string
  a: AbSide
  b: AbSide
  compare:
    | { ok: true; items: PersonaRow[]; total?: number; changed?: number; exhausted?: number; axes?: Record<string, string> }
    | { ok: false; message: string; items: PersonaRow[] }
  diagrams: { a: DiagramPayload | null; b: DiagramPayload | null }
  /** 흐름도 막대를 눌렀을 때 뜨는 단계 상세·여정 재생. 테스트 상세와 같은 자료. */
  steps?: { a: StepsPayload | null; b: StepsPayload | null }
}

export const listAbTests = () => request<{ items: AbCard[] }>('/api/ab')

export const getAbTest = (id: string) => request<AbResult>(`/api/ab/${id}`)

export function createAbTest(body: {
  name: string
  a_project_id: string
  b_project_id: string
}) {
  return request<{ id?: string; error?: string }>('/api/ab', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
