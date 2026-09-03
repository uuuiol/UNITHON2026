import type { PersonaRow } from '../api/client'
import { Chip, SideResult, TraitLabel } from './PersonaBits'

/**
 * 페르소나별 결과 비교 (Figma 329:24937 · 290:9817).
 *
 * 이 표가 성립하는 이유는 하나다 — 같은 페르소나 열 명을 양쪽에 똑같이 투입했다.
 * 그래서 "P005 가 A 에서는 달성했는데 B 에서는 포기했다"가 사이트의 차이지
 * 사람의 차이가 아니라고 말할 수 있다. 사람이 다르면 이 표는 아무 뜻이 없다.
 */

export type ComparePayload = {
  items: PersonaRow[]
  total?: number
  changed?: number
  exhausted?: number
  axes?: Record<string, string>
}

export function PersonaCompareTable({
  data,
  baseName,
  againstName,
  baseRate,
  againstRate,
  onPick,
  selectedId,
}: {
  data: ComparePayload
  baseName: string
  againstName: string
  baseRate?: number | null
  againstRate?: number | null
  /** 행을 누르면 그 사람의 두 세션을 옆 패널에서 펼친다. 없으면 표만 보여준다. */
  onPick?: (persona: PersonaRow) => void
  selectedId?: string | null
}) {
  const items = data.items ?? []
  const axes = data.axes ?? {}
  const axisKeys = Object.keys(axes)
  const changed = data.changed ?? 0

  // 어느 쪽으로 달라졌는지까지 세야 문장을 쓸 수 있다. "3명이 달라졌다"만으로는
  // 좋아진 건지 나빠진 건지 알 수 없다.
  const worse = items.filter(
    (p) => p.changed && p.baseline?.outcome === 'success' && p.compare?.outcome !== 'success',
  ).length
  const better = changed - worse

  return (
    <section>
      <div className="flex flex-wrap items-center gap-[8px]">
        <Chip tone="plain">전체 {data.total ?? items.length}명</Chip>
        {changed > 0 ? <Chip tone="warn">결과가 달라진 {changed}명</Chip> : null}
        {(data.exhausted ?? 0) > 0 ? <Chip tone="hold">스텝 소진 {data.exhausted}명</Chip> : null}
        <span className="ml-auto text-[13px] text-subtext tabular-nums">
          {baseName} {pct(baseRate)} → {againstName} {pct(againstRate)}
        </span>
      </div>

      <div className="mt-[12px] rounded-[12px] bg-bg px-[18px] py-[14px]">
        <p className="text-[15px] font-semibold text-ink">
          {changed === 0
            ? '두 사이트에서 열 명의 결과가 모두 같았어요.'
            : `${worse > 0 ? `${worse}명이 ${baseName}에서는 달성했지만 ${againstName}에서는 못 했어요.` : ''}${
                better > 0
                  ? `${worse > 0 ? ' ' : ''}${better}명은 반대로 ${againstName}에서 해냈어요.`
                  : ''
              }`}
        </p>
        <p className="mt-[4px] text-[13px] text-subtext">
          {axisKeys.map((k) => axes[k]).join('·')}는 테스트 중 AI가 내부적으로 생성한 행동
          특성이며, 사용자가 직접 설정하는 값이 아니에요. 두 사이트에 같은 사람을 투입했기
          때문에 이 차이는 사람이 아니라 화면에서 온 것입니다.
        </p>
      </div>

      <div className="mt-[14px] overflow-x-auto rounded-[16px] border border-line">
        <table className="w-full min-w-[980px] border-collapse text-left">
          <thead>
            <tr className="bg-bg text-[13px] text-subtext">
              <th className="px-[18px] py-[12px] font-medium">페르소나</th>
              {axisKeys.map((k) => (
                <th key={k} className="px-[10px] py-[12px] font-medium whitespace-nowrap">
                  {axes[k]}
                </th>
              ))}
              <th className="px-[14px] py-[12px] font-medium whitespace-nowrap">{baseName}</th>
              <th className="px-[14px] py-[12px] font-medium whitespace-nowrap">{againstName}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((persona) => (
              <tr
                key={persona.id}
                onClick={onPick ? () => onPick(persona) : undefined}
                className={`border-t border-line text-[14px] ${
                  persona.changed ? 'bg-[#fff6f5]' : ''
                } ${selectedId === persona.id ? 'outline outline-2 -outline-offset-2 outline-main' : ''} ${
                  onPick ? 'cursor-pointer hover:bg-black/[0.02]' : ''
                }`}
              >
                <td className="px-[18px] py-[12px]">
                  <p className="font-semibold text-ink">{persona.code}</p>
                  <p className="text-[12px] text-subtext">{persona.name}</p>
                </td>
                {axisKeys.map((k) => (
                  <td key={k} className="px-[10px] py-[12px]">
                    <TraitLabel value={persona.traits?.[k]} />
                  </td>
                ))}
                <td className="px-[14px] py-[12px]">
                  <SideResult side={persona.baseline ?? null} />
                </td>
                <td className="px-[14px] py-[12px]">
                  <div className="flex items-center gap-[8px]">
                    <SideResult side={persona.compare ?? null} />
                    {persona.changed ? <Chip tone="warn">결과 변화</Chip> : null}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {onPick ? (
        <p className="mt-[10px] text-[13px] text-subtext">
          행을 선택하면 그 페르소나가 두 사이트에서 밟은 경로를 자세히 볼 수 있어요.
        </p>
      ) : null}
    </section>
  )
}

function pct(value: number | null | undefined): string {
  return value === null || value === undefined ? '–' : `${value}%`
}
