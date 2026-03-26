from dataclasses import dataclass


@dataclass(frozen=True)
class TenantScope:
    club_id: str | None = None
    tenant_mode: str = "stage1_single_tenant"
    tenant_resolved: bool = False
