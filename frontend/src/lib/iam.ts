import type { ModuleInfo, Statement } from '@/api/types'

export function parseLines(text: string): string[] {
  return [...new Set(text.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean))]
}

export function projectResources(projectId: string): string[] {
  return [`project/${projectId}`, `project/${projectId}/*`]
}

export function brandResource(brandId: string): string {
  return `brand/${brandId}`
}

export function emptyStatement(): Statement {
  return { effect: 'allow', actions: [], resources: ['*'] }
}

export function actionModules(modules: ModuleInfo[]): Record<string, string> {
  const out: Record<string, string> = {}
  for (const m of modules) for (const a of m.actions) out[a.name] = m.id
  return out
}

export function statementProblems(statements: Statement[]): string | null {
  if (!statements.length) return 'Un rol necesita al menos un statement.'
  for (const [i, s] of statements.entries()) {
    if (!s.actions.length) return `El statement ${i + 1} no tiene acciones.`
    if (!s.resources.length) return `El statement ${i + 1} no tiene recursos.`
  }
  return null
}
