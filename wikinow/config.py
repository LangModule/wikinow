"""
Configuration module for WikiNow.

Config file: ~/.wikinow/config.yaml
Created with defaults on first run.
Missing keys merged from defaults on load (forward-compatible upgrades).
"""

import copy
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml


WIKINOW_DIR = Path.home() / ".wikinow"
CONFIG_PATH = WIKINOW_DIR / "config.yaml"


# ── Env Var Mapping ───────────────────────────────────────────────────────

ENV_VARS: dict[str, str] = {
    "ollama.api_key": "OLLAMA_API_KEY",
    "ingestion.jina_api_key": "JINA_API_KEY",
}


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OllamaConfig:
    """Ollama API configuration."""

    api_key: str = ""


@dataclass(frozen=True)
class WhisperConfig:
    """Whisper configuration — local speech-to-text."""

    model: str = "turbo"


@dataclass(frozen=True)
class IngestionConfig:
    """Source ingestion configuration."""

    jina_api_key: str = ""
    auto_compile: bool = True
    auto_watch: bool = False


@dataclass(frozen=True)
class SearchConfig:
    """Search configuration."""

    max_results: int = 10


@dataclass(frozen=True)
class ProjectsConfig:
    """Project management configuration."""

    active: str = ""


@dataclass(frozen=True)
class WikiNowConfig:
    """Complete WikiNow configuration."""

    projects: ProjectsConfig = field(default_factory=ProjectsConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)
    search: SearchConfig = field(default_factory=SearchConfig)


# ── Helpers ───────────────────────────────────────────────────────────────


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base recursively. Override values win."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _resolve_env(key: str, value: str) -> str:
    """Return env var value if mapped and set, otherwise return config value."""
    env_var = ENV_VARS.get(key)
    if env_var:
        env_value = os.environ.get(env_var)
        if env_value:
            return env_value
    return value


def _set_nested(data: dict, key: str, value: object) -> None:
    """Set a value in nested dict by dot-notation key."""
    parts = key.split(".")
    node = data
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            node[part] = {}
        node = node[part]
    node[parts[-1]] = value


def _coerce_value(raw: str) -> object:
    """Coerce a CLI string value to the appropriate Python type."""
    if raw.lower() in ("true", "yes"):
        return True
    if raw.lower() in ("false", "no"):
        return False
    try:
        return int(raw)
    except ValueError:
        return raw


# ── Builder ───────────────────────────────────────────────────────────────


def _build_config(data: dict) -> WikiNowConfig:
    """Build typed WikiNowConfig from raw YAML dict with env var resolution."""
    ollama = data.get("ollama") or {}
    whisper = data.get("whisper") or {}
    ingestion = data.get("ingestion") or {}
    search = data.get("search") or {}
    projects = data.get("projects") or {}

    return WikiNowConfig(
        projects=ProjectsConfig(
            active=projects.get("active") or "",
        ),
        ollama=OllamaConfig(
            api_key=_resolve_env("ollama.api_key", ollama.get("api_key") or ""),
        ),
        whisper=WhisperConfig(
            model=whisper.get("model") or "turbo",
        ),
        ingestion=IngestionConfig(
            jina_api_key=_resolve_env(
                "ingestion.jina_api_key", ingestion.get("jina_api_key") or ""
            ),
            auto_compile=ingestion.get("auto_compile", True),
            auto_watch=ingestion.get("auto_watch", False),
        ),
        search=SearchConfig(
            max_results=search.get("max_results", 10),
        ),
    )


# ── Config Manager ────────────────────────────────────────────────────────


class ConfigManager:
    """Manages WikiNow configuration (load, save, update)."""

    def __init__(self) -> None:
        self._raw: dict = {}
        self._config: WikiNowConfig | None = None
        self._load()

    def _load(self) -> None:
        """Load config from disk, creating with defaults if missing."""
        defaults = asdict(WikiNowConfig())

        if not CONFIG_PATH.exists():
            WIKINOW_DIR.mkdir(parents=True, exist_ok=True)
            self._raw = copy.deepcopy(defaults)
            self._save()
        else:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                try:
                    loaded = yaml.safe_load(f)
                    file_data = loaded if isinstance(loaded, dict) else {}
                except yaml.YAMLError:
                    file_data = {}
            self._raw = _deep_merge(copy.deepcopy(defaults), file_data)

        self._config = _build_config(self._raw)

    def _save(self) -> None:
        """Write current config to disk."""
        WIKINOW_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(self._raw, f, default_flow_style=False, sort_keys=False)

    def reload(self) -> None:
        """Re-read config from disk."""
        self._load()

    @property
    def config(self) -> WikiNowConfig:
        """Get the typed config."""
        assert self._config is not None
        return self._config

    def set(self, key: str, value: str) -> None:
        """Set a config value by dot-notation key and save to disk."""
        _set_nested(self._raw, key, _coerce_value(value))
        self._save()
        self._config = _build_config(self._raw)

    def project_path(self, name: str | None = None) -> Path:
        """Return the path for a project. Uses active project if name is None."""
        project = name or self.config.projects.active
        if not project:
            raise ValueError(
                "No active project. Run 'wn init <name>' or 'wn use <name>'."
            )
        return WIKINOW_DIR / project

    def list_projects(self) -> list[str]:
        """Return names of all projects."""
        if not WIKINOW_DIR.exists():
            return []
        return sorted(
            d.name
            for d in WIKINOW_DIR.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )


# ── Module-level singleton ────────────────────────────────────────────────

_manager: ConfigManager | None = None


def _get_manager() -> ConfigManager:
    """Get or create the ConfigManager singleton."""
    global _manager
    if _manager is None:
        _manager = ConfigManager()
    return _manager


# ── Public accessors ──────────────────────────────────────────────────────


def get_config() -> WikiNowConfig:
    """Get the complete WikiNow configuration."""
    return _get_manager().config


def get_ollama_config() -> OllamaConfig:
    """Get Ollama configuration."""
    return _get_manager().config.ollama


def get_whisper_config() -> WhisperConfig:
    """Get Whisper configuration."""
    return _get_manager().config.whisper


def get_ingestion_config() -> IngestionConfig:
    """Get ingestion configuration."""
    return _get_manager().config.ingestion


def get_search_config() -> SearchConfig:
    """Get search configuration."""
    return _get_manager().config.search


def get_active_project() -> str:
    """Get the active project name."""
    return _get_manager().config.projects.active


def get_project_path(name: str | None = None) -> Path:
    """Get the path for a project."""
    return _get_manager().project_path(name)


def list_projects() -> list[str]:
    """List all project names."""
    return _get_manager().list_projects()


def set_config(key: str, value: str) -> None:
    """Set a config value and save to disk."""
    _get_manager().set(key, value)


def reload_config() -> None:
    """Re-read config from disk."""
    _get_manager().reload()
