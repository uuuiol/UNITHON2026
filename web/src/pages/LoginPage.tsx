import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, signup } from '../api/client'
import { useMutation } from '../api/hooks'
import { setToken } from '../lib/authToken'
import logoMark from '../assets/img/logo-mark.svg'
import logoWordmark from '../assets/img/logo-wordmark.svg'

/** 로그인 (Figma 311:21134). 이메일/이름을 더 넣으면 그 자리에서 회원가입 모드가 된다. */
export function LoginPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [ssoNotice, setSsoNotice] = useState(false)

  const loginMutation = useMutation(login)
  const signupMutation = useMutation(signup)
  const active = mode === 'login' ? loginMutation : signupMutation

  const signIn = async () => {
    const result =
      mode === 'login' ? await loginMutation.run(email, password) : await signupMutation.run(email, password, name)
    if (result) {
      setToken(result.token)
      navigate('/projects')
    }
  }

  return (
    <div className="flex min-h-screen bg-white">
      {/* 왼쪽 판 — 720px 고정. 폼이 넓어지면 한 줄이 길어져서 읽기 나빠진다. */}
      <div className="w-[720px] shrink-0 px-[118px] pt-[58px] pb-[60px]">
        <div className="flex items-center gap-[15px]">
          <span className="grid size-[85px] place-items-center rounded-[19.22px] bg-main">
            <img src={logoMark} alt="" className="w-[71.5px]" />
          </span>
          <img src={logoWordmark} alt="더드미" className="h-[29.8px] w-[82px]" />
        </div>

        <h1 className="mt-[31px] text-[34px] font-bold text-heading">
          {mode === 'login' ? '다시 만나서 반가워요' : '계정을 만들어볼까요'}
        </h1>
        <p className="mt-[10px] text-[16px] text-muted">
          {mode === 'login' ? '계속하려면 계정에 로그인해주세요.' : '이메일과 비밀번호만 있으면 바로 시작할 수 있어요.'}
        </p>

        <form
          className="mt-[62px] flex w-[484px] flex-col"
          onSubmit={(event) => {
            event.preventDefault()
            signIn()
          }}
        >
          {mode === 'signup' ? (
            <>
              <Label htmlFor="login-name">이름</Label>
              <Input
                id="login-name"
                type="text"
                autoComplete="name"
                placeholder="홍길동"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </>
          ) : null}

          <Label htmlFor="login-email" className={mode === 'signup' ? 'mt-[27px]' : ''}>
            이메일
          </Label>
          <Input
            id="login-email"
            type="email"
            autoComplete="email"
            placeholder="name@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />

          <Label htmlFor="login-password" className="mt-[27px]">
            비밀번호
          </Label>
          <Input
            id="login-password"
            type="password"
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            placeholder="••••••••••••"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />

          {mode === 'login' ? (
            <button
              type="button"
              className="mt-[6px] self-end text-[14px] font-medium text-main hover:underline"
            >
              비밀번호를 잊으셨나요?
            </button>
          ) : null}

          {active.error ? (
            <p className="mt-[16px] text-[14px] font-medium text-danger">{active.error}</p>
          ) : null}

          <button
            type="submit"
            disabled={active.pending}
            className="mt-[21px] h-[56px] rounded-[10px] bg-main text-[16px] font-semibold text-white transition-colors hover:bg-[#2872dd] disabled:opacity-60"
          >
            {active.pending ? '처리 중...' : mode === 'login' ? '로그인' : '회원가입'}
          </button>
        </form>

        <div className="mt-[36px] flex w-[484px] items-center gap-[8px]">
          <span className="h-px flex-1 bg-divider" />
          <span className="text-[14px] text-placeholder">또는</span>
          <span className="h-px flex-1 bg-divider" />
        </div>

        <div className="mt-[26px] flex w-[484px] flex-col gap-[14px]">
          <SocialButton onClick={() => setSsoNotice(true)}>G&nbsp;&nbsp;Google로 계속하기</SocialButton>
          <SocialButton onClick={() => setSsoNotice(true)}>→&nbsp;&nbsp;SSO로 계속하기</SocialButton>
        </div>
        {ssoNotice ? (
          <p className="mt-[12px] text-[14px] text-muted">소셜 로그인은 아직 준비 중이에요. 이메일로 진행해주세요.</p>
        ) : null}

        <p className="mt-[142px] flex items-center gap-[41px] text-[14px]">
          <span className="text-muted">
            {mode === 'login' ? '아직 계정이 없으신가요?' : '이미 계정이 있으신가요?'}
          </span>
          <button
            type="button"
            onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}
            className="font-semibold text-main hover:underline"
          >
            {mode === 'login' ? '회원가입' : '로그인'}
          </button>
        </p>
      </div>

      {/* 오른쪽 판 — 제품이 무엇을 보여주는지 미리 보여주는 자리.
          카드 세 장은 실제 화면(다이어그램·페르소나·리플레이)에서 따 왔다. */}
      <div className="relative min-w-0 flex-1 overflow-hidden bg-brand-tint">
        <div className="relative h-full w-[1200px] pt-[128px] pl-[166px]">
          <span className="inline-flex h-[30px] items-center rounded-full bg-white px-[16px] text-[13px] font-semibold text-main">
            AI PERSONA UX TEST
          </span>
          <h2 className="mt-[27px] text-[42px] leading-[1.4] font-bold text-heading">
            반복 테스트는 AI에게,
            <br />
            중요한 판단은 사람에게.
          </h2>
          <p className="mt-[22px] text-[18px] text-muted">
            페르소나가 직접 탐색하고, 행동·감정·이탈 지점을 한 번에 기록해요.
          </p>

          <FlowCard />
          <PersonaCard />
          <ReplayCard />
        </div>
      </div>
    </div>
  )
}

function Label({
  children,
  htmlFor,
  className = '',
}: {
  children: React.ReactNode
  htmlFor: string
  className?: string
}) {
  return (
    <label htmlFor={htmlFor} className={`text-[14px] font-medium text-heading ${className}`}>
      {children}
    </label>
  )
}

function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="mt-[9px] h-[54px] rounded-[10px] border border-divider bg-white px-[16px] text-[15px] text-heading outline-none placeholder:text-placeholder focus:border-main"
    />
  )
}

function SocialButton({
  children,
  onClick,
}: {
  children: React.ReactNode
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="h-[54px] rounded-[10px] border border-divider bg-white text-[16px] font-semibold text-heading transition-colors hover:bg-black/[0.02]"
    >
      {children}
    </button>
  )
}

const FLOW = [
  { label: 'Home', done: false },
  { label: 'Search', done: false },
  { label: 'Detail', done: false },
  { label: 'Done', done: true },
]

function FlowCard() {
  return (
    <div className="absolute top-[402px] left-[146px] h-[260px] w-[430px] overflow-hidden rounded-[22px] border border-divider bg-white p-[24px]">
      <p className="text-[16px] font-bold text-heading">Navigation Flow</p>
      <p className="mt-[9px] text-[13px] text-placeholder">20 personas · Step 6</p>
      <div className="mt-[36px] flex items-center">
        {FLOW.map((step, index) => (
          <div key={step.label} className="flex items-center">
            {/* 이음선은 '다음 칸이 완료인지'로 칠한다 — 완료 직전 한 칸만 초록이다. */}
            {index > 0 ? (
              <span
                className={`h-[4px] w-[32px] rounded-[2px] ${
                  step.done ? 'bg-[#8ad8ba]' : 'bg-[#b7c4d6]'
                }`}
              />
            ) : null}
            <span
              className={`grid h-[44px] w-[68px] place-items-center rounded-[10px] text-[12px] font-semibold ${
                step.done ? 'bg-ok-bg text-ok' : 'bg-track text-muted'
              }`}
            >
              {step.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function PersonaCard() {
  return (
    <div className="absolute top-[470px] left-[610px] h-[300px] w-[390px] overflow-hidden rounded-[22px] border border-divider bg-white px-[25px] pt-[27px]">
      <div className="flex items-center gap-[15px]">
        <span className="grid size-[40px] place-items-center rounded-full bg-brand-soft text-[16px] font-bold text-main">
          김
        </span>
        <div className="flex-1">
          <p className="text-[17px] font-bold text-heading">김민지</p>
          <p className="mt-[7px] text-[13px] text-muted">23세 · 여성 · 가격 민감형</p>
        </div>
        <span className="grid h-[30px] w-[70px] place-items-center rounded-full bg-ok-bg text-[13px] font-semibold text-ok">
          성공
        </span>
      </div>

      <div className="mt-[27px] h-px bg-divider" />

      <p className="mt-[23px] text-[13px] font-semibold text-main">AI 내면 독백</p>
      <p className="mt-[12px] rounded-[12px] bg-brand-faint px-[16px] py-[18px] text-[14px] leading-[1.6] font-medium text-heading">
        “비교하기 쉬운 것부터 보고
        <br />
        가격이 맞으면 바로 진행해야겠다.”
      </p>
      <p className="mt-[22px] text-[13px] font-medium text-muted">현재 감정 · 안도 76%</p>
    </div>
  )
}

function ReplayCard() {
  return (
    <div className="absolute top-[716px] left-[208px] h-[180px] w-[292px] rounded-[18px] border border-divider bg-white px-[24px] pt-[22px]">
      <p className="text-[15px] font-bold text-heading">Replay</p>
      <p className="mt-[9px] text-[13px] text-muted">Step 6 / 18</p>
      <div className="mt-[26px] h-[10px] w-[220px] rounded-full bg-track">
        <div className="h-full w-[142px] rounded-full bg-main" />
      </div>
      <p className="mt-[17px] text-[16px] font-bold text-main">▶</p>
    </div>
  )
}
