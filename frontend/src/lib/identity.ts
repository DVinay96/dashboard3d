export interface Identity {
  actAs: string | null
  clientId: string | null
}

const KEY = 'pipeline3d.identity'
const COOKIES = { actAs: 'x-act-as', clientId: 'x-client-id' } as const

function read(): Identity {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? '{}') as Partial<Identity>
    return { actAs: raw.actAs ?? null, clientId: raw.clientId ?? null }
  } catch {
    return { actAs: null, clientId: null }
  }
}

function writeCookies(id: Identity) {
  for (const [field, name] of Object.entries(COOKIES) as [keyof Identity, string][]) {
    const value = id[field]
    document.cookie = value
      ? `${name}=${encodeURIComponent(value)}; path=/; SameSite=Strict`
      : `${name}=; path=/; max-age=0; SameSite=Strict`
  }
}

let current = read()
const listeners = new Set<() => void>()
writeCookies(current)

export const getIdentity = () => current

export function setIdentity(patch: Partial<Identity>) {
  current = { ...current, ...patch }
  try {
    localStorage.setItem(KEY, JSON.stringify(current))
  } catch {
  }
  writeCookies(current)
  listeners.forEach((l) => l())
}

export function subscribeIdentity(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
