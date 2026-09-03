import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  getAbTest,
  type AbResult,
  type PersonaRow,
  type PersonaSideResult,
  type StepsPayload,
} from '../api/client'
import { useQuery } from '../api/hooks'
import backArrow from '../assets/icons/back-arrow.svg'
import { Icon } from '../components/Icon'
import { NavigationDiagram } from '../components/NavigationDiagram'
import { StepDetailModal } from '../components/StepDetailModal'
import { Chip, TraitDots } from '../components/PersonaBits'
import { PersonaCompareTable } from '../components/PersonaCompareTable'
import { ErrorBlock, LoadingBlock } from '../components/StateView'

/**
 * A/B 테스트 결과 (Figma 329:24937 · 290:10341).
 *
 * 위는 같은 페르소나가 두 사이트에서 어떻게 갈렸는지 보여주는 표,
 * 아래는 각 사이트의 이동 흐름이다. 흐름을 한 장만 그리면 "어디서 갈렸나"를
 * 눈으로 대조할 수 없어서 두 장을 위아래로 놓는다.
 */
export function AbResultPage() {
  const { abId = '' } = useParams()
  const navigate = useNavigate()
  const result = useQuery(() => getAbTest(abId), [abId])
  const [picked, setPicked] = useState<PersonaRow | null>(null)

  const data = result.data

  return (
    <div className="flex h-full min-h-screen flex-col bg-bg">
      <header className="flex h-[70px] shrink-0 items-center gap-[12px] border-b border-line bg-white pr-[40px] pl-[30px]">
        <button
          type="button"
          onClick={() => navigate('/ab')}
          aria-label="A/B 테스트 목록으로"
          className="shrink-0"
        >
          <img src={backArrow} alt="" className="size-[30px] rotate-180" />
        </button>
        <p className="flex items-center gap-[6px] leading-[1.45] whitespace-nowrap">
          <span className="text-[20px] font-semibold text-heading">{data?.name ?? ''}</span>
          <span className="text-[15px] text-subtext">{data?.mission ?? ''}</span>
        </p>
      </header>

      <div className="flex min-h-0 flex-1">
        <main className="min-h-0 flex-1 overflow-y-auto px-[40px] py-[40px]">
          {result.loading ? <LoadingBlock label="비교 결과를 불러오는 중이에요" /> : null}
          {result.error ? <ErrorBlock message={result.error} onRetry={result.reload} /> : null}

          {data ? (
            <div className="mx-auto w-full max-w-[1573px]">
              <section className="rounded-[16px] border border-line bg-white px-[27px] pt-[32px] pb-[34px]">
                <h1 className="text-[24px] leading-[1.45] font-bold text-heading">
                  페르소나별 결과 비교
                </h1>
                <p className="mt-[8px] text-[14px] text-subtext">
                  같은 페르소나가 같은 미션을 수행했을 때 사이트별 결과가 어떻게 달라졌는지
                  확인해요.
                </p>

                <div className="mt-[20px]">
                  {data.compare.ok ? (
                    <PersonaCompareTable
                      data={data.compare}
                      baseName={data.a.name}
                      againstName={data.b.name}
                      baseRate={data.a.success_rate}
                      againstRate={data.b.success_rate}
                      onPick={setPicked}
                      selectedId={picked?.id ?? null}
                    />
                  ) : (
                    <p className="rounded-[12px] bg-bg px-[18px] py-[14px] text-[14px] text-subtext">
                      {data.compare.message}
                    </p>
                  )}
                </div>
              </section>

              <DiagramBlock tag="A" side={data.a} diagram={data.diagrams.a}
                            steps={data.steps?.a ?? null} />
              <DiagramBlock tag="B" side={data.b} diagram={data.diagrams.b}
                            steps={data.steps?.b ?? null} />
            </div>
          ) : null}
        </main>

        {picked && data ? (
          <PersonaPanel persona={picked} result={data} onClose={() => setPicked(null)} />
        ) : null}
      </div>
    </div>
  )
}

function DiagramBlock({
  tag,
  side,
  diagram,
  steps,
}: {
  tag: 'A' | 'B'
  side: AbResult['a']
  diagram: AbResult['diagrams']['a']
  /** 없으면 막대를 눌러도 아무 일이 없다. 그럴 때는 누를 수 있는 척하지 않는다. */
  steps: StepsPayload | null
}) {
  // 테스트 상세 화면과 같은 창을 띄운다. A/B 는 흐름도가 두 장일 뿐,
  // 막대 하나를 눌렀을 때 보고 싶은 것은 똑같다.
  const [picked, setPicked] = useState<string | null>(null)
  const detail = picked ? steps?.steps[picked] : null

  return (
    <section className="mt-[34px]">
      <h2 className="text-[22px] leading-[1.45] font-bold text-heading">
        프로젝트 {tag} · {side.name}
      </h2>
      <p className="mt-[6px] text-[14px] text-subtext">
        AI 페르소나가 실제로 이동한 경로와 미션 완료 방식을 확인해요.
      </p>

      <div className="mt-[16px] rounded-[16px] border border-line bg-white px-[24px] pt-[22px] pb-[24px]">
        <h3 className="text-[20px] leading-[1.45] font-bold text-heading">
          네비게이션 다이어그램 뷰
        </h3>
        <div className="mt-[6px] flex items-center gap-[12px]">
          <Legend color="#00824f" label="성공" />
          <Legend color="#df2d48" label="실패" />
        </div>
        <div className="mt-[24px]">
          {diagram ? (
            <NavigationDiagram
              data={diagram}
              onPickNode={
                steps
                  ? (id) => {
                      if (steps.steps[id]) setPicked(id)
                    }
                  : undefined
              }
            />
          ) : (
            <p className="py-[60px] text-center text-[15px] text-subtext">
              이 사이트의 이동 기록이 아직 없어요.
            </p>
          )}
        </div>
      </div>

      {detail && steps ? (
        <StepDetailModal
          detail={detail}
          filmstrip={steps.filmstrip}
          sentences={steps.sentences}
          axes={steps.axes}
          testName={`${side.name} · ${steps.test_name}`}
          replay={steps.replay}
          onMove={setPicked}
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
// 페르소나 한 명 상세 (Figma 290:10341)
// --------------------------------------------------------------------------- //

function PersonaPanel({
  persona,
  result,
  onClose,
}: {
  persona: PersonaRow
  result: AbResult
  onClose: () => void
}) {
  const axes = result.compare.ok ? (result.compare.axes ?? {}) : {}
  const axisKeys = Object.keys(axes)

  return (
    <aside className="w-[420px] shrink-0 overflow-y-auto border-l border-line bg-white px-[28px] py-[26px]">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-[20px] font-bold text-heading">
            {persona.code} · {persona.name}
          </h2>
          <p className="mt-[8px] text-[13px] text-muted">
            동일한 페르소나가 두 사이트에서 다른 결과를 보여줬어요.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-[10px]">
          {persona.changed ? <Chip tone="warn">결과 변화</Chip> : null}
          <button
            type="button"
            onClick={onClose}
            aria-label="닫기"
            className="text-[18px] leading-none text-subtext hover:text-ink"
          >
            ×
          </button>
        </div>
      </div>

      {axisKeys.length > 0 ? (
        <>
          <h3 className="mt-[26px] text-[15px] font-bold text-heading">테스트 중 생성된 행동 특성</h3>
          <p className="mt-[6px] text-[12px] text-muted">
            사용자가 설정한 값이 아니라 조건과 별개로 AI가 만든 내부 행동 값이에요.
          </p>
          <dl className="mt-[16px] grid grid-cols-2 gap-x-[20px] gap-y-[14px]">
            {axisKeys.map((key) => (
              <div key={key} className="flex items-center justify-between gap-[10px]">
                <dt className="text-[12px] text-muted">{axes[key]}</dt>
                <dd>
                  <TraitDots value={persona.traits?.[key]} />
                </dd>
              </div>
            ))}
          </dl>
        </>
      ) : null}

      <div className="mt-[24px] grid grid-cols-2 gap-[14px]">
        <SideBox label="기준 사이트" name={result.a.name} side={persona.baseline ?? null} />
        <SideBox label="비교 사이트" name={result.b.name} side={persona.compare ?? null} />
      </div>

      {persona.changed ? (
        <div className="mt-[20px] rounded-[12px] bg-[#fff6f5] px-[16px] py-[14px]">
          <p className="text-[13px] font-bold text-heading">같은 목표·같은 사람인데 결과가 달라졌어요</p>
          <p className="mt-[6px] text-[12px] leading-[1.6] text-muted">
            행동 특성은 유지되므로 두 사이트의 UI·상태 차이를 우선 검토할 수 있어요.
          </p>
        </div>
      ) : null}

      <h3 className="mt-[26px] text-[15px] font-bold text-heading">행동 경로 비교</h3>
      <PathLine label="기준 사이트" side={persona.baseline ?? null} />
      <PathLine label="비교 사이트" side={persona.compare ?? null} />

      <div className="mt-[24px] rounded-[12px] bg-bg px-[16px] py-[14px]">
        <p className="text-[13px] font-bold text-heading">분석 시 확인할 점</p>
        <ul className="mt-[8px] flex flex-col gap-[6px] text-[12px] leading-[1.6] text-muted">
          <li>· 어느 화면부터 이동 경로가 달라졌는지</li>
          <li>· 실패 사이트에서 반복 클릭·되돌기가 스텝 소진이 발생했는지</li>
          <li>· 동일 특성의 다른 페르소나에서도 같은 차이가 반복되는지</li>
        </ul>
      </div>
    </aside>
  )
}

function SideBox({
  label,
  name,
  side,
}: {
  label: string
  name: string
  side: PersonaSideResult | null
}) {
  const success = side?.outcome === 'success'
  return (
    <div className="rounded-[12px] border border-line px-[14px] py-[13px]">
      <p className="text-[11px] text-muted">{label}</p>
      <p className="mt-[5px] truncate text-[14px] font-semibold text-heading">{name}</p>
      <div className="mt-[10px] flex items-center gap-[8px]">
        <span
          className={`rounded-[6px] px-[8px] py-[3px] text-[12px] font-semibold ${
            success ? 'bg-ok-bg text-ok' : 'bg-[#fdeced] text-danger'
          }`}
        >
          {side?.end_label ?? '기록 없음'}
        </span>
        <span className="text-[13px] font-semibold text-heading tabular-nums">
          {side?.step_count === null || side === null ? '–' : `${side.step_count} step`}
        </span>
      </div>
    </div>
  )
}

/** 경로를 화면 이름의 줄로 편다. 기록이 없으면 그 사실을 말한다. */
function PathLine({ label, side }: { label: string; side: PersonaSideResult | null }) {
  const screens = side?.screens ?? []
  return (
    <div className="mt-[14px]">
      <p className="text-[12px] text-muted">{label}</p>
      {screens.length === 0 ? (
        <p className="mt-[7px] text-[12px] text-subtext">이동 기록이 없어요.</p>
      ) : (
        <div className="mt-[7px] flex flex-wrap items-center gap-[6px]">
          {screens.map((screen, index) => (
            <span key={`${screen}-${index}`} className="flex items-center gap-[6px]">
              {index > 0 ? <Icon name="arrowUp2" size={16} className="rotate-90 text-subtext" /> : null}
              <span
                className={`rounded-[8px] px-[10px] py-[5px] text-[12px] font-medium ${
                  index === screens.length - 1
                    ? side?.outcome === 'success'
                      ? 'bg-main text-white'
                      : 'bg-[#fdeced] text-danger'
                    : 'bg-track text-body'
                }`}
              >
                {screen}
              </span>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
