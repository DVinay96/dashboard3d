import type { components } from './schema'

type S = components['schemas']

export type Me = S['MeOut']
export type ClientBrief = S['ClientBrief']
export type Client = S['ClientOut']
export type Project = S['ProjectOut']
export type ProjectRef = S['ProjectRef']
export type Product = S['ProductOut']
export type Role = S['RoleOut']
export type User = S['UserOut']
export type UserRef = S['UserRef']
export type Catalog = S['CatalogOut']
export type Brand = S['BrandOut']
export type BrandFields = S['BrandFieldsOut']
export type ModuleInfo = S['ModuleOut']
export type DevIdentities = S['DevIdentities']
export type AccessRow = S['AccessRow']
export type PlatformSettings = S['PlatformSettings']
export type UnitySync = S['UnitySyncOut']
export type Integration = S['IntegrationOut']
export type SetupStep = S['SetupStep']
export type IntegrationEvent = S['EventInfo']

export type Statement = {
  effect: 'allow' | 'deny'
  actions: string[]
  resources: string[]
}

export type FieldDef = {
  key: string
  label: string
  type: 'text' | 'number' | 'select' | 'bool' | 'date'
  required: boolean
  options: string[]
  default: string | boolean
  help: string
  scope?: 'base' | 'brand'
}

export interface QaCheck {
  level: 'pass' | 'warn' | 'fail' | 'info'
  msg: string
}
export interface QaSnapshot {
  tris?: number
  verts?: number
  quads?: number
  uv_layers?: string[]
  dimensions_m?: number[]
  bbox_min?: number[]
  surface_area_m2?: number
  sliver_pct?: number
  loose_parts?: number
  boundary_edges?: number
  materials?: unknown[]
  uv_stats?: { packing_pct?: number }
}
export interface QaMetrics {
  checks?: QaCheck[]
  actions?: string[]
  renders?: string[]
  uv_render?: string
  exported?: Record<string, string>
  before?: QaSnapshot
  after?: QaSnapshot
}

export const ACTIVE_STATUSES = ['QUEUED', 'GENERATING', 'DOWNLOADING', 'CONDITIONING']

export const UNITY_ACTIVE = ['PENDING', 'SYNCING']
