import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import chevronDownIcon from '../assets/icons/chevron-down.svg'
import avatar from '../assets/img/avatar.png'
import { clearToken } from '../lib/authToken'

/**
 * 사이드바 맨 아래 프로필. 누르면 계정 메뉴가 열린다.
 *
 * 전역 사이드바와 테스트 상세 사이드바가 같은 블록을 쓴다 — 둘로 나눠 두면
 * 한쪽에만 메뉴가 달려서 "여기선 되는데 저기선 안 되는" 상태가 된다.
 */
export function ProfileMenu({ collapsed = false }: { collapsed?: boolean }) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)

  // 바깥을 누르거나 Esc 를 누르면 닫는다. 열어 둔 채로 다른 곳을 누르면
  // 메뉴가 화면에 남아 무엇이 눌린 것인지 알 수 없다.
  useEffect(() => {
    if (!open) return
    const onDown = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const go = (to: string) => {
    setOpen(false)
    navigate(to)
  }

  const signOut = () => {
    setOpen(false)
    clearToken()
    navigate('/login')
  }

  return (
    <div
      ref={box}
      className={`relative flex h-[70px] shrink-0 items-center ${
        collapsed ? 'justify-center px-0' : 'px-[30px]'
      }`}
    >
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        title="계정 메뉴"
        className="flex items-center gap-[7px] rounded-[12px] transition-colors hover:bg-black/[0.03]"
      >
        <img src={avatar} alt="" className="size-[35px] rounded-full object-cover" />
        {collapsed ? null : (
          <>
            <span className="text-[20px] text-ink">영찬</span>
            <span className="text-[13px] leading-[1.45] font-medium text-subtext">Pro</span>
            <img
              src={chevronDownIcon}
              alt=""
              className={`size-[24px] transition-transform ${open ? 'rotate-180' : ''}`}
            />
          </>
        )}
      </button>

      {open ? (
        <div
          role="menu"
          className={`absolute bottom-[62px] z-30 w-[212px] overflow-hidden rounded-[14px] border border-line bg-white py-[6px] shadow-[0_10px_30px_rgba(0,0,0,0.12)] ${
            collapsed ? 'left-[12px]' : 'left-[24px]'
          }`}
        >
          <div className="px-[16px] pt-[8px] pb-[10px]">
            <p className="text-[14px] font-semibold text-heading">영찬</p>
            <p className="mt-[3px] truncate text-[12px] text-muted">youngchan@example.com</p>
          </div>
          <div className="h-px bg-divider" />
          <MenuItem onClick={() => go('/settings')}>계정 설정</MenuItem>
          <MenuItem onClick={() => go('/credit')}>크레딧 및 플랜</MenuItem>
          <div className="h-px bg-divider" />
          <MenuItem onClick={signOut} tone="danger">
            로그아웃
          </MenuItem>
        </div>
      ) : null}
    </div>
  )
}

function MenuItem({
  children,
  onClick,
  tone = 'plain',
}: {
  children: React.ReactNode
  onClick: () => void
  tone?: 'plain' | 'danger'
}) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      className={`block w-full px-[16px] py-[10px] text-left text-[14px] transition-colors hover:bg-black/[0.03] ${
        tone === 'danger' ? 'font-semibold text-danger' : 'text-body'
      }`}
    >
      {children}
    </button>
  )
}
