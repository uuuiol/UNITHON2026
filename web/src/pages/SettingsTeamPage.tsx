import { useEffect, useState } from 'react'
import { getAccount, updateAccount } from '../api/client'
import { useMutation, useQuery } from '../api/hooks'
import { SettingsCard, SettingsLayout } from '../components/SettingsLayout'
import { ErrorBlock, LoadingBlock } from '../components/StateView'

/** 설정 · 팀 설정 (Figma 311:21271). */
export function SettingsTeamPage() {
  const account = useQuery(getAccount, [])
  const save = useMutation(updateAccount)

  const [name, setName] = useState('')
  const [workspace, setWorkspace] = useState('')
  const [email, setEmail] = useState('')
  const [notice, setNotice] = useState<string | null>(null)

  // 서버 값이 도착하면 한 번 채운다. 이후에 사용자가 고친 값은 건드리지 않는다.
  const data = account.data
  useEffect(() => {
    if (!data) return
    setName(data.name)
    setWorkspace(data.workspace)
    setEmail(data.email)
  }, [data])

  return (
    <SettingsLayout title="사용자 설정" description="프로필과 기본 정보를 관리해요.">
      {account.loading ? <LoadingBlock label="설정을 불러오는 중이에요" /> : null}
      {account.error ? <ErrorBlock message={account.error} onRetry={account.reload} /> : null}

      {data ? (
        <SettingsCard className="max-w-[1050px] px-[34px] pt-[30px] pb-[34px]">
          <h2 className="text-[18px] font-bold text-heading">기본 정보</h2>
          <p className="mt-[8px] text-[13px] text-muted">
            더드미에서 표시되는 이름과 프로필을 변경할 수 있어요.
          </p>

          <div className="mt-[35px] flex items-center gap-[24px]">
            <span className="grid size-[92px] place-items-center rounded-[20px] bg-brand-soft text-[28px] font-bold text-main">
              {data.initial}
            </span>
            <button
              type="button"
              onClick={() => setNotice('프로필 이미지 변경은 준비 중이에요.')}
              className="h-[44px] rounded-[10px] border border-divider bg-white px-[28px] text-[14px] font-medium text-heading transition-colors hover:bg-black/[0.02]"
            >
              프로필 이미지 변경
            </button>
          </div>

          <Field id="settings-name" label="이름" value={name} onChange={setName} />
          <Field
            id="settings-workspace"
            label="워크스페이스 이름"
            value={workspace}
            onChange={setWorkspace}
          />
          <Field
            id="settings-email"
            label="이메일"
            value={email}
            onChange={setEmail}
            hint="로그인 및 알림에 사용되는 이메일입니다."
          />

          <div className="mt-[24px] flex items-center justify-end gap-[16px]">
            {save.error ? (
              <p className="text-[13px] font-medium text-danger">{save.error}</p>
            ) : notice ? (
              <p className="text-[13px] text-muted">{notice}</p>
            ) : null}
            <button
              type="button"
              disabled={save.pending}
              onClick={async () => {
                setNotice(null)
                const result = await save.run({ name, workspace, email })
                if (result) {
                  setNotice('저장했어요.')
                  account.reload()
                }
              }}
              className="h-[50px] w-[200px] rounded-[10px] bg-main text-[16px] font-semibold text-white transition-colors hover:bg-[#2872dd] disabled:opacity-60"
            >
              {save.pending ? '저장 중...' : '변경사항 저장'}
            </button>
          </div>
        </SettingsCard>
      ) : null}
    </SettingsLayout>
  )
}

function Field({
  id,
  label,
  value,
  onChange,
  hint,
}: {
  id: string
  label: string
  value: string
  onChange: (next: string) => void
  hint?: string
}) {
  return (
    <div className="mt-[38px] max-w-[660px]">
      <label htmlFor={id} className="text-[14px] font-medium text-heading">
        {label}
      </label>
      <input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-[9px] h-[54px] w-full rounded-[10px] border border-divider bg-white px-[16px] text-[15px] text-heading outline-none focus:border-main"
      />
      {hint ? <p className="mt-[8px] text-[13px] text-muted">{hint}</p> : null}
    </div>
  )
}
