import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  getTest,
  getTestDiagram,
  getTestSteps,
  getTestPaths,
  getTestPersonas,
  type MissionPath,
} from '../api/client'
import { useRunId } from '../lib/useRunId'
import { useQuery } from '../api/hooks'
import backArrow from '../assets/icons/back-arrow.svg'
import { Emoji, type EmojiName } from '../components/Emoji'
import { Icon } from '../components/Icon'
import { MissionPathCard } from '../components/MissionPathCard'
import { NavigationDiagram } from '../components/NavigationDiagram'
import { PersonaFace, PersonaNameToggle, usePersonaLabel } from '../components/PersonaIdentity'
import { PersonaReplayModal } from '../components/PersonaReplayModal'
import { StepDetailModal } from '../components/StepDetailModal'
import { SegmentedControl } from '../components/SegmentedControl'
import { SitePreview } from '../components/SitePreview'
import { Chip, SideResult, TraitDots } from '../components/PersonaBits'
import { ErrorBlock, LoadingBlock } from '../components/StateView'
import { TestSidebar } from '../components/TestSidebar'

type ViewMode = 'path' | 'diagram' | 'persona'

const VIEWS = [
  { value: 'path', label: '경로', icon: <Icon name="list" size={19} /> },
  { value: 'diagram', label: '다이어그램', icon: <Icon name="graph" size={20} /> },
  { value: 'persona', label: '페르소나', icon: <Icon name="userProfile" size={19} /> },
] as const satisfies readonly { value: ViewMode; label: string; icon: React.ReactNode }[]

type Outcome = 'success' | 'drop'

/**
 * 테스트 상세 (Figma 264:8033 · 276:3101 · 276:3259 · 264:8736).
 *
 * 전역 사이드바를 쓰지 않는다 — 이 화면은 상단 바가 화면 전체 폭을 쓰고,
 * 왼쪽에는 같은 프로젝트의 테스트/페르소나 목록이 온다.
 */
export function TestDetailPage() {
  const { projectId = '', testId = '' } = useParams()
  const navigate = useNavigate()

  const runId = useRunId()
  const test = useQuery(() => getTest(testId, undefined, runId), [testId, runId])

  return (
    <div className="flex h-full min-h-screen flex-col bg-bg">
      <header className="flex h-[70px] shrink-0 items-center gap-[12px] border-b border-line bg-white pr-[40px] pl-[30px]">
        <button
          type="button"
          onClick={() => navigate(`/projects/${projectId}`)}
          aria-label="프로젝트로 돌아가기"
          className="shrink-0"
        >
          <img src={backArrow} alt="" className="size-[30px] rotate-180" />
        </button>
        <p className="flex items-center gap-[2px] leading-[1.45] whitespace-nowrap">
          <span className="text-[20px] font-semibold text-heading">
            {test.data?.project.name ?? ''} /
          </span>
          <span className="text-[15px] text-ink">{test.data?.name ?? ''}</span>
        </p>
      </header>

      <div className="flex min-h-0 flex-1">
        <TestSidebar projectId={projectId} testId={testId} />

        <main className="min-h-0 flex-1 overflow-y-auto px-[40px] py-[40px]">
          <div className="w-full max-w-[1573px] rounded-[16px] border border-line bg-white px-[27px] pt-[40px] pb-[40px]">
            {test.loading ? <LoadingBlock label="테스트를 불러오는 중이에요" /> : null}
            {test.error ? <ErrorBlock message={test.error} onRetry={test.reload} /> : null}

            {test.data ? (
              <>
                <div className="ml-[13px]">
                  <h1 className="text-[34px] leading-[1.45] font-bold text-ink">
                    {test.data.project.name} / {test.data.name}
                  </h1>
                  <p className="mt-[4px] text-[20px] leading-[1.45] text-subtext">
                    {test.data.mission?.prompt ?? '아직 미션이 저장되지 않았어요.'}
                  </p>
                </div>

                <div className="mt-[40px] ml-[53px] flex items-center">
                  <Stat
                    icon="target"
                    value={pct(test.data.success_rate)}
                    label="미션 성공률"
                    tone="success"
                    className="w-[406px]"
                  />
                  <Stat
                    icon="warning"
                    value={pct(test.data.drop_rate)}
                    label="이탈률"
                    tone="drop"
                    className="w-[458px]"
                    divider
                  />
                  <Stat
                    icon="chart"
                    value={steps(test.data.avg_success_steps)}
                    label="평균 미션 성공 step"
                    divider
                  />
                </div>

                {/* 테스트를 옮기면 보기 상태도 처음으로 돌아간다. key 로 갈아 끼우면
                    '다이어그램을 보던 상태'가 다음 테스트로 새지 않는다. */}
                <MissionPathSection key={testId} testId={testId} />
              </>
            ) : null}
          </div>
        </main>
      </div>
    </div>
  )
}

/** '미션 경로' 제목 + 보기 전환 + 고른 보기. 보기 상태는 여기에만 산다. */
function MissionPathSection({ testId }: { testId: string }) {
  const [view, setView] = useState<ViewMode>('path')

  return (
    <>
      <div className="mt-[40px] flex items-center justify-between">
        <div>
          <h2 className="text-[24px] leading-[1.45] font-bold text-heading">미션 경로</h2>
          <p className="mt-[4px] text-[14px] leading-[1.45] text-subtext">
            AI 페르소나가 실제로 이동한 경로와 미션 완료 방식을 확인해요.
          </p>
        </div>
        <SegmentedControl options={VIEWS} value={view} onChange={setView} className="w-[420px]" />
      </div>

      {view === 'path' ? <PathView testId={testId} /> : null}
      {view === 'diagram' ? <DiagramView testId={testId} /> : null}
      {view === 'persona' ? <PersonaView testId={testId} /> : null}
    </>
  )
}

// --------------------------------------------------------------------------- //
// 경로
// --------------------------------------------------------------------------- //

function PathView({ testId }: { testId: string }) {
  const runId = useRunId()
  const paths = useQuery(() => getTestPaths(testId, undefined, runId), [testId, runId])
  const [outcome, setOutcome] = useState<Outcome>('success')
  const [heatmap, setHeatmap] = useState<MissionPath | null>(null)

  if (paths.loading) return <LoadingBlock label="경로를 불러오는 중이에요" />
  if (paths.error) return <ErrorBlock message={paths.error} onRetry={paths.reload} />
  if (!paths.data) return null

  const list = paths.data.paths[outcome]
  const share = paths.data[outcome]

  return (
    <>
      <div className="mt-[16px] flex border-b border-line">
        <OutcomeTab
          label="성공"
          count={paths.data.success.count}
          percent={paths.data.success.percent}
          active={outcome === 'success'}
          onClick={() => setOutcome('success')}
        />
        <OutcomeTab
          label="이탈률"
          count={paths.data.drop.count}
          percent={paths.data.drop.percent}
          active={outcome === 'drop'}
          onClick={() => setOutcome('drop')}
        />
      </div>

      <div className="mt-[19px] flex items-center justify-between">
        <p className="text-[14px] leading-[1.45] text-subtext">
          {outcome === 'success' ? '성공한' : '이탈한'} {share.count}명의 주요 경로
        </p>
        <p className="text-[12px] leading-[1.45] text-subtext">
          동일한 화면 이동 순서 기준으로 묶었어요
        </p>
      </div>

      <div className="mt-[18px] flex flex-col gap-[18px]">
        {list.length === 0 ? (
          <p className="py-[80px] text-center text-[15px] text-subtext">
            아직 묶을 이동 기록이 없어요. 테스트를 한 번 돌리면 여기에 경로가 쌓여요.
          </p>
        ) : null}
        {list.map((path) => (
          <MissionPathCard key={path.rank} path={path} onHeatmap={() => setHeatmap(path)} />
        ))}
      </div>

      <HeatmapModal path={heatmap} onClose={() => setHeatmap(null)} />
    </>
  )
}

function OutcomeTab({
  label,
  count,
  percent,
  active,
  onClick,
}: {
  label: string
  count: number
  percent: number
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`-mb-px flex w-[183px] flex-col items-center gap-[20px] transition-colors ${
        active ? 'text-main' : 'text-subtext hover:text-ink'
      }`}
    >
      <span className="flex items-center gap-[12px]">
        <span className="text-[16px] leading-[1.45] font-bold">{label}</span>
        {/* 자릿수가 달라도 칸 폭이 흔들리지 않도록 고정 폭을 준다. */}
        <span className="flex h-[27px] w-[72px] items-center justify-center rounded-[6px] border border-line bg-white text-[13px] leading-[1.45] font-semibold tabular-nums">
          {count}
          <span>({percent}%)</span>
        </span>
      </span>
      <span className={`h-[2px] w-full ${active ? 'bg-main' : 'bg-transparent'}`} />
    </button>
  )
}

/** 히트맵 화면은 아직 디자인이 없다. 지금은 그 경로가 지난 화면을 크게 펼쳐 보여준다. */
function HeatmapModal({ path, onClose }: { path: MissionPath | null; onClose: () => void }) {
  useEffect(() => {
    if (!path) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [path, onClose])

  if (!path) return null

  return (
    <div
      role="dialog"
      aria-modal
      aria-label={`${path.name} 화면 순서`}
      onClick={onClose}
      className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-[32px]"
    >
      <div
        onClick={(event) => event.stopPropagation()}
        className="max-h-full w-[980px] max-w-full overflow-y-auto rounded-[16px] bg-white p-[28px] shadow-[0_20px_60px_rgba(0,0,0,0.25)]"
      >
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[20px] font-bold text-heading">
              {path.name} · {path.label}
            </p>
            <p className="mt-[4px] text-[14px] text-subtext">
              {path.persona_count}명 · {path.step_count} step
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="닫기"
            className="text-[18px] leading-none text-subtext hover:text-ink"
          >
            ×
          </button>
        </div>

        <ol className="mt-[20px] grid grid-cols-4 gap-[16px]">
          {path.screens.map((screen, index) => (
            <li key={`${screen.key}-${index}`} className="flex flex-col gap-[6px]">
              <div className="h-[150px] overflow-hidden rounded-[8px] border border-line">
                <SitePreview url={screen.url} alt={screen.title} fit="cover" />
              </div>
              <p className="truncate text-[13px] text-body">
                {index + 1}. {screen.title}
              </p>
            </li>
          ))}
        </ol>
        {path.more > 0 ? (
          <p className="mt-[14px] text-[13px] text-subtext">화면 {path.more}개는 접었어요.</p>
        ) : null}
      </div>
    </div>
  )
}

// --------------------------------------------------------------------------- //
// 다이어그램
// --------------------------------------------------------------------------- //

function DiagramView({ testId }: { testId: string }) {
  const runId = useRunId()
  const diagram = useQuery(() => getTestDiagram(testId, undefined, runId), [testId, runId])
  // 단계 상세는 흐름도와 같은 실행에서 나온 것이라 함께 받아둔다. 막대를 누른
  // 뒤에 받으면 창이 빈 채로 먼저 뜬다.
  const steps = useQuery(() => getTestSteps(testId, undefined, runId), [testId, runId])
  const [picked, setPicked] = useState<string | null>(null)
  const detail = picked ? steps.data?.steps[picked] : null
  const replay = steps.data?.replay

  return (
    <section className="mt-[7px] rounded-[16px] border border-line px-[24px] pt-[22px] pb-[24px]">
      <h3 className="text-[24px] leading-[1.45] font-bold text-heading">네비게이션 다이어그램 뷰</h3>
      <div className="mt-[4px] flex items-center gap-[12px]">
        <Legend color="#00824f" label="성공" />
        <Legend color="#df2d48" label="실패" />
      </div>

      <div className="mt-[29px]">
        {diagram.loading ? <LoadingBlock label="흐름을 그리는 중이에요" /> : null}
        {diagram.error ? <ErrorBlock message={diagram.error} onRetry={diagram.reload} /> : null}
        {diagram.data ? (
          <NavigationDiagram
            data={diagram.data}
            // 상세가 아직 안 왔거나 그 막대에 상세가 없으면(달성·이탈 막대)
            // 누를 수 있는 척하지 않는다.
            onPickNode={
              steps.data
                ? (id) => {
                    if (steps.data?.steps[id]) setPicked(id)
                  }
                : undefined
            }
          />
        ) : null}
      </div>

      {detail && steps.data ? (
        <StepDetailModal
          detail={detail}
          filmstrip={steps.data.filmstrip}
          sentences={steps.data.sentences}
          axes={steps.data.axes}
          testName={steps.data.test_name}
          onMove={setPicked}
          replay={replay}
          onClose={() => setPicked(null)}
        />
      ) : null}
    </section>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-[5px]">
      <span className="size-[18px] rounded-[4px]" style={{ backgroundColor: color }} />
      <span className="text-[14px] leading-[1.45] text-subtext">{label}</span>
    </span>
  )
}

// --------------------------------------------------------------------------- //
// 페르소나
// --------------------------------------------------------------------------- //

/**
 * 페르소나 목록 — **이 사이트에서의 결과만.**
 *
 * 두 사이트를 나란히 놓는 표는 여기서 뺐다. 사용자는 주소 하나를 넣었으므로
 * 프로젝트 안에서 다른 사이트가 튀어나오면 "내가 넣지도 않은 게 왜 있지?"가 된다.
 * 견주는 일은 A/B 테스트(/ab)에서만 한다 — 데이터는 그대로 남아 있다.
 */
function PersonaView({ testId }: { testId: string }) {
  const runId = useRunId()
  const personas = useQuery(() => getTestPersonas(testId, undefined, runId), [testId, runId])
  // 재생 자료는 단계 상세와 같은 곳에서 온다. 표를 누르는 순간 받으면
  // 창이 빈 채로 먼저 뜬다.
  const steps = useQuery(() => getTestSteps(testId, undefined, runId), [testId, runId])
  const [replayId, setReplayId] = useState<string | null>(null)
  const label = usePersonaLabel()
  const replay = steps.data?.replay
  const playing = replayId ? replay?.[replayId] : null

  if (personas.loading) return <LoadingBlock label="페르소나를 불러오는 중이에요" />
  if (personas.error) return <ErrorBlock message={personas.error} onRetry={personas.reload} />

  const data = personas.data
  const items = data?.items ?? []
  if (items.length === 0) {
    return (
      <p className="py-[80px] text-center text-[15px] text-subtext">
        아직 만들어진 페르소나가 없어요.
      </p>
    )
  }

  const axes = data?.axes ?? {}
  const axisKeys = Object.keys(axes)

  return (
    <section className="mt-[16px]">
      <div className="flex flex-wrap items-center gap-[8px]">
        <Chip tone="plain">전체 {data?.total ?? items.length}명</Chip>
        <PersonaNameToggle />
        {(data?.exhausted ?? 0) > 0 ? (
          <Chip tone="hold">스텝 소진 {data?.exhausted}명</Chip>
        ) : null}
        <span className="ml-auto text-[13px] text-subtext">실행 · {data?.compare_run ?? '–'}</span>
      </div>

      <p className="mt-[12px] rounded-[12px] bg-bg px-[18px] py-[12px] text-[13px] text-subtext">
        {axisKeys.map((k) => axes[k]).join('·')}는 테스트 중 AI가 내부적으로 생성한 행동
        특성이며, 사용자가 직접 설정하는 값이 아니에요.
      </p>

      <div className="mt-[14px] overflow-x-auto rounded-[16px] border border-line">
        <table className="w-full min-w-[760px] border-collapse text-left">
          <thead>
            <tr className="bg-bg text-[13px] text-subtext">
              <th className="px-[18px] py-[12px] font-medium">페르소나</th>
              {axisKeys.map((k) => (
                <th key={k} className="px-[10px] py-[12px] font-medium whitespace-nowrap">
                  {axes[k]}
                </th>
              ))}
              <th className="px-[14px] py-[12px] font-medium whitespace-nowrap">결과</th>
            </tr>
          </thead>
          <tbody>
            {items.map((persona) => (
              <tr
                key={persona.id}
                onClick={() => replay?.[persona.code] && setReplayId(persona.code)}
                className={`border-t border-line text-[14px] ${
                  replay?.[persona.code] ? 'cursor-pointer hover:bg-black/[0.02]' : ''
                }`}
              >
                <td className="px-[18px] py-[12px]">
                  <div className="flex items-center gap-[10px]">
                    <PersonaFace id={persona.code} size={32} />
                    <div className="min-w-0">
                      <p className="font-semibold text-ink">{label(persona.code)}</p>
                      <p className="truncate text-[12px] text-subtext">
                        {persona.age_band_real && persona.gender_real
                          ? `${persona.age_band_real} · ${persona.gender_real}`
                          : persona.name}
                      </p>
                    </div>
                  </div>
                </td>
                {axisKeys.map((k) => (
                  <td key={k} className="px-[10px] py-[12px]">
                    <TraitDots value={persona.traits?.[k]} />
                  </td>
                ))}
                <td className="px-[14px] py-[12px]">
                  <SideResult side={persona.compare ?? null} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-[10px] text-[13px] text-subtext">
        줄을 누르면 그 사람의 여정을 처음부터 재생해요.
      </p>

      {playing ? (
        <PersonaReplayModal
          person={playing}
          others={Object.values(replay ?? {})}
          onPick={setReplayId}
          onClose={() => setReplayId(null)}
        />
      ) : null}
    </section>
  )
}

// --------------------------------------------------------------------------- //

/** 여정이 없으면 서버가 null 을 준다. 0.0% 라고 쓰면 '전부 실패'로 읽힌다. */
function pct(value: number | null): string {
  return value === null ? '–' : `${value}%`
}

function steps(value: number | null): string {
  return value === null ? '–' : `${value} step`
}

const TONE = {
  neutral: 'text-subtext',
  success: 'text-main',
  drop: 'text-drop',
} as const

function Stat({
  icon,
  value,
  label,
  tone = 'neutral',
  className = '',
  divider = false,
}: {
  icon: EmojiName
  value: string
  label: string
  tone?: keyof typeof TONE
  className?: string
  divider?: boolean
}) {
  return (
    <div className={`flex items-center ${className}`}>
      {divider ? <span className="mr-[52px] h-[160px] w-px shrink-0 bg-line" /> : null}
      <div className="flex flex-col gap-[3px]">
        <Emoji name={icon} size={40} />
        <strong className={`text-[30px] leading-[1.45] font-bold ${TONE[tone]}`}>{value}</strong>
        <span className="text-[16px] leading-[1.45] font-semibold whitespace-nowrap text-subtext">
          {label}
        </span>
      </div>
    </div>
  )
}
