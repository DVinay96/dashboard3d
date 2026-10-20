import { useMutation, useQuery, useQueryClient, type QueryKey } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, ApiError, detailMessage, identityHeaders, unwrap } from './client'
import { ACTIVE_STATUSES, UNITY_ACTIVE, type BrandFields, type Catalog, type Product, type Statement } from './types'
import type { components } from './schema'

type S = components['schemas']

export const useMe = () => useQuery({ queryKey: ['me'], queryFn: () => unwrap(api.GET('/api/me')), retry: false })
export const useModules = () =>
  useQuery({ queryKey: ['modules'], queryFn: () => unwrap(api.GET('/api/modules')), staleTime: Infinity })
export const useDevIdentities = () =>
  useQuery({ queryKey: ['dev-identities'], queryFn: () => unwrap(api.GET('/api/dev/identities')), retry: false })

export const useClients = () => useQuery({ queryKey: ['clients'], queryFn: () => unwrap(api.GET('/api/clients')) })
export const useUsers = (clientId?: string) =>
  useQuery({
    queryKey: ['users', clientId ?? 'all'],
    queryFn: () => unwrap(api.GET('/api/users', { params: { query: { client_id: clientId } } })),
  })
export const useRoles = (clientId?: string) =>
  useQuery({
    queryKey: ['roles', clientId ?? 'all'],
    queryFn: () => unwrap(api.GET('/api/roles', { params: { query: { client_id: clientId } } })),
  })
export const useAccess = () => useQuery({ queryKey: ['access'], queryFn: () => unwrap(api.GET('/api/access')) })
export const usePlatform = () =>
  useQuery({ queryKey: ['platform'], queryFn: () => unwrap(api.GET('/api/platform/settings')) })

export const useProjects = () => useQuery({ queryKey: ['projects'], queryFn: () => unwrap(api.GET('/api/projects')) })
export const useProjectsOf = (clientId: string | null | undefined) =>
  useQuery({
    queryKey: ['projects-of', clientId],
    enabled: !!clientId,
    queryFn: () => unwrap(api.GET('/api/projects', { headers: { 'X-Client-Id': clientId! } })),
  })

export const useCatalog = (enabled = true) =>
  useQuery({
    queryKey: ['catalog'],
    enabled,
    queryFn: () => unwrap<Catalog>(api.GET('/api/brands')),
  })
export const useBrandFields = (brandId: string, enabled = true) =>
  useQuery({
    queryKey: ['brand-fields', brandId || 'none'],
    enabled,
    queryFn: () =>
      unwrap(api.GET('/api/brands/{brand_id}/fields', { params: { path: { brand_id: brandId || 'none' } } })) as Promise<BrandFields>,
  })

export const useProducts = (projectId?: string) =>
  useQuery({
    queryKey: ['products', projectId ?? 'all'],
    queryFn: () => unwrap(api.GET('/api/products', { params: { query: { project_id: projectId } } })),
    select: (d) => d.products,
    refetchInterval: (q) => (q.state.data?.products.some((p) => ACTIVE_STATUSES.includes(p.status)) ? 2000 : 10000),
  })

export const useSetup = () => useQuery({ queryKey: ['setup'], queryFn: () => unwrap(api.GET('/api/platform/setup')) })

export const useIntegrations = () =>
  useQuery({ queryKey: ['integrations'], queryFn: () => unwrap(api.GET('/api/integrations')) })

export const useUnityStatus = () =>
  useQuery({
    queryKey: ['unity-status'],
    queryFn: () => unwrap(api.GET('/api/unity/status')),
    refetchInterval: (q) => (q.state.data?.items.some((i) => UNITY_ACTIVE.includes(i.status)) ? 2000 : 15000),
  })

export async function fetchLog(pid: string): Promise<string> {
  const r = await fetch(`/api/products/${pid}/log`, { headers: identityHeaders() })
  if (!r.ok) throw new ApiError(r.status, 'No se pudo leer el log')
  return r.text()
}

interface ActionOptions<V, O> {
  invalidate?: QueryKey[]
  success?: string | ((out: O, vars: V) => string)
}

export function useAction<V, O>(fn: (vars: V) => Promise<O>, opts: ActionOptions<V, O> = {}) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (out, vars) => {
      for (const key of opts.invalidate ?? []) void qc.invalidateQueries({ queryKey: key })
      if (opts.success) toast.success(typeof opts.success === 'function' ? opts.success(out, vars) : opts.success)
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Algo salió mal'),
  })
}

const PRODUCTS: QueryKey = ['products']
const PROJECTS: QueryKey = ['projects']
const CATALOG: QueryKey = ['catalog']

export async function createProduct(form: FormData): Promise<Product> {
  const r = await fetch('/api/products', { method: 'POST', body: form, headers: identityHeaders() })
  const j = (await r.json().catch(() => ({}))) as { detail?: unknown }
  if (!r.ok) throw new ApiError(r.status, detailMessage(j.detail))
  return j as unknown as Product
}

export const useCreateProduct = () =>
  useAction(createProduct, { invalidate: [PRODUCTS, PROJECTS], success: (p) => `En cola: ${p.name}` })
export const useRetexture = () =>
  useAction((v: { id: string; prompt: string }) => unwrap(api.POST('/api/products/{pid}/retexture', { params: { path: { pid: v.id } }, body: { prompt: v.prompt } })), {
    invalidate: [PRODUCTS, PROJECTS],
    success: (p) => `En cola: ${p.name}`,
  })
export const useRetry = () =>
  useAction((id: string) => unwrap(api.POST('/api/products/{pid}/retry', { params: { path: { pid: id } } })), {
    invalidate: [PRODUCTS],
    success: 'Reprocesando',
  })
export const useDeleteProduct = () =>
  useAction((id: string) => unwrap(api.DELETE('/api/products/{pid}', { params: { path: { pid: id } } })), {
    invalidate: [PRODUCTS, PROJECTS],
    success: 'Producto borrado',
  })
export const useAssignProjects = () =>
  useAction((v: { id: string; projectIds: string[] }) => unwrap(api.PUT('/api/products/{pid}/projects', { params: { path: { pid: v.id } }, body: { project_ids: v.projectIds } })), {
    invalidate: [PRODUCTS, PROJECTS],
    success: 'Proyectos actualizados',
  })

export const useSaveIntegration = () =>
  useAction((v: { id: string; body: Partial<S['IntegrationUpdate']> }) => unwrap(api.PUT('/api/integrations/{integration_id}', { params: { path: { integration_id: v.id } }, body: { clear_secrets: [], ...v.body } })), {
    invalidate: [['integrations'], ['platform']],
    success: 'Integración guardada',
  })
export const useCreateIntegration = () =>
  useAction((body: Partial<S['IntegrationCreate']> & Pick<S['IntegrationCreate'], 'kind' | 'name'>) => unwrap(api.POST('/api/integrations', { body: { enabled: true, config: {}, secrets: {}, ...body } })), { invalidate: [['integrations']], success: 'Conector agregado' })
export const useDeleteIntegration = () =>
  useAction((id: string) => unwrap(api.DELETE('/api/integrations/{integration_id}', { params: { path: { integration_id: id } } })), {
    invalidate: [['integrations']],
    success: 'Conector borrado',
  })
export const useTestIntegration = () =>
  useAction((id: string) => unwrap(api.POST('/api/integrations/{integration_id}/test', { params: { path: { integration_id: id } } })), {
    invalidate: [['integrations'], ['platform']],
  })

export const useUnitySync = () =>
  useAction((id: string) => unwrap(api.POST('/api/products/{pid}/unity/sync', { params: { path: { pid: id } } })), {
    invalidate: [PRODUCTS, ['unity-status']],
    success: 'Sincronizando con Unity',
  })

export const useCreateProject = () =>
  useAction((body: S['ProjectCreate']) => unwrap(api.POST('/api/projects', { body })), { invalidate: [PROJECTS], success: 'Proyecto creado' })
export const useUpdateProject = () =>
  useAction((v: { id: string; body: S['ProjectUpdate'] }) => unwrap(api.PATCH('/api/projects/{project_id}', { params: { path: { project_id: v.id } }, body: v.body })), {
    invalidate: [PROJECTS, ['projects-of']],
    success: 'Proyecto guardado',
  })
export const useDeleteProject = () =>
  useAction((id: string) => unwrap(api.DELETE('/api/projects/{project_id}', { params: { path: { project_id: id } } })), { invalidate: [PROJECTS], success: 'Proyecto borrado' })

export const useSaveBrand = () =>
  useAction(
    (v: { id?: string; body: S['BrandIn'] }) =>
      v.id
        ? unwrap(api.PUT('/api/brands/{brand_id}', { params: { path: { brand_id: v.id } }, body: v.body }))
        : unwrap(api.POST('/api/brands', { body: v.body })),
    { invalidate: [CATALOG, ['brand-fields']], success: 'Marca guardada' },
  )
export const useDeleteBrand = () =>
  useAction((id: string) => unwrap(api.DELETE('/api/brands/{brand_id}', { params: { path: { brand_id: id } } })), {
    invalidate: [CATALOG, ['brand-fields']],
    success: 'Marca borrada',
  })
export const useSaveBaseFields = () =>
  useAction((fields: S['BaseFieldsIn']['fields']) => unwrap(api.PUT('/api/brands/base-fields', { body: { fields } })), {
    invalidate: [CATALOG, ['brand-fields']],
    success: 'Campos base guardados',
  })

const ADMIN: QueryKey[] = [['clients'], ['users'], ['roles'], ['access'], ['dev-identities']]
export const useCreateClient = () =>
  useAction((body: S['ClientCreate']) => unwrap(api.POST('/api/clients', { body })), { invalidate: ADMIN, success: 'Cliente creado' })
export const useUpdateClient = () =>
  useAction((v: { id: string; body: S['ClientUpdate']; silent?: boolean }) => unwrap(api.PATCH('/api/clients/{client_id}', { params: { path: { client_id: v.id } }, body: v.body })), {
    invalidate: [...ADMIN, ['me']],
  })
export const useDeleteClient = () =>
  useAction((id: string) => unwrap(api.DELETE('/api/clients/{client_id}', { params: { path: { client_id: id } } })), { invalidate: ADMIN, success: 'Cliente borrado' })
export const useCreateUser = () =>
  useAction((body: S['UserCreate']) => unwrap(api.POST('/api/users', { body })), { invalidate: ADMIN, success: 'Usuario creado' })
export const useUpdateUser = () =>
  useAction((v: { id: string; body: S['UserUpdate'] }) => unwrap(api.PATCH('/api/users/{user_id}', { params: { path: { user_id: v.id } }, body: v.body })), {
    invalidate: ADMIN,
    success: 'Usuario guardado',
  })
export const useDeleteUser = () =>
  useAction((id: string) => unwrap(api.DELETE('/api/users/{user_id}', { params: { path: { user_id: id } } })), { invalidate: ADMIN, success: 'Usuario borrado' })
export const useSaveRole = () =>
  useAction(
    (v: { id?: string; body: Omit<S['RoleIn'], 'statements'> & { statements: Statement[] } }) =>
      v.id
        ? unwrap(api.PUT('/api/roles/{role_id}', { params: { path: { role_id: v.id } }, body: v.body }))
        : unwrap(api.POST('/api/roles', { body: v.body })),
    { invalidate: ADMIN, success: 'Rol guardado' },
  )
export const useDeleteRole = () =>
  useAction((id: string) => unwrap(api.DELETE('/api/roles/{role_id}', { params: { path: { role_id: id } } })), { invalidate: ADMIN, success: 'Rol borrado' })
export const useSavePlatform = () =>
  useAction((body: S['PlatformSettingsIn']) => unwrap(api.PUT('/api/platform/settings', { body })), {
    invalidate: [['platform']],
    success: 'Ajustes guardados',
  })
