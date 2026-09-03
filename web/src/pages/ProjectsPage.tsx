import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { deleteProject, listProjects, type ProjectCard } from '../api/client'
import { useActiveRunPoll, useQuery } from '../api/hooks'
import moreIcon from '../assets/icons/more.svg'
import { AppLayout, PageBody, PageHeading } from '../components/AppLayout'
import { Button } from '../components/Button'
import { EmptyProjects } from '../components/EmptyProjects'
import { RunProgressBanner } from '../components/RunProgressBanner'
import { SitePreview } from '../components/SitePreview'
import { ErrorBlock, LoadingBlock } from '../components/StateView'
import { Tabs } from '../components/Tabs'
import { timeAgo } from '../lib/time'

const TABS = [
  { value: 'recent', label: '최근순' },
  { value: 'category', label: '카테고리별' },
] as const

type TabValue = (typeof TABS)[number]['value']

export function ProjectsPage() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<TabValue>('recent')

  const projects = useQuery(listProjects)
  const active = useActiveRunPoll()

  // 실행이 막 끝나면(진행중 → null) 배너가 사라지는데, 방금 끝난 테스트로
  // 카드의 개수·성공률이 바뀌었을 수 있다 — 목록도 같이 다시 물어야 한다.
  const wasRunning = useRef(false)
  useEffect(() => {
    if (active) {
      wasRunning.current = true
      return
    }
    if (wasRunning.current) {
      wasRunning.current = false
      projects.reload()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active])

  const groups = useMemo(() => {
    const rows = projects.data ?? []
    if (tab === 'recent') return [{ title: null, items: rows }]

    const byCategory = new Map<string, ProjectCard[]>()
    for (const project of rows) {
      const bucket = byCategory.get(project.category) ?? []
      bucket.push(project)
      byCategory.set(project.category, bucket)
    }
    return [...byCategory].map(([title, items]) => ({ title, items }))
  }, [projects.data, tab])

  return (
    <AppLayout>
      <PageBody>
        <div className="mx-auto max-w-[1442px]">
          {active ? (
            <div className="mb-[45px]">
              <RunProgressBanner
                progress={{
                  projectName: active.project_name,
                  testName: active.test_name,
                  done: active.done,
                  total: active.total,
                  percent: active.percent,
                }}
                onOpen={() => navigate(`/projects/${active.project_id}/tests/new/running`)}
              />
            </div>
          ) : null}

          <div className="flex items-start justify-between">
            <PageHeading title="프로젝트" description="진행한 프로젝트를 한눈에 확인해요." />
            <Button onClick={() => navigate('/projects/new')} className="w-[230px]">
              새 프로젝트 만들기
            </Button>
          </div>

          <Tabs tabs={TABS} value={tab} onChange={setTab} className="mt-[22px]" />

          <div className="mt-[41px] flex flex-col gap-[40px]">
            {projects.loading ? <LoadingBlock label="프로젝트를 불러오는 중이에요" /> : null}
            {projects.error ? (
              <ErrorBlock message={projects.error} onRetry={projects.reload} />
            ) : null}

            {!projects.loading && !projects.error && (projects.data?.length ?? 0) === 0 ? (
              <EmptyProjects onCreate={() => navigate('/projects/new')} />
            ) : null}

            {groups.map((group, index) => (
              <section key={group.title ?? index}>
                {group.title ? (
                  <h2 className="mb-[16px] text-[18px] font-semibold text-ink">{group.title}</h2>
                ) : null}
                <div className="grid grid-cols-3 gap-x-[31px] gap-y-[22px]">
                  {group.items.map((project) => (
                    <ProjectCardItem
                      onRemove={async () => {
                        const r = await deleteProject(project.id)
                        if (r.ok) projects.reload()
                        else window.alert(r.message ?? '지우지 못했어요.')
                      }}
                      key={project.id}
                      project={project}
                      onOpen={() => navigate(`/projects/${project.id}`)}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        </div>
      </PageBody>
    </AppLayout>
  )
}

function ProjectCardItem({
  project,
  onOpen,
  onRemove,
}: {
  project: ProjectCard
  onOpen: () => void
  onRemove: () => void
}) {
  const [menu, setMenu] = useState(false)

  return (
    <article
      onClick={onOpen}
      className="flex h-[315px] cursor-pointer flex-col gap-[8px] rounded-[16px] border border-line bg-white p-[14px] transition-shadow hover:shadow-[0_6px_20px_rgba(0,0,0,0.06)]"
    >
      <div className="min-h-0 flex-1 overflow-hidden rounded-[12px] border border-line">
        <SitePreview url={project.preview_url} alt={`${project.name} 미리보기`} />
      </div>

      <div className="flex items-start justify-between px-[8px]">
        <div className="flex min-w-0 flex-1 flex-col gap-[11px] break-words">
          <p className="font-noto text-[22px] leading-[1.45] font-bold text-ink">{project.name}</p>
          <p className="font-noto text-[14px] leading-[1.45] text-subtext">
            진행한 테스트 {project.test_count}개
          </p>
          <p className="text-[14px] text-subtext">{timeAgo(project.last_activity_at)}</p>
        </div>
        {/* 예전에는 눌러도 아무 일이 없었다. 직접 만든 프로젝트가 쌓이면
            치울 방법이 있어야 한다 — 데모에 딸려 오는 셋은 대상이 아니다. */}
        <div className="relative shrink-0">
          <button
            type="button"
            aria-label={`${project.name} 더보기`}
            aria-expanded={menu}
            onClick={(event) => {
              event.stopPropagation()
              setMenu((v) => !v)
            }}
            className="grid size-[36px] place-items-center rounded-full hover:bg-black/[0.04]"
          >
            <img src={moreIcon} alt="" className="size-[36px]" />
          </button>

          {menu ? (
            <div
              onClick={(event) => event.stopPropagation()}
              className="absolute top-[38px] right-0 z-10 w-[188px] rounded-[10px] border border-line bg-white py-[6px] shadow-[0_8px_24px_rgba(0,0,0,0.12)]"
            >
              {project.removable ? (
                <button
                  type="button"
                  onClick={() => {
                    setMenu(false)
                    if (window.confirm(`"${project.name}" 프로젝트를 지울까요?`)) onRemove()
                  }}
                  className="block w-full px-[14px] py-[9px] text-left text-[14px] text-danger hover:bg-black/[0.03]"
                >
                  프로젝트 지우기
                </button>
              ) : (
                <p className="px-[14px] py-[9px] text-[13px] leading-[1.5] text-subtext">
                  데모에 들어 있는 프로젝트라 지울 수 없어요.
                </p>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </article>
  )
}
