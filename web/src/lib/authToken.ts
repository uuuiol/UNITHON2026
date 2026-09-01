/**
 * 로그인 토큰 저장소.
 *
 * `personaNames.ts`와 같은 패턴 — localStorage에 두고, 바뀌면 `CustomEvent`로
 * 이 창의 모든 구독자(라우트 가드, 프로필 메뉴 등)에게 알린다. 다른 탭에서
 * 로그아웃해도 `storage` 이벤트로 따라간다.
 */

const KEY = 'moji.authToken'
const EVENT = 'moji:auth-token'

export function getToken(): string | null {
  try {
    return localStorage.getItem(KEY)
  } catch {
    // 사생활 보호 창처럼 저장이 막힌 곳. 로그인 안 된 것으로 본다.
    return null
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(KEY, token)
  } catch {
    // 저장은 못 해도 이번 화면(탭)에서는 로그인 상태로 다뤄야 한다.
  }
  window.dispatchEvent(new CustomEvent(EVENT))
}

export function clearToken(): void {
  try {
    localStorage.removeItem(KEY)
  } catch {
    // 무시 — 못 지워도 아래 이벤트로 이번 창은 로그아웃 상태가 된다.
  }
  window.dispatchEvent(new CustomEvent(EVENT))
}

export function subscribeToken(fn: () => void): () => void {
  window.addEventListener(EVENT, fn)
  window.addEventListener('storage', fn)
  return () => {
    window.removeEventListener(EVENT, fn)
    window.removeEventListener('storage', fn)
  }
}
