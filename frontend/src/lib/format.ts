export const fmt = (n: number | null | undefined) => (n == null ? '-' : n.toLocaleString('es'))

export function fmtDate(ts: number | null | undefined): string {
  return ts ? new Date(ts * 1000).toLocaleString('es', { dateStyle: 'medium', timeStyle: 'short' }) : 'Nunca'
}

export type Tone = 'neutral' | 'accent' | 'ok' | 'warn' | 'fail'

export const STATUS: Record<string, { label: string; tone: Tone }> = {
  QUEUED: { label: 'En cola', tone: 'neutral' },
  GENERATING: { label: 'Generando', tone: 'accent' },
  DOWNLOADING: { label: 'Descargando', tone: 'accent' },
  CONDITIONING: { label: 'Blender', tone: 'accent' },
  DONE: { label: 'Listo', tone: 'ok' },
  QA_FAILED: { label: 'QA con fallos', tone: 'warn' },
  FAILED: { label: 'Falló', tone: 'fail' },
}
