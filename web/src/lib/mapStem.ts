/**
 * server/app/orchestrate.py의 _map_stem()과 같은 규칙 — 답사 지도·스크린샷
 * 파일명에 쓰는 호스트 기반 짧은 이름이다. 갤러리 링크를 만들 때 서버가
 * 실제로 그 이름으로 저장했는지 왕복으로 물을 방법이 없어(있으면 보여주고
 * 없으면 빈 화면), 여기서도 같은 규칙으로 미리 계산한다. 로직을 바꿀 땐
 * orchestrate.py의 _map_stem()도 같이 고칠 것.
 */
export function mapStem(url: string): string {
  const clean = url.includes('://') ? url : `https://${url}`
  let host = ''
  try {
    host = new URL(clean).host
  } catch {
    return 'site'
  }
  const safe = Array.from(host)
    .map((c) => (/[A-Za-z0-9._-]/.test(c) ? c : '_'))
    .join('')
  const trimmed = safe.replace(/^_+|_+$/g, '')
  return trimmed || 'site'
}
