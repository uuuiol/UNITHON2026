import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, getActiveRun, type ActiveRun } from './client'

type QueryState<T> = {
  data: T | undefined
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * 조회용 최소 훅. react-query 를 넣을 만큼의 복잡도가 아직 없어서 직접 만든다.
 * 언마운트 뒤 setState 를 막고, deps 가 바뀌면 이전 응답을 버린다.
 */
export function useQuery<T>(fetcher: () => Promise<T>, deps: unknown[] = []): QueryState<T> {
  const [data, setData] = useState<T>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  useEffect(() => {
    let current = true
    setLoading(true)
    setError(null)

    fetcher()
      .then((result) => {
        if (!current || !alive.current) return
        setData(result)
      })
      .catch((cause: unknown) => {
        if (!current || !alive.current) return
        setError(cause instanceof ApiError ? cause.message : '불러오지 못했어요.')
      })
      .finally(() => {
        if (current && alive.current) setLoading(false)
      })

    return () => {
      current = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])

  return { data, loading, error, reload }
}

const ACTIVE_RUN_POLL_MS = 3000

/**
 * 진행중인 실행을 주기적으로 다시 묻는다.
 *
 * 프로젝트 목록/상세 화면의 진행 배너가 `useQuery(getActiveRun)`로 **한 번만**
 * 물어서, 실행이 끝나거나 계속 진행돼도 처음 값(예: 0%)에 배너가 멈춰 있던
 * 문제가 있었다 — RunningPage.tsx와 같은 뿌리지만 다른 화면에서 또 터진 것.
 * 여기서는 완료 시 100%로 마무리할 필요가 없다 — null이 오면 그냥 배너가
 * 사라지고, 아래 목록에 방금 끝난 테스트가 나타난다.
 */
export function useActiveRunPoll(): ActiveRun | null {
  const [run, setRun] = useState<ActiveRun | null>(null)

  useEffect(() => {
    let alive = true

    const tick = async () => {
      try {
        const next = await getActiveRun()
        if (alive) setRun(next)
      } catch {
        // 폴링 실패는 화면을 깨뜨리지 않는다. 다음 주기에 다시 시도한다.
      }
    }

    void tick()
    const timer = window.setInterval(tick, ACTIVE_RUN_POLL_MS)
    return () => {
      alive = false
      window.clearInterval(timer)
    }
  }, [])

  return run
}

/** 쓰기용. 진행 상태와 실패 사유만 돌려준다. */
export function useMutation<Args extends unknown[], T>(action: (...args: Args) => Promise<T>) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(
    async (...args: Args): Promise<T | null> => {
      setPending(true)
      setError(null)
      try {
        return await action(...args)
      } catch (cause) {
        setError(cause instanceof ApiError ? cause.message : '요청에 실패했어요.')
        return null
      } finally {
        setPending(false)
      }
    },
    [action],
  )

  return { run, pending, error }
}
