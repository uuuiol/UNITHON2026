import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getActiveRun, getProject, type ActiveRun } from '../api/client'
import { useQuery } from '../api/hooks'
import arrowIcon from '../assets/icons/arrow.svg'
import { AppLayout, PageBody } from '../components/AppLayout'
import { WizardTopBar } from '../components/StepIndicator'
import { estimateRun } from '../lib/estimate'
import { useWizard } from '../state/WizardContext'

/** 진행 상황을 얼마나 자주 다시 물을지. 파이프라인이 여정을 채우는 속도 기준. */
const POLL_MS = 3000

/** 재생 중 눈금 갱신 주기. 값이 시간에서 나오므로 촘촘히 물어야 부드럽다. */
const REPLAY_POLL_MS = 400

export function RunningPage() {
  const { projectId = '' } = useParams()
  const navigate = useNavigate()
  const { testName } = useWizard()

  const project = useQuery(() => getProject(projectId), [projectId])
  const [run, setRun] = useState<ActiveRun | null>(null)
  const replaying = run?.replay ?? false
  // 서버는 "도는 중"인 실행만 돌려준다 — A/B 두 arm이 모두 done 이 되는
  // 순간 /api/runs/active 는 null 로 뒤집힌다. 그걸 그대로 반영하면
  // done/total 이 0/0 이 되어 진행바가 100% 문턱에서 0%로 되감긴 것처럼
  // 보이고, 완료 판정(percent>=100)도 영영 안 걸려 화면이 멈춰 선다.
  // 그래서 마지막으로 본 실행을 기억해 뒀다가, null 로 바뀌면 그걸 100%로
  // 마무리해 넘겨준다.
  const lastRunRef = useRef<ActiveRun | null>(null)

  useEffect(() => {
    let alive = true

    const tick = async () => {
      try {
        const next = await getActiveRun()
        if (!alive) return
        if (next) {
          lastRunRef.current = next
          setRun(next)
          return
        }
        const last = lastRunRef.current
        if (last?.test_id) {
          setRun({ ...last, percent: 100, done: last.total || last.done })
        }
      } catch {
        // 폴링 실패는 화면을 깨뜨리지 않는다. 다음 주기에 다시 시도한다.
      }
    }

    void tick()
    // 재생 중에는 눈금이 초 단위로 움직인다. 3초마다 물으면 막대가 뚝뚝 끊긴다.
    const timer = window.setInterval(tick, replaying ? REPLAY_POLL_MS : POLL_MS)
    return () => {
      alive = false
      window.clearInterval(timer)
    }
  }, [replaying])

  // 다 돌면 결과로 데려간다. 100% 에서 멈춰 선 막대를 계속 보여줄 이유가 없다.
  //
  // 한 번만 건다. run 객체는 폴링마다 새로 오는데 그것을 의존성에 걸면
  // 타이머가 매번 지워졌다 다시 걸려서 **영영 터지지 않는다.**
  const sent = useRef(false)
  useEffect(() => {
    if (sent.current || !run || (run.percent ?? 0) < 100 || !run.test_id) return
    sent.current = true
    // 로컬에서 진짜로 돌렸으면 그 실행의 기록을 읽으라고 알려준다. 안 붙이면
    // 방금 30명을 돌리고도 화면에는 번들된 예전 기록이 뜬다.
    const q = run.run_log ? `?run=${encodeURIComponent(run.run_log)}` : ''
    const to = `/projects/${run.project_id || projectId}/tests/${run.test_id}${q}`
    // 정리 함수를 두지 않는다. 폴링이 run 을 새로 물어올 때마다 정리가 돌아
    // 타이머를 지우는데, sent 가 막아서 새 타이머는 걸리지 않는다 — 그러면
    // 100% 에 도달하고도 영영 넘어가지 않는다. 중복은 sent 하나로 막는다.
    window.setTimeout(() => navigate(to), 900)
  }, [run, navigate, projectId])

  const done = run?.done ?? 0
  const total = run?.total ?? 0
  // 서버가 계산해 주면 그것을 쓴다. 답사 단계에도 눈금이 오르기 때문이다 —
  // done/total 로만 세면 답사 2분 동안 0% 에 멈춰 있어 죽은 것처럼 보인다.
  const percent = run?.percent ?? (total > 0 ? Math.round((done / total) * 100) : 0)
  const name = run?.test_name ?? testName
  const projectName = run?.project_name ?? project.data?.name ?? ''

  // 남은 시간 = 전체 예상 시간 × 남은 비율. 실측이 아니라 공식이라 '예상'을 붙인다.
  const remaining = total > 0 ? Math.max(0, Math.round(estimateRun(total).minutes * (1 - done / total))) : null

  return (
    <AppLayout
      topBar={<WizardTopBar breadcrumb={{ project: projectName, page: name }} current={4} />}
    >
      <PageBody className="pt-[56px]">
        <div className="mx-auto flex max-w-[1402px] flex-col items-center">
          <LoadingRing />

          <p className="mt-[32px] flex items-baseline gap-[8px] whitespace-nowrap">
            <span className="text-[24px] leading-[1.45] font-bold text-ink">
              {projectName} / {name}
            </span>
            <span className="text-[20px] leading-[1.45] text-ink">
              {run ? '진행중' : '대기중'}
            </span>
          </p>

          {/* 배포본에는 파이프라인이 붙어 있지 않다. 지금 새로 도는 것처럼
              보이게 두면 없는 실행을 지어내는 것이라서, 재생 중이라고 적는다. */}
          {replaying ? (
            <p className="mt-[10px] text-[14px] text-subtext">
              이미 돌려 둔 실행을 다시 재생하고 있어요. 인원과 결과는 그때 기록 그대로예요.
            </p>
          ) : null}

          <div className="mt-[28px] w-full">
            <p className="text-[36px] leading-[1.45] font-bold text-ink tabular-nums">{percent}%</p>
            <div
              role="progressbar"
              aria-valuenow={percent}
              aria-valuemin={0}
              aria-valuemax={100}
              className="mt-[12px] h-[14px] w-full overflow-hidden rounded-[7px] bg-track"
            >
              <div
                className="h-full rounded-[7px] bg-main transition-[width] duration-500"
                style={{ width: `${percent}%` }}
              />
            </div>
            <div className="mt-[22px] flex justify-end gap-[38px] text-[15px] text-subtext">
              <span>
                {done} / {total}명이 테스트를 마쳤어요
              </span>
              {/* 재생 중에는 남은 시간을 적지 않는다. 공식이 낸 "63분"이
                  20초 만에 끝나는 막대 옆에 붙으면 고장 난 것처럼 보인다. */}
              {remaining !== null && !replaying ? <span>예상 {remaining}분 남음</span> : null}
            </div>
          </div>

          <button
            type="button"
            onClick={() => navigate(`/projects/${projectId}`)}
            className="mt-[44px] flex h-[76px] w-[316px] items-center justify-center gap-[10px] rounded-[16px] border border-ink bg-white text-[24px] leading-[1.45] font-bold text-ink transition-colors hover:bg-black/[0.03]"
          >
            프로젝트로 돌아가기
            <img src={arrowIcon} alt="" aria-hidden className="size-[15px] invert" />
          </button>

          {/* [빠짐] 답사자가 본 화면 링크는 원래 로컬 개발 중 agent-ux/server.py를
              띄워 두고 보는 임시 통로였다 — 그 스크린샷 서버는 AWS 배포본에는
              애초에 붙어 있지 않다(진짜 실행은 orchestrate.py가 다른 경로로
              돌린다). 안 쓰는 링크를 남겨 두면 눌렀을 때 404만 본다 — 실제로
              보여줄 화면이 생기면 그때 다시 연결한다. */}
        </div>
      </PageBody>
    </AppLayout>
  )
}

// 디자인은 1920×1080 기준 395px. 노트북 높이에서 스크롤이 생기지 않도록 줄였다.
const RING_SIZE = 300
const RING_STROKE = 14

/**
 * 무한 회전 로딩 링.
 *
 * 진행률은 아래 진행바가 이미 정확히 보여준다. 이 링은 "지금 돌고 있다"만 말하는
 * 장식이라 값과 묶지 않는다 — 값에 묶으면 68%에서 멈춰 선 것처럼 보인다.
 */
function LoadingRing() {
  const radius = (RING_SIZE - RING_STROKE) / 2

  return (
    <svg
      width={RING_SIZE}
      height={RING_SIZE}
      viewBox={`0 0 ${RING_SIZE} ${RING_SIZE}`}
      role="status"
      aria-label="테스트 진행중"
      className="loading-ring"
    >
      <circle
        cx={RING_SIZE / 2}
        cy={RING_SIZE / 2}
        r={radius}
        fill="none"
        stroke="var(--color-track)"
        strokeWidth={RING_STROKE}
      />
      <circle
        className="loading-ring__arc"
        cx={RING_SIZE / 2}
        cy={RING_SIZE / 2}
        r={radius}
        fill="none"
        stroke="var(--color-main)"
        strokeOpacity={0.45}
        strokeWidth={RING_STROKE}
        strokeLinecap="round"
      />
    </svg>
  )
}
