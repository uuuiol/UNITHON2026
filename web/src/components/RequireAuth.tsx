import { useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { getToken, subscribeToken } from '../lib/authToken'

/**
 * 로그인 라우트 가드. 토큰이 없으면 `/login`으로 보낸다.
 *
 * `subscribeToken`을 구독하므로 로그인/로그아웃이 새로고침 없이 바로 반영된다
 * — 다른 요청이 401을 받아 `clearToken()`을 호출해도 이 컴포넌트가 즉시 반응한다.
 */
export function RequireAuth() {
  const location = useLocation()
  const [token, setTokenState] = useState(getToken())

  useEffect(() => subscribeToken(() => setTokenState(getToken())), [])

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  return <Outlet />
}
