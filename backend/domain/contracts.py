from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Settings(StrictModel):
    profile: Literal['low_vram', 'balanced', 'performance'] = 'low_vram'
    target_engine: Literal['unreal', 'generic'] = 'unreal'
    comfy_port: int = Field(default=8188, ge=1024, le=65535)
    checkpoint: str = Field(default='', max_length=240)
    model_license: str = Field(default='', max_length=100)
    model_version: str = Field(default='', max_length=100)
    license_reviewed: bool = False
    # Local configuration only; no executable paths accepted over HTTP.


PROFILES = {
    'low_vram': {'width': 512, 'height': 512, 'steps': 4, 'gpu_workers': 1, 'unload': True, 'pixel_ratio': 1},
    'balanced': {'width': 768, 'height': 768, 'steps': 4, 'gpu_workers': 1, 'unload': True, 'pixel_ratio': 1.5},
    'performance': {'width': 1024, 'height': 1024, 'steps': 4, 'gpu_workers': 1, 'unload': False, 'pixel_ratio': 2},
}


class Generate(StrictModel):
    project_id: UUID
    prompt: str = Field(min_length=1, max_length=4000)
    reference_id: UUID | None = None
    sketch_id: UUID | None = None
    seed: int | None = Field(default=None, ge=0, le=2**53-1)
    priority: Literal['interactive', 'normal', 'background'] = 'normal'

    @field_validator('prompt')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('Escreva sua ideia antes de gerar.')
        return value.strip()


class AssetUpdate(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=20)
    favorite: bool = False
    archived: bool = False

    @field_validator('name')
    @classmethod
    def nonempty(cls, value):
        if not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError('Nome inválido')
        return value.strip()

    @field_validator('tags')
    @classmethod
    def safe_tags(cls, tags):
        if any(not tag.strip() or len(tag) > 40 for tag in tags):
            raise ValueError('Tags devem ter entre 1 e 40 caracteres')
        return sorted(set(tag.strip() for tag in tags))


class ExportRequest(StrictModel):
    format: Literal['glb', 'fbx', 'zip', 'unreal'] = 'glb'
    version_id: UUID | None = None


class RestoreRequest(StrictModel):
    version_id: UUID


class Effect(StrictModel):
    schema_version: Literal[1] = 1
    type: Literal['particles'] = 'particles'
    emitter: Literal['point', 'sphere'] = 'point'
    count: int = Field(default=200, ge=1, le=2000)
    lifetime: float = Field(default=3, ge=.1, le=30)
    speed: float = Field(default=1, ge=0, le=20)
    size: float = Field(default=.06, ge=.005, le=2)
    color: str = Field(default='#b9ed83', pattern=r'^#[0-9a-fA-F]{6}$')
    duration: float = Field(default=5, ge=.1, le=120)
    looping: bool = True
    seed: int = Field(default=42, ge=0, le=2**31-1)
    position: tuple[float, float, float] = (0, 0, 0)
    attachment: UUID | None = None
