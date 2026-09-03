/**
 * server/app/orchestrate.py의 _map_stem()과 같은 규칙 — 답사 지도·스크린샷
 * 파일명에 쓰는 짧은 이름이다. 갤러리 링크를 만들 때 서버가 실제로 그
 * 이름으로 저장했는지 왕복으로 물을 방법이 없어(있으면 보여주고 없으면
 * 빈 화면), 여기서도 같은 규칙으로 미리 계산한다. 로직을 바꿀 땐
 * orchestrate.py의 _map_stem()·agent-ux/uxagent/config.py의 map_stem()도
 * 같이 고칠 것.
 *
 * 호스트만 쓰던 예전 버전은 같은 호스트의 서로 다른 페이지(우리
 * 테스트베드의 clean/flawed 등)가 캐시 파일명을 공유해 서로 덮어썼다
 * (2026-09-03 실측) — 그래서 경로까지 포함한 root를 키로 쓴다.
 */
const MAP_STEM_MAX_LEN = 150 // 세 구현(config.py·orchestrate.py·여기)이 반드시 같은 값을 써야 한다.

export function mapStem(url: string): string {
  const clean = url.includes('://') ? url : `https://${url}`
  let origin = ''
  try {
    origin = new URL(clean).origin
  } catch {
    return 'site'
  }
  const slashCount = (clean.match(/\//g) ?? []).length
  const root = slashCount > 2 ? clean.slice(0, clean.lastIndexOf('/')) : origin
  const rawName = root.replace(/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//, '')
  const safe = Array.from(rawName)
    .map((c) => (/[A-Za-z0-9._-]/.test(c) ? c : '_'))
    .join('')
  const trimmed = (safe.replace(/^_+|_+$/g, '') || 'site').slice(0, MAP_STEM_MAX_LEN)
  return trimmed || 'site'
}
