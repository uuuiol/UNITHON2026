import type { ReactNode } from 'react'
import type { PersonaSideResult } from '../api/client'

/**
 * 페르소나 표에 쓰는 작은 조각들.
 *
 * 프로젝트 안의 결과 표와 두 사이트를 견주는 비교 표가 같은 눈금을 써야 한다 —
 * 스텝 막대의 기준이 화면마다 다르면 나란히 놓았을 때 길이를 믿을 수 없다.
 */

const OUTCOME_STYLE = {
  success: { label: '성공', className: 'bg-success-soft text-success' },
  drop: { label: '이탈', className: 'bg-[#fff6d6] text-[#8a6d00]' },
  other: { label: '기록 없음', className: 'bg-track text-subtext' },
} as const

/** 막대를 꽉 채우는 스텝 수. 두 화면이 같은 값을 써야 길이가 비교된다. */
const FULL_STEPS = 30

/** 1~5 단계를 점으로. 숫자만 보면 크기가 느껴지지 않는다. */
export function Dots({ value }: { value: number }) {
  return (
    <span className="flex gap-[4px]" title={`${value}단계`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <i key={i} className={`size-[8px] rounded-full ${i <= value ? 'bg-main' : 'bg-line'}`} />
      ))}
    </span>
  )
}

/**
 * DB 특성 축 하나의 값 — "정독"/"훑기"처럼 **둘 중 하나**다.
 *
 * Dots는 1~5 단계용이라 이 값에 억지로 씌우면 없는 중간 단계를 지어내는
 * 셈이 된다. 실제 값을 그대로 텍스트로 보여준다.
 */
export function TraitLabel({ value }: { value?: string }) {
  if (!value) return <span className="text-[13px] text-subtext">–</span>
  return (
    <span className="rounded-[6px] bg-bg px-[8px] py-[3px] text-[13px] font-medium text-ink">
      {value}
    </span>
  )
}

/** 한쪽 사이트에서의 결과 — 배지 + 스텝 막대. 막대 길이는 스텝 수에 비례한다. */
export function SideResult({ side }: { side: PersonaSideResult | null }) {
  if (!side) return <span className="text-[13px] text-subtext">–</span>
  const tone = OUTCOME_STYLE[side.outcome ?? 'other']
  const steps = side.step_count ?? 0
  const width = Math.min(100, Math.max(8, (steps / FULL_STEPS) * 100))

  return (
    <span className="flex items-center gap-[10px] whitespace-nowrap">
      <span
        className={`rounded-[6px] px-[8px] py-[3px] text-[12px] font-semibold ${tone.className}`}
      >
        {side.end_label || tone.label}
      </span>
      <span className="h-[6px] w-[86px] overflow-hidden rounded-[3px] bg-line">
        <span
          className={`block h-full rounded-[3px] ${
            side.outcome === 'success' ? 'bg-success' : 'bg-[#e56a5a]'
          }`}
          style={{ width: `${width}%` }}
        />
      </span>
      <span className="text-[13px] text-subtext tabular-nums">{steps} step</span>
    </span>
  )
}

export function Chip({ tone, children }: { tone: 'plain' | 'warn' | 'hold'; children: ReactNode }) {
  const style = {
    plain: 'bg-bg text-subtext',
    warn: 'bg-[#fdeceb] text-[#c0392b]',
    hold: 'bg-[#fdf4e3] text-[#9a6b1a]',
  }[tone]
  return (
    <span className={`rounded-[999px] px-[10px] py-[4px] text-[12px] font-medium ${style}`}>
      {children}
    </span>
  )
}
