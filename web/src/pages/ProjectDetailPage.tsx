import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getProject, listTests, type TestStats } from '../api/client'
import { useActiveRunPoll, useQuery } from '../api/hooks'
import iosArrowIcon from '../assets/icons/ios-arrow.svg'
import { AppLayout, PageBody } from '../components/AppLayout'
import { Button } from '../components/Button'
import { Emoji, type EmojiName } from '../components/Emoji'
import { RunProgressBanner } from '../components/RunProgressBanner'
import { SitePreview } from '../components/SitePreview'
import { ErrorBlock, LoadingBlock } from '../components/StateView'
import { Tabs } from '../components/Tabs'
import { timeAgo } from '../lib/time'
import { useWizard } from '../state/WizardContext'

const TABS = [
  { value: 'recent', label: '최근순' },
  { value: 'category', label: '카테고리별' },
] as const

export function ProjectDetailPage() {
  const { projectId = '' } = useParams()
  const navigate = useNavigate()
  const [tab, setTab] = useState<(typeof TABS)[number]['value']>('recent')
  const { resetTest } = useWizard()

  const project = useQuery(() => getProject(projectId), [projectId])
  const tests = useQuery(() => listTests(projectId), [projectId])
  const active = useActiveRunPoll()

  const running = active?.project_id === projectId ? active : null

  // 실행이 막 끝나면(진행중 → null) 배너가 사라지는데, 그 순간 방금 끝난
  // 테스트가 아래 목록에는 아직 없다 — 목록도 같이 다시 물어야 바로 나타난다.
  const wasRunning = useRef(false)
  useEffect(() => {
    if (running) {
      wasRunning.current = true
      return
    }
    if (wasRunning.current) {
      wasRunning.current = false
      tests.reload()
      project.reload()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running])

  if (project.loading) {
    return (
      <AppLayout>
        <PageBody>
          <LoadingBlock label="프로젝트를 불러오는 중이에요" />
        </PageBody>
      </AppLayout>
    )
  }

  if (project.error || !project.data) {
    return (
      <AppLayout>
        <PageBody>
          <ErrorBlock message={project.error ?? '프로젝트가 없어요'} onRetry={project.reload} />
        </PageBody>
      </AppLayout>
    )
  }

  const detail = project.data

  return (
    <AppLayout>
      <PageBody>
        <div className="mx-auto max-w-[1444px]">
          {running ? (
            <div className="mb-[40px]">
              <RunProgressBanner
                progress={{
                  projectName: running.project_name,
                  testName: running.test_name,
                  done: running.done,
                  total: running.total,
                  percent: running.percent,
                }}
                onOpen={() =>
                  navigate(`/projects/${running.project_id || projectId}/tests/new/running`)
                }
              />
            </div>
          ) : null}

          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-[48px] leading-[1.45] font-bold text-ink">{detail.name}</h1>
              <p className="mt-[9px] text-[16px] leading-[1.45] text-subtext">
                이 프로젝트에 대한 최근 테스트와 중요한 결과를 한눈에 확인해요.
              </p>
            </div>
            {/* 마법사 상태는 앱 전체가 하나를 쓴다. 새로 시작할 때 비워 주지 않으면
                앞선 테스트의 이름과 미션이 그대로 남는다. */}
            <Button
              onClick={() => {
                resetTest()
                navigate(`/projects/${projectId}/tests/new`)
              }}
              className="w-[230px]"
            >
              새 테스트 만들기
            </Button>
          </div>

          <div className="mt-[34px] flex gap-[217px]">
            <Stat icon="doc" value={`${detail.test_count}개`} label="진행한 테스트 수" />
            <Stat icon="target" value={pct(detail.success_rate)} label="평균 미션 성공률" tone="success" />
            <Stat icon="warning" value={pct(detail.drop_rate)} label="평균 이탈률" tone="drop" />
          </div>

          <Tabs tabs={TABS} value={tab} onChange={setTab} className="mt-[48px]" />

          <div className="mt-[39px] flex flex-col gap-[15px]">
            {tests.loading ? <LoadingBlock label="테스트를 불러오는 중이에요" /> : null}
            {tests.error ? <ErrorBlock message={tests.error} onRetry={tests.reload} /> : null}
            {!tests.loading && !tests.error && (tests.data?.length ?? 0) === 0 ? (
              <p className="py-[60px] text-center text-[15px] text-subtext">
                아직 진행한 테스트가 없어요. 새 테스트를 만들어 보세요.
              </p>
            ) : null}

            {(tests.data ?? []).map((test) => (
              <TestRow
                key={test.test_id}
                test={test}
                previewUrl={detail.preview_url}
                onOpen={() => navigate(`/projects/${projectId}/tests/${test.test_id}`)}
              />
            ))}
          </div>
        </div>
      </PageBody>
    </AppLayout>
  )
}

/** 여정이 없으면 서버가 null 을 준다. 0.0% 라고 쓰면 '전부 실패'로 읽힌다. */
function pct(value: number | null): string {
  return value === null ? '–' : `${value}%`
}

const TONE = {
  neutral: 'text-ink',
  success: 'text-main',
  drop: 'text-drop',
} as const

function Stat({
  icon,
  value,
  label,
  tone = 'neutral',
}: {
  icon: EmojiName
  value: string
  label: string
  tone?: keyof typeof TONE
}) {
  return (
    <div className="flex flex-col">
      <Emoji name={icon} size={40} />
      <strong className={`mt-[3px] text-[30px] leading-[1.45] font-bold ${TONE[tone]}`}>
        {value}
      </strong>
      <span className="mt-[5px] text-[16px] text-subtext">{label}</span>
    </div>
  )
}

function TestRow({
  test,
  previewUrl,
  onOpen,
}: {
  test: TestStats
  previewUrl: string | null
  onOpen: () => void
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex w-full items-center justify-between rounded-[14px] border border-line bg-white px-[30px] py-[20px] text-left transition-shadow hover:shadow-[0_6px_20px_rgba(0,0,0,0.06)]"
    >
      <div className="flex min-w-0 flex-1 items-end gap-[15px]">
        {/* 79×80 정사각형에 가까운 칸이다. 폭만 맞추면 웹 상단 띠만 보여 어색하므로
            확대해서 칸을 꽉 채우고 가운데를 보여준다. */}
        <div className="h-[80px] w-[79px] shrink-0 overflow-hidden rounded-[12px] border border-line">
          <SitePreview url={previewUrl} alt="" fit="cover" />
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-[9px] break-words">
          <p className="text-[20px] leading-[1.45] font-bold text-ink">{test.name}</p>
          <p className="text-[14px] leading-[1.45] text-subtext">페르소나 {test.persona_count}명</p>
          <p className="text-[14px] text-subtext">{timeAgo(test.created_at)}</p>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-[17px]">
        <div className="flex items-center gap-[8px]">
          <Metric icon="target" label="성공률" value={test.success_rate} />
          <Metric icon="warning" label="이탈률" value={test.drop_rate} />
        </div>
        <img src={iosArrowIcon} alt="" className="size-[40px] rotate-180" />
      </div>
    </button>
  )
}

function Metric({ icon, label, value }: { icon: EmojiName; label: string; value: number | null }) {
  return (
    <div className="flex items-center gap-[5px] rounded-full px-[6px] py-[5px]">
      <Emoji name={icon} size={30} />
      <span className="text-[20px] leading-[1.45] text-ink">{label}</span>
      {/* 행마다 자릿수가 달라 폭이 흔들리면 아이콘 세로줄이 어긋난다. 폭·자간을 고정한다. */}
      <span className="w-[70px] text-[20px] leading-[1.45] font-semibold text-ink tabular-nums">
        {pct(value)}
      </span>
    </div>
  )
}
