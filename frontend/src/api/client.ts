import createClient, { type Middleware } from 'openapi-fetch'
import { getIdentity } from '@/lib/identity'
import type { paths } from './schema'

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function detailMessage(detail: unknown, fallback = 'Algo salió mal'): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const msgs = detail.map((d: { msg?: string; loc?: unknown[] }) => {
      const field = Array.isArray(d.loc) ? d.loc.filter((x) => x !== 'body').join('.') : ''
      return field ? `${field}: ${d.msg}` : (d.msg ?? '')
    })
    return msgs.filter(Boolean).join(' · ') || fallback
  }
  return fallback
}

export function identityHeaders(): Record<string, string> {
  const { actAs, clientId } = getIdentity()
  const h: Record<string, string> = {}
  if (actAs) h['X-Act-As'] = actAs
  if (clientId) h['X-Client-Id'] = clientId
  return h
}

const identity: Middleware = {
  onRequest({ request }) {
    for (const [k, v] of Object.entries(identityHeaders())) {
      if (!request.headers.has(k)) request.headers.set(k, v)
    }
    return request
  },
}

export const api = createClient<paths>({ baseUrl: '' })
api.use(identity)

type Result<T> = { data?: T; error?: unknown; response: Response }

export async function unwrap<T>(promise: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await promise
  if (!response.ok) throw new ApiError(response.status, detailMessage((error as { detail?: unknown })?.detail))
  return data as T
}
