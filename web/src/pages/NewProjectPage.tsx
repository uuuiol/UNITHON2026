import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createProject } from '../api/client'
import { useMutation } from '../api/hooks'
import apkIcon from '../assets/img/src-apk.png'
import githubIcon from '../assets/img/src-github.png'
import linkIcon from '../assets/img/src-link.png'
import { AppLayout, PageBody, PageHeading } from '../components/AppLayout'
import { CATEGORIES, CategorySelect } from '../components/CategorySelect'
import { ConnectionCard } from '../components/ConnectionCard'
import { DEVICE_PRESETS, DeviceSelect } from '../components/DeviceSelect'
import { FieldLabel, TextField } from '../components/Field'
import { FileDropZone } from '../components/FileDropZone'
import { PreviewModal } from '../components/PreviewModal'
import { SegmentedControl } from '../components/SegmentedControl'
import { WizardTopBar } from '../components/StepIndicator'
import { WizardFooter } from '../components/WizardFooter'
import { useConnection } from '../hooks/useConnection'

const SOURCES = [
  { value: 'web_link', label: '웹 링크', icon: <img src={linkIcon} alt="" className="size-[14px]" /> },
  { value: 'github', label: '깃허브', icon: <img src={githubIcon} alt="" className="size-[19px]" /> },
  { value: 'apk', label: 'APK 파일', icon: <img src={apkIcon} alt="" className="size-[19px]" /> },
] as const

export function NewProjectPage() {
  const navigate = useNavigate()
  const [source, setSource] = useState<(typeof SOURCES)[number]['value']>('web_link')
  const [name, setName] = useState('')
  const [device, setDevice] = useState(DEVICE_PRESETS[3].id) // 노트북 1280×800 — 기본 답사 환경
  const [category, setCategory] = useState<string>(CATEGORIES[0])
  const [link, setLink] = useState('')
  const [flowMap, setFlowMap] = useState<File | null>(null)
  const [previewOpen, setPreviewOpen] = useState(false)

  const connection = useConnection()
  const create = useMutation(createProject)

  return (
    <AppLayout
      topBar={<WizardTopBar breadcrumb={{ page: '새 프로젝트' }} />}
      footer={
        <WizardFooter
          onPrev={() => navigate('/projects')}
          onNext={async () => {
            const created = await create.run({
              name: name.trim(),
              category: category.trim(),
              target_url: connection.previewUrl ?? link,
              source,
              device_preset: device,
              flow_map_path: flowMap?.name ?? null,
              preview_embeddable: connection.embeddable,
            })
            if (created) navigate(`/projects/${created.id}`)
          }}
          nextLabel={create.pending ? '만드는 중…' : '생성하기'}
          // 필수 칸이 비어 있으면 넘어가지 못한다. 링크는 연결 확인까지 거친다.
          // 다만 **시간 초과는 막지 않는다** — 느린 사이트가 15초 안에 대답을
          // 못 한 것과 주소가 틀린 것은 다르다. 주소를 아는 쪽은 사용자다.
          nextDisabled={
            create.pending ||
            name.trim() === '' ||
            link.trim() === '' ||
            category.trim() === '' ||
            !connection.canProceed
          }
        />
      }
    >
      <PageBody>
        <div className="max-w-[1280px]">
          <PageHeading
            title="어떤 프로젝트를 업로드 할까요?"
            description="링크나 파일을 연결하면 테스트 가능한 상태인지 바로 확인해요."
          />

          <SegmentedControl
            options={SOURCES}
            value={source}
            onChange={setSource}
            className="mt-[21px] w-[420px]"
          />

          {/* 지금 도는 것은 웹 링크뿐이다. 나머지를 눌렀을 때 아무 말도 없으면
              "왜 아무 일도 안 나지?" 하고 고장으로 읽힌다. 안 되는 것은
              안 된다고 먼저 말하는 편이 낫다. */}
          {source !== 'web_link' ? (
            <div
              role="status"
              className="mt-[16px] flex max-w-[720px] items-start gap-[10px] rounded-[12px] border border-[#f0d9a8] bg-[#fdf7e8] px-[18px] py-[14px]"
            >
              <span aria-hidden className="text-[16px] leading-[1.3]">🚧</span>
              <p className="text-[14px] leading-[1.6] text-[#7a5a12]">
                <b className="font-semibold">
                  {source === 'github' ? '깃허브' : 'APK 파일'} 연결은 추후 업데이트 예정이에요.
                </b>
                <br />
                지금은 <b className="font-semibold">웹 링크</b>만 검사할 수 있어요. AI 페르소나가
                실제 브라우저로 화면을 열어 조작하는 방식이라, 주소로 열리는 사이트가 필요해요.
                <button
                  type="button"
                  onClick={() => setSource('web_link')}
                  className="ml-[6px] font-semibold text-main underline underline-offset-4"
                >
                  웹 링크로 하기
                </button>
              </p>
            </div>
          ) : null}

          <div className="mt-[17px] flex flex-col gap-[20px]">
            <TextField
              label="프로젝트 이름"
              required
              placeholder="예) 쇼핑몰 v.1"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={100}
              counter
            />

            <div className="flex flex-col gap-[7px]">
              <FieldLabel required>실행 환경 디바이스</FieldLabel>
              <DeviceSelect value={device} onChange={setDevice} />
            </div>

            <div className="flex flex-col gap-[7px]">
              <FieldLabel required>프로젝트 카테고리</FieldLabel>
              <CategorySelect value={category} onChange={setCategory} />
            </div>

            <TextField
              label="프로젝트 링크"
              required
              placeholder="www.example.com/proto/..."
              value={link}
              onChange={(event) => {
                setLink(event.target.value)
                connection.reset()
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter') connection.run(link)
              }}
              leading={<span className="shrink-0 text-[15px] text-placeholder">https://</span>}
              trailing={
                <button
                  type="button"
                  onClick={() => connection.run(link)}
                  disabled={link.trim() === '' || connection.state.status === 'checking'}
                  className="h-[62px] w-[160px] shrink-0 rounded-[14px] bg-main text-[20px] leading-[1.45] font-bold text-white transition-colors hover:bg-[#2872dd] disabled:cursor-not-allowed disabled:bg-[#c4d9f9]"
                >
                  {connection.state.status === 'checking' ? '확인 중…' : '연결하기'}
                </button>
              }
            />

            <ConnectionCard
              state={connection.state}
              onPreview={() => setPreviewOpen(true)}
              onRetry={() => connection.run(link)}
            />

            {create.error ? (
              <p className="text-[14px] font-medium text-danger">{create.error}</p>
            ) : null}

            <div className="flex flex-col gap-[7px]">
              <FieldLabel hint="예) sitemap.xml">유저 플로우 맵</FieldLabel>
              <p className="text-[16px] leading-[1.45] text-body">
                혹시 유저 플로우 맵이 있다면 정확도가 훨씬 올라가요
              </p>
              <FileDropZone file={flowMap} onSelect={setFlowMap} />
            </div>
          </div>
        </div>
      </PageBody>

      <PreviewModal
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
        url={connection.previewUrl}
        embeddable={connection.embeddable}
        blockReason={connection.blockReason}
      />
    </AppLayout>
  )
}
