"""
Load manifests/batch-ingest.yml into typed config objects.

.env file at the vault root is loaded automatically if present, so
ANTHROPIC_API_KEY (and other provider keys) can be set there without
exporting them to the shell environment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError as exc:
    raise ImportError("pyyaml is required: pip install pyyaml") from exc

VAULT_ROOT = Path(__file__).parent.parent.parent
CONFIG_PATH = VAULT_ROOT / "manifests" / "batch-ingest.yml"


def _load_dotenv(vault_root: Path = VAULT_ROOT) -> None:
    """Load .env from vault root if present. Never overrides existing env vars."""
    env_file = vault_root / ".env"
    if not env_file.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file, override=False)
    except ImportError:
        # Manual parse if python-dotenv is not installed
        import os
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


# Load .env at import time so every module that imports config gets the keys.
_load_dotenv()


@dataclass
class ModelsConfig:
    extraction: str = "claude-haiku-4-5-20251001"
    resolution: str = "claude-sonnet-5"
    curation: str = "claude-sonnet-5"
    curation_new: str = "claude-haiku-4-5-20251001"


@dataclass
class TokensConfig:
    extraction_max_output: int = 6000
    resolution_max_output: int = 1500
    curation_max_output: int = 6000


@dataclass
class CacheConfig:
    enabled: bool = True
    ttl: str = "1h"


@dataclass
class ProviderBatchConfig:
    max_requests: int = 5000
    max_payload_mb: int = 200
    max_retries: int = 2


@dataclass
class ChunkingConfig:
    enabled: bool = True
    target_tokens: int = 100_000
    overlap_tokens: int = 1500


@dataclass
class ResolutionConfig:
    fuzzy_auto_threshold: float = 0.97
    max_candidates: int = 5


@dataclass
class QualityConfig:
    sample_rate: float = 0.10
    min_sample_size: int = 20
    max_sample_size: int = 100
    require_all_extractions_valid: bool = True
    critical_claim_locator_rate: float = 1.0
    minimum_claim_locator_rate: float = 0.95
    allow_deferred_resolution: bool = True
    allow_unresolved_provider_errors: bool = False


@dataclass
class ApplyConfig:
    require_clean_git: bool = True
    optimistic_locking: bool = True


@dataclass
class ModelResolutionConfig:
    extraction_keyword: str = "haiku"
    resolution_keyword: str = "sonnet"
    curation_keyword: str = "sonnet"


@dataclass
class BatchIngestConfig:
    schema_version: str = "1"
    # "anthropic" → Anthropic Message Batches API (default, async, 50% discount)
    # "litellm"   → synchronous litellm calls (any provider, no batch discount)
    provider: str = "anthropic"
    wiki_language: str = "source"
    models: ModelsConfig = field(default_factory=ModelsConfig)
    model_resolution: ModelResolutionConfig = field(default_factory=ModelResolutionConfig)
    tokens: TokensConfig = field(default_factory=TokensConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    provider_batch: ProviderBatchConfig = field(default_factory=ProviderBatchConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    resolution: ResolutionConfig = field(default_factory=ResolutionConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    apply: ApplyConfig = field(default_factory=ApplyConfig)


def _nested(cls, data: dict):
    """Instantiate a dataclass from a dict, ignoring unknown keys."""
    import dataclasses

    known = {f.name for f in dataclasses.fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in known})


def load_config(path: Path = CONFIG_PATH) -> BatchIngestConfig:
    if not path.exists():
        return BatchIngestConfig()

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    cfg = BatchIngestConfig()
    cfg.schema_version = str(raw.get("schema_version", "1"))
    cfg.provider = str(raw.get("provider", "anthropic"))
    cfg.wiki_language = str(raw.get("wiki_language", "source"))

    if m := raw.get("models"):
        cfg.models = _nested(ModelsConfig, m)
    if t := raw.get("tokens"):
        cfg.tokens = _nested(TokensConfig, t)
    if c := raw.get("cache"):
        cfg.cache = _nested(CacheConfig, c)
    if pb := raw.get("provider_batch"):
        cfg.provider_batch = _nested(ProviderBatchConfig, pb)
    if ch := raw.get("chunking"):
        cfg.chunking = _nested(ChunkingConfig, ch)
    if r := raw.get("resolution"):
        cfg.resolution = _nested(ResolutionConfig, r)
    if q := raw.get("quality"):
        cfg.quality = _nested(QualityConfig, q)
    if a := raw.get("apply"):
        cfg.apply = _nested(ApplyConfig, a)
    if mr := raw.get("model_resolution"):
        cfg.model_resolution = _nested(ModelResolutionConfig, mr)

    return cfg


# ---------------------------------------------------------------------------
# Proxy model resolution
# ---------------------------------------------------------------------------

_resolved_models: dict[str, str] = {}


def resolve_model_names(cfg: "BatchIngestConfig", vault_root: Path = VAULT_ROOT) -> None:
    """
    When running through a proxy (ANTHROPIC_BASE_URL set), query the proxy's
    /v1/models endpoint and replace model names in cfg.models with the first
    available model whose id contains the configured keyword.

    Mutates cfg.models in-place. Idempotent (cached after first call).
    No-op when ANTHROPIC_BASE_URL is not set (direct Anthropic).
    """
    import os

    base_url = os.environ.get("ANTHROPIC_BASE_URL", "").rstrip("/")
    if not base_url:
        return  # direct Anthropic — use model names as configured

    global _resolved_models
    if _resolved_models:
        # Apply cached results
        if "extraction" in _resolved_models:
            cfg.models.extraction = _resolved_models["extraction"]
        if "resolution" in _resolved_models:
            cfg.models.resolution = _resolved_models["resolution"]
        if "curation" in _resolved_models:
            cfg.models.curation = _resolved_models["curation"]
        return

    try:
        import ssl
        import urllib.request
        import json

        token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        req = urllib.request.Request(
            f"{base_url}/v1/models",
            headers={"Authorization": f"Bearer {token}"} if token else {},
        )
        # Proxy may use a self-signed / corporate CA cert — skip verification for
        # this internal catalog query (read-only, no credentials sent in body).
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
            data = json.loads(resp.read())
        model_ids: list[str] = [m["id"] for m in data.get("data", [])]
    except Exception:
        return  # proxy unreachable — leave configured names unchanged

    def _pick(keyword: str) -> str | None:
        kw = keyword.lower()
        # Prefer anthropic.* prefix when on Anthropic proxy
        for mid in model_ids:
            if "anthropic." in mid.lower() and kw in mid.lower():
                return mid
        for mid in model_ids:
            if kw in mid.lower():
                return mid
        return None

    mr = cfg.model_resolution
    for role, keyword, attr in [
        ("extraction",   mr.extraction_keyword, "extraction"),
        ("resolution",   mr.resolution_keyword, "resolution"),
        ("curation",     mr.curation_keyword,   "curation"),
        ("curation_new", mr.extraction_keyword, "curation_new"),  # same tier as extraction
    ]:
        resolved = _pick(keyword)
        if resolved:
            _resolved_models[role] = resolved
            setattr(cfg.models, attr, resolved)
        else:
            _resolved_models[role] = getattr(cfg.models, attr)  # keep original
