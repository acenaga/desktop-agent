"""
config.py: Esquema y carga de configuración de LocalDesk.
"""

from pathlib import Path
from typing import Optional, List
import yaml
from pydantic import BaseModel, Field


class InferenceConfig(BaseModel):
    provider: str = "ollama"
    base_url: str = "http://127.0.0.1:11434"
    model_id: Optional[str] = None
    context_tokens: int = 8192
    request_timeout_seconds: int = 120
    cloud_fallback: bool = False
    require_local_execution: bool = True


class ExecutionConfig(BaseModel):
    max_active_tasks: int = 1
    max_steps: int = 40
    max_active_seconds: int = 600
    tool_timeout_seconds: int = 15
    max_read_retries: int = 2
    max_no_progress_steps: int = 3
    desktop_adapter: str = "windows_uia"
    visual_fallback_enabled: bool = False


class PermissionsConfig(BaseModel):
    read_roots: List[str] = Field(default_factory=list)
    write_roots: List[str] = Field(default_factory=list)
    allowed_apps: List[str] = Field(default_factory=list)
    allowed_origins: List[str] = Field(default_factory=list)
    permanent_delete_enabled: bool = False
    arbitrary_shell_enabled: bool = False


class NetworkConfig(BaseModel):
    mode: str = "offline"
    bind_host: str = "127.0.0.1"
    bind_port: int = 0
    external_integration_enabled: bool = False


class PrivacyConfig(BaseModel):
    telemetry_enabled: bool = False
    persist_screenshots: bool = False
    log_full_document_contents: bool = False
    history_retention_days: int = 30


class AppConfig(BaseModel):
    schema_version: int = 1
    inference: InferenceConfig = Field(default_factory=InferenceConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)

    @classmethod
    def load_from_yaml(cls, path: str | Path) -> "AppConfig":
        p = Path(path)
        if not p.exists():
            return cls()
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls.model_validate(data)

    def save_to_yaml(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.model_dump(), f, default_flow_style=False, sort_keys=False)
