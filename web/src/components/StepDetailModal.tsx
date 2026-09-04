import { useEffect, useMemo, useRef, useState } from 'react'
import type {
  FilmFrame,
  PersonaReplay,
  StepClick,
  StepDetail,
  StepPersona,
} from '../api/client'
import { ClickHeatmap } from './ClickHeatmap'
import { PersonaFace, PersonaNameToggle, usePersonaLabel } from './PersonaIdentity'
import { ReplayStage } from './ReplayStage'

/**
 * 흐름도에서 막대 하나를 누르면 뜨는 창 (Figma 290:11203 / 290:11542).
 *
 * 왼쪽은 그 화면의 사진 위에 눌린 자리를 얹은 것, 오른쪽은 그 순간 그 자리에
 * 있던 사람들이다. 사람을 펼치면 그때 무슨 생각으로 그것을 눌렀는지가 나온다 —
 * 이 파이프라인이 다른 자동화 도구와 갈리는 지점이라 가장 크게 보여준다.
 *
 * 사진은 답사자가 찍어둔 화면 6종을 재사용한다. 페르소나마다 새로 찍지 않는 것이
 * 설계다(뒷사람은 글로만 움직인다). 좌표가 페이지 절대좌표라 그대로 포개진다.
 */

const SHOT_WIDTH = 640
const PLAY_MS = 1400

export function StepDetailModal({
  detail,
  filmstrip,
  sentences,
  axes,
  testName,
  onMove,
  replay,
  onClose,
}: {
  detail: StepDetail
  filmstrip: FilmFrame[]
  sentences: Record<string, Record<string, string>>
  axes: Record<string, string>
  testName: string
  /** 필름 띠의 다른 칸으로 옮긴다. */
  onMove: (id: string) => void
  /** 페르소나 id → 그 사람의 전체 여정. 주면 왼쪽을 재생으로 갈아끼울 수 있다. */
  replay?: Record<string, PersonaReplay>
  onClose: () => void
}) {
  const [open, setOpen] = useState<string | null>(null)
  const [picked, setPicked] = useState<StepClick | null>(null)
  const [playing, setPlaying] = useState(false)
  // 재생은 **이 창 안에서** 왼쪽만 바꾼다. 창을 하나 더 띄우면 오른쪽 패널이
  // 가려져서 "그 자리에 누가 또 있었나"를 같이 못 본다.
  const [replayId, setReplayId] = useState<string | null>(null)
  const strip = useRef<HTMLDivElement>(null)

  const at = filmstrip.findIndex((f) => f.id === detail.id)
  const here = at >= 0 ? at : filmstrip.findIndex((f) => f.step === detail.step)
  const prev = here > 0 ? filmstrip[here - 1] : null
  const next = here >= 0 && here < filmstrip.length - 1 ? filmstrip[here + 1] : null

  // 창이 바뀌면 펼쳐둔 사람과 짚어둔 클릭을 놓는다. 남겨두면 다음 단계에
  // 있지도 않은 사람이 펼쳐진 채로 보인다.
  useEffect(() => {
    setOpen(null)
    setPicked(null)
    setReplayId(null)
  }, [detail.id])

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowLeft' && prev) onMove(prev.id)
      if (e.key === 'ArrowRight' && next) onMove(next.id)
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [onClose, onMove, prev, next])

  // 자동재생. 마지막 칸에 닿으면 스스로 멈춘다 — 처음으로 되감으면 어디까지
  // 봤는지 알 수 없게 된다.
  useEffect(() => {
    if (!playing) return
    if (!next) {
      setPlaying(false)
      return
    }
    const timer = window.setTimeout(() => onMove(next.id), PLAY_MS)
    return () => window.clearTimeout(timer)
  }, [playing, next, onMove])

  // 현재 칸이 항상 띠 안에 보이도록 따라 움직인다.
  useEffect(() => {
    strip.current?.querySelector('[data-here="1"]')?.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
      inline: 'center',
    })
  }, [detail.id])

  const landed = detail.clicks.length - detail.wasted
  const replaying = replayId ? replay?.[replayId] : null

  // 같은 단계의 다른 화면으로 건너뛴다. 막대 id 는 'c{열}:{화면}' 규칙이라
  // 열 번호를 그대로 쓰고 화면만 갈아 끼우면 된다.
  const jumpTo = (screen: string) => onMove(`c${detail.step - 1}:${screen}`)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-[24px]"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`${detail.step}단계 ${detail.title} 상세`}
        className="flex max-h-full w-full max-w-[1320px] flex-col overflow-hidden rounded-[18px] bg-white shadow-[0_24px_70px_rgba(0,0,0,0.28)]"
      >
        <header className="flex items-start justify-between border-b border-line px-[28px] py-[20px]">
          <div>
            <h2 className="text-[20px] leading-[1.4] font-bold text-heading">
              {testName} / {detail.step}단계 · {detail.title}
            </h2>
            <p className="mt-[6px] flex flex-wrap items-center gap-x-[16px] gap-y-[4px] text-[14px] text-subtext">
              <span>{detail.count}명이 이 자리에 있었어요</span>
              {detail.clicks.length > 0 ? (
                <span>
                  이 단계 조작 {detail.clicks.length}회 —{' '}
                  <span className="text-[#00824f]">반응함 {landed}</span> ·{' '}
                  <span className="text-[#df2d48]">헛클릭 {detail.wasted}</span>
                </span>
              ) : null}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-[8px]">
            <Round label="이전 단계" disabled={!prev} onClick={() => prev && onMove(prev.id)}>
              &lsaquo;
            </Round>
            <Round label="다음 단계" disabled={!next} onClick={() => next && onMove(next.id)}>
              &rsaquo;
            </Round>
            <Round label="닫기" onClick={onClose}>
              &times;
            </Round>
          </div>
        </header>

        <div className="flex min-h-0 flex-1">
          {/* 왼쪽 — 화면 사진 + 눌린 자리. 재생 중이면 그 자리에 무대가 들어온다. */}
          <div className="flex min-w-0 flex-1 flex-col border-r border-line">
            {replaying ? (
              <ReplayStage
                person={replaying}
                width={SHOT_WIDTH}
                onExit={() => setReplayId(null)}
              />
            ) : (
            <>
            <div className="flex-1 overflow-auto bg-[#f6f7f9] p-[24px]">
              <div className="mx-auto w-fit">
                {detail.shot ? (
                  <ClickHeatmap
                    shot={detail.shot}
                    clicks={detail.clicks}
                    background={detail.screen_clicks}
                    width={SHOT_WIDTH}
                    picked={picked}
                    onPick={(c) => {
                      setPicked(c)
                      setOpen(c ? c.persona : null)
                    }}
                  />
                ) : (
                  <p className="py-[80px] text-center text-[14px] text-subtext">
                    이 화면은 답사자가 찍어둔 사진이 없어요.
                  </p>
                )}
              </div>
            </div>

            <div className="border-t border-line px-[20px] py-[12px]">
              <p className="mb-[8px] text-[12px] text-subtext">
                옅은 색은 이 화면에서 벌어진 조작 전부({detail.screen_clicks.length}회),
                테두리는 이 단계의 조작이에요. 붉은 것은 눌러도 아무 일이 없었던 자리입니다.
              </p>
              <div ref={strip} className="flex gap-[10px] overflow-x-auto pb-[6px]">
                {filmstrip.map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    data-here={f.id === detail.id ? '1' : undefined}
                    onClick={() => onMove(f.id)}
                    className={`shrink-0 rounded-[8px] border p-[4px] text-left transition-colors ${
                      f.id === detail.id
                        ? 'border-main bg-main/5'
                        : 'border-line hover:border-subtext'
                    }`}
                  >
                    <span className="block text-[11px] font-semibold text-heading tabular-nums">
                      {f.step}단계
                    </span>
                    {f.shot ? (
                      <img
                        src={f.shot.src}
                        alt=""
                        className="mt-[3px] h-[52px] w-[84px] rounded-[4px] object-cover object-top"
                      />
                    ) : null}
                    <span className="mt-[3px] block max-w-[84px] truncate text-[10px] text-subtext">
                      {f.title} {f.count}명
                    </span>
                  </button>
                ))}
              </div>
              <div className="mt-[10px] flex items-center gap-[12px]">
                <button
                  type="button"
                  onClick={() => setPlaying((v) => !v)}
                  disabled={!next && !playing}
                  className="flex h-[30px] items-center gap-[6px] rounded-[8px] bg-main px-[12px] text-[12px] font-semibold text-white disabled:opacity-40"
                >
                  {playing ? '❚❚ 멈춤' : '▶ 자동재생'}
                </button>
                <div className="h-[6px] flex-1 overflow-hidden rounded-[3px] bg-track">
                  <div
                    className="h-full rounded-[3px] bg-main transition-[width] duration-300"
                    style={{
                      width: `${filmstrip.length ? ((here + 1) / filmstrip.length) * 100 : 0}%`,
                    }}
                  />
                </div>
                <span className="text-[12px] text-subtext tabular-nums">
                  {here + 1} / {filmstrip.length}
                </span>
              </div>
            </div>
            </>
            )}
          </div>

          {/* 오른쪽 — 이 단계에 열 명이 각각 무엇을 하고 있었나.
              세 무리로 나뉜다: 이 화면 · 같은 단계의 다른 화면 · 이미 끝난 사람.
              셋을 더하면 언제나 전체 인원이다. 이 화면에 있던 사람만 보여주면
              "10단계에 왜 네 명뿐이지?" 하고 나머지 여섯을 잃어버린다. */}
          <aside className="flex w-[400px] shrink-0 flex-col">
            <div className="flex items-center gap-[10px] border-b border-line px-[20px] py-[13px]">
              <span className="text-[15px] font-bold text-heading">화면 정보</span>
              <span className="text-[13px] text-subtext">
                <span aria-hidden>👤</span> {detail.total}
              </span>
              <span className="text-[13px] text-subtext">
                <span aria-hidden>≡</span> {detail.personas.length}
              </span>
              <span className="ml-auto">
                <PersonaNameToggle />
              </span>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              {detail.personas.map((p) => (
                <PersonaCard
                  key={p.id}
                  person={p}
                  step={detail.step}
                  axes={axes}
                  sentences={sentences}
                  open={open === p.id}
                  onReplay={replay ? setReplayId : undefined}
                  onToggle={() => {
                    const nextOpen = open === p.id ? null : p.id
                    setOpen(nextOpen)
                    setPicked(
                      nextOpen ? (detail.clicks.find((c) => c.persona === p.id) ?? null) : null,
                    )
                  }}
                />
              ))}

              {detail.elsewhere.length > 0 ? (
                <GroupLabel>같은 단계, 다른 화면에 있던 {detail.elsewhere.length}명</GroupLabel>
              ) : null}
              {detail.elsewhere.map((p) => (
                <PersonaCard
                  key={p.id}
                  person={p}
                  step={detail.step}
                  axes={axes}
                  sentences={sentences}
                  open={open === p.id}
                  onReplay={replay ? setReplayId : undefined}
                  onToggle={() => setOpen(open === p.id ? null : p.id)}
                  onJump={p.screen ? () => jumpTo(p.screen as string) : undefined}
                />
              ))}

              {detail.finished.length > 0 ? (
                <GroupLabel>{detail.step}단계 전에 이미 끝난 {detail.finished.length}명</GroupLabel>
              ) : null}
              {detail.finished.map((p) => (
                <PersonaCard
                  key={p.id}
                  person={p}
                  step={detail.step}
                  axes={axes}
                  sentences={sentences}
                  open={open === p.id}
                  onReplay={replay ? setReplayId : undefined}
                  onToggle={() => setOpen(open === p.id ? null : p.id)}
                  ended
                />
              ))}
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}

function Round({
  children,
  label,
  onClick,
  disabled,
}: {
  children: React.ReactNode
  label: string
  onClick: () => void
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className="flex size-[30px] items-center justify-center rounded-[8px] border border-line text-[16px] leading-none text-heading transition-colors hover:bg-black/[0.04] disabled:opacity-30"
    >
      {children}
    </button>
  )
}

const OUTCOME: Record<string, string> = {
  success: 'text-[#00824f]',
  drop: 'text-[#df2d48]',
}

/** 기록의 조작 이름을 사람 말로. 없는 것은 그대로 둔다. */
const ACTION: Record<string, string> = {
  click: '누름',
  type: '입력',
  select: '선택',
  scroll: '스크롤',
  goto: '주소로 이동',
  give_up: '포기',
  wait: '기다림',
}

function GroupLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="border-y border-line bg-[#f6f7f9] px-[20px] py-[8px] text-[12px] font-semibold text-subtext">
      {children}
    </p>
  )
}

function PersonaCard({
  person,
  step,
  axes,
  sentences,
  open,
  onToggle,
  onJump,
  onReplay,
  ended,
}: {
  person: StepPersona
  step: number
  axes: Record<string, string>
  sentences: Record<string, Record<string, string>>
  open: boolean
  onToggle: () => void
  /** 이 사람이 있던 화면으로 창을 옮긴다. 같은 단계의 다른 화면일 때만 준다. */
  onJump?: () => void
  /** 이 사람의 여정 전체를 재생한다. */
  onReplay?: (personaId: string) => void
  /** 이 단계에 이미 끝나 있던 사람. 그 순간의 조작이 없다. */
  ended?: boolean
}) {
  // 성격 문장은 페르소나 규격의 원문이다. 화면이 지어낸 문장이 아니다.
  const label = usePersonaLabel()
  const character = useMemo(
    () =>
      Object.keys(axes)
        .map((axis) => sentences[axis]?.[String(person.traits[axis])])
        .filter(Boolean)
        .join(' '),
    [axes, sentences, person.traits],
  )

  return (
    <div className={`border-b border-line ${open ? 'bg-main/[0.04]' : ''} ${ended ? 'opacity-70' : ''}`}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-[12px] px-[20px] py-[14px] text-left transition-colors hover:bg-black/[0.02]"
      >
        <PersonaFace id={person.code} />
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-[6px] text-[15px] font-semibold text-heading">
            {label(person.code)}
            {/* 어느 화면에 있었는지를 이름 옆에 붙여야 "10단계에 이 사람은
                주문/결제에 있었구나"가 한눈에 읽힌다. */}
            {person.screen_title ? (
              <span className="rounded-[5px] border border-line px-[5px] py-[1px] text-[11px] font-normal text-subtext">
                {person.screen_title}
              </span>
            ) : null}
          </span>
          <span className="block truncate text-[12px] text-subtext">
            {person.age_band && person.gender
              ? `${person.age_band} · ${person.gender}`
              : person.label}
          </span>
        </span>
        <span className="shrink-0 text-right">
          <span className={`block text-[14px] font-semibold ${OUTCOME[person.outcome] ?? ''}`}>
            {person.end_label}
          </span>
          <span className="block text-[12px] text-subtext tabular-nums">
            {person.total_steps} Step
          </span>
        </span>
        <span className="shrink-0 text-[15px] text-subtext">{open ? '⌃' : '›'}</span>
      </button>

      {open ? (
        <div className="px-[20px] pb-[16px]">
          <p className="text-[12px] font-semibold text-subtext">성격</p>
          <p className="mt-[4px] text-[13px] leading-[1.6] text-body">{character}</p>

          <div className="mt-[12px] flex items-baseline justify-between">
            <p className="text-[12px] font-semibold text-subtext">
              AI 에이전트 실시간 내면 독백
            </p>
            <p className="text-[12px] text-subtext tabular-nums">
              {ended ? `마지막 · Step ${person.total_steps}` : `Step ${step}`}
            </p>
          </div>
          <blockquote className="mt-[6px] rounded-[10px] border border-main/30 bg-white px-[14px] py-[12px] text-[13px] leading-[1.65] text-body">
            “{person.thought}”
          </blockquote>
          {ended ? (
            <p className="mt-[8px] text-[12px] text-subtext">
              {person.total_steps}스텝에서 {person.end_label} — 이 단계에는 이미 없었어요.
            </p>
          ) : person.target || person.action ? (
            <p className="mt-[8px] text-[12px] text-subtext">
              {ACTION[person.action] ?? person.action}
              {person.target ? <span className="text-body"> · {person.target}</span> : null}
              {person.blocked ? ' · 규칙에 막혀 못 한 조작이 있었어요' : ''}
            </p>
          ) : null}
          <div className="mt-[10px] flex flex-wrap items-center gap-[14px]">
            {onReplay ? (
              // 이 창은 '이 순간'을 가로로 본다. 한 사람이 어디서 헤맸는지는
              // 그 사람의 스텝을 이어서 봐야 보이므로 재생으로 넘긴다.
              <button
                type="button"
                onClick={() => onReplay(person.code)}
                className="rounded-[8px] bg-main px-[12px] py-[6px] text-[12px] font-semibold text-white"
              >
                ▶ 이 사람 여정 재생
              </button>
            ) : null}
            {onJump ? (
              <button
                type="button"
                onClick={onJump}
                className="text-[12px] font-semibold text-main underline underline-offset-4"
              >
                {person.screen_title} 화면으로 보기 →
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}
