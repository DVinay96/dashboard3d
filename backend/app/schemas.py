from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserRef(ORM):
    id: str
    email: str
    display_name: str


class ClientBrief(ORM):
    id: str
    name: str
    slug: str
    modules: list[str]
    theme: dict[str, Any]
    disabled: bool


class MeOut(BaseModel):
    user: UserRef
    is_super_admin: bool
    client: ClientBrief | None
    modules: list[str]
    can: list[str]
    auth_mode: str


class ModuleAction(BaseModel):
    name: str
    description: str


class ModuleOut(BaseModel):
    id: str
    label: str
    description: str
    actions: list[ModuleAction]


class DevIdentity(BaseModel):
    id: str
    email: str
    display_name: str
    client_id: str | None
    client_name: str | None
    is_super_admin: bool


class DevIdentities(BaseModel):
    users: list[DevIdentity]
    clients: list[ClientBrief]


class ClientOut(ClientBrief):
    created_at: float
    user_count: int = 0
    project_count: int = 0
    product_count: int = 0


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    modules: list[str] | None = None
    theme: dict[str, Any] | None = None


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    modules: list[str] | None = None
    theme: dict[str, Any] | None = None
    disabled: bool | None = None


class ProjectRef(ORM):
    id: str
    name: str


class ProjectOut(ORM):
    id: str
    client_id: str
    name: str
    description: str
    unity_project_id: str | None
    archived: bool
    created_at: float
    product_count: int = 0


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    archived: bool | None = None
    unity_project_id: str | None = Field(default=None, max_length=64)


class RoleOut(ORM):
    id: str
    client_id: str | None
    name: str
    description: str
    statements: list[dict[str, Any]]
    builtin: bool
    user_count: int = 0


class RoleIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=200)
    statements: list[dict[str, Any]]
    client_id: str | None = None


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    client_id: str | None
    client_name: str | None
    is_super_admin: bool
    disabled: bool
    role_ids: list[str]
    role_names: list[str]
    created_at: float


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    display_name: str = Field(default="", max_length=120)
    client_id: str | None = None
    role_ids: list[str] = []
    is_super_admin: bool = False


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    role_ids: list[str] | None = None
    disabled: bool | None = None


class BrandOut(BaseModel):
    id: str
    name: str
    slug: str
    notes: str
    fields: list[dict[str, Any]]
    pipeline: dict[str, Any]
    created_at: float


class CatalogOut(BaseModel):
    base_fields: list[dict[str, Any]]
    brands: list[BrandOut]


class BrandIn(BaseModel):
    name: str = ""
    notes: str = ""
    fields: list[dict[str, Any]] = []
    pipeline: dict[str, Any] = {}


class BaseFieldsIn(BaseModel):
    fields: list[dict[str, Any]] = []


class BrandFieldsOut(BaseModel):
    fields: list[dict[str, Any]]
    pipeline: dict[str, Any]


class UnitySyncOut(BaseModel):
    id: str
    product_id: str
    product_name: str
    project_id: str
    project_name: str
    unity_project_id: str
    status: str
    error: str | None
    attempts: int
    unity_asset_id: str | None
    created_at: float
    updated_at: float
    synced_at: float | None


class UnityStatusOut(BaseModel):
    configured: bool
    items: list[UnitySyncOut]


class ProductOut(BaseModel):
    id: str
    client_id: str
    name: str
    slug: str
    status: str
    stage: str
    progress: int
    source: str
    brand_id: str | None
    brand_name: str
    parent_id: str | None
    retexture_prompt: str | None
    credits: float | None
    error: str | None
    options: dict[str, Any]
    metadata: dict[str, Any]
    photos: list[str]
    raw_files: dict[str, Any]
    textures: dict[str, Any]
    metrics: dict[str, Any] | None
    original_filename: str | None
    thumbnail_url: str | None
    created_by: UserRef | None
    projects: list[ProjectRef]
    unity: list[UnitySyncOut] = []
    created_at: float
    updated_at: float


class ProductsOut(BaseModel):
    products: list[ProductOut]


class AssignIn(BaseModel):
    project_ids: list[str] = Field(min_length=1)


class RetextureIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=800)


class PlatformSettings(BaseModel):
    blender_path: str
    blender_ok: bool
    unity_export_dir: str
    meshy_key_set: bool
    meshy_key_masked: str
    unity_configured: bool
    unity_api_base: str


class PlatformSettingsIn(BaseModel):
    blender_path: str | None = Field(default=None, max_length=500)
    unity_export_dir: str | None = Field(default=None, max_length=500)


class AccessRow(BaseModel):

    user_id: str
    email: str
    display_name: str
    client_id: str | None
    client_name: str | None
    is_super_admin: bool
    disabled: bool
    roles: list[str]
    client_modules: list[str]
    effective_modules: list[str]
    action_count: int


class SecretState(BaseModel):
    set: bool
    hint: str


class IntegrationOut(BaseModel):
    id: str
    kind: str
    name: str
    enabled: bool
    config: dict[str, Any]
    secrets: dict[str, SecretState]
    last_status: str | None
    last_message: str | None
    last_at: float | None


class EventInfo(BaseModel):
    name: str
    description: str


class IntegrationsOut(BaseModel):
    items: list[IntegrationOut]
    events: list[EventInfo]


class IntegrationCreate(BaseModel):
    kind: str
    name: str = Field(min_length=1, max_length=120)
    enabled: bool = True
    config: dict[str, Any] = {}
    secrets: dict[str, str] = {}


class IntegrationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    config: dict[str, Any] | None = None
    secrets: dict[str, str] | None = None
    clear_secrets: list[str] = []


class TestResult(BaseModel):
    ok: bool
    message: str


class SetupStep(BaseModel):
    id: str
    title: str
    detail: str
    done: bool
    link: str | None


class SetupOut(BaseModel):
    steps: list[SetupStep]
    ready: bool
