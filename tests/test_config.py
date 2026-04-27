"""Tests for wikinow.config.

Verifies:
- Default config creation and values
- Set/reload operations with type coercion
- Forward compatibility (missing/extra keys)
- Resilience (corrupted YAML)
- Env var resolution and priority
- Frozen dataclass immutability

Usage:
    pytest tests/test_config.py -v
"""

import pytest
import yaml

from wikinow.config import (
    ConfigManager,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Redirect WIKINOW_DIR to a temp directory for every test.

    Ensures no test reads or writes the user's real ~/.wikinow/ config.
    Resets the module-level singleton so each test starts fresh.
    """
    test_dir = tmp_path / ".wikinow"
    monkeypatch.setattr("wikinow.config.WIKINOW_DIR", test_dir)
    monkeypatch.setattr("wikinow.config.CONFIG_PATH", test_dir / "config.yaml")
    monkeypatch.setattr("wikinow.config._manager", None)
    yield test_dir


# =============================================================================
# Default Config
# =============================================================================


class TestDefaultConfig:
    """Verify config.yaml is created with correct defaults on first run."""

    def test_creates_config_on_first_run(self, isolated_config):
        ConfigManager()
        assert (isolated_config / "config.yaml").exists()

    def test_default_ollama_api_key_empty(self, isolated_config):
        mgr = ConfigManager()
        assert mgr.config.ollama.api_key == ""

    def test_default_whisper_model_turbo(self, isolated_config):
        mgr = ConfigManager()
        assert mgr.config.whisper.model == "turbo"

    def test_default_auto_compile_true(self, isolated_config):
        mgr = ConfigManager()
        assert mgr.config.ingestion.auto_compile is True

    def test_default_max_results_10(self, isolated_config):
        mgr = ConfigManager()
        assert mgr.config.search.max_results == 10

    def test_default_active_project_empty(self, isolated_config):
        mgr = ConfigManager()
        assert mgr.config.projects.active == ""


# =============================================================================
# Set / Reload
# =============================================================================


class TestSetAndReload:
    """Verify config values persist across save/reload cycles."""

    def test_set_string_persists(self, isolated_config):
        mgr = ConfigManager()
        mgr.set("ollama.api_key", "test-key-123")
        assert mgr.config.ollama.api_key == "test-key-123"

        mgr2 = ConfigManager()
        assert mgr2.config.ollama.api_key == "test-key-123"

    def test_set_coerces_bool(self, isolated_config):
        mgr = ConfigManager()
        mgr.set("ingestion.auto_watch", "true")
        assert mgr.config.ingestion.auto_watch is True

        mgr.set("ingestion.auto_watch", "false")
        assert mgr.config.ingestion.auto_watch is False

    def test_set_coerces_int(self, isolated_config):
        mgr = ConfigManager()
        mgr.set("search.max_results", "20")
        assert mgr.config.search.max_results == 20

    def test_reload_picks_up_external_changes(self, isolated_config):
        mgr = ConfigManager()
        config_path = isolated_config / "config.yaml"

        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        data["whisper"]["model"] = "large-v3"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        mgr.reload()
        assert mgr.config.whisper.model == "large-v3"


# =============================================================================
# Forward Compatibility
# =============================================================================


class TestForwardCompatibility:
    """Verify config handles missing keys (upgrade) and extra keys (user custom)."""

    def test_missing_keys_get_defaults(self, isolated_config):
        config_path = isolated_config / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("ollama:\n  api_key: my-key\n", encoding="utf-8")

        mgr = ConfigManager()
        assert mgr.config.ollama.api_key == "my-key"
        assert mgr.config.whisper.model == "turbo"
        assert mgr.config.search.max_results == 10
        assert mgr.config.ingestion.auto_compile is True

    def test_extra_keys_preserved(self, isolated_config):
        config_path = isolated_config / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            "ollama:\n  api_key: key\ncustom:\n  foo: bar\n",
            encoding="utf-8",
        )

        mgr = ConfigManager()
        assert mgr.config.ollama.api_key == "key"
        assert mgr._raw.get("custom") == {"foo": "bar"}


# =============================================================================
# Resilience
# =============================================================================


class TestResilience:
    """Verify config handles corrupted or invalid YAML gracefully."""

    def test_corrupted_yaml_falls_back_to_defaults(self, isolated_config):
        config_path = isolated_config / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(":\n  broken: [invalid yaml\n", encoding="utf-8")

        mgr = ConfigManager()
        assert mgr.config.whisper.model == "turbo"
        assert mgr.config.search.max_results == 10

    def test_non_dict_yaml_falls_back_to_defaults(self, isolated_config):
        config_path = isolated_config / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("just a plain string\n", encoding="utf-8")

        mgr = ConfigManager()
        assert mgr.config.whisper.model == "turbo"
        assert mgr.config.search.max_results == 10


# =============================================================================
# Env Var Resolution
# =============================================================================


class TestEnvVarResolution:
    """Verify environment variables override config file values."""

    def test_ollama_key_from_env(self, isolated_config, monkeypatch):
        monkeypatch.setenv("OLLAMA_API_KEY", "env-ollama-key")
        mgr = ConfigManager()
        assert mgr.config.ollama.api_key == "env-ollama-key"

    def test_jina_key_from_env(self, isolated_config, monkeypatch):
        monkeypatch.setenv("JINA_API_KEY", "env-jina-key")
        mgr = ConfigManager()
        assert mgr.config.ingestion.jina_api_key == "env-jina-key"

    def test_env_var_wins_over_config(self, isolated_config, monkeypatch):
        mgr = ConfigManager()
        mgr.set("ollama.api_key", "from-config")

        monkeypatch.setenv("OLLAMA_API_KEY", "from-env")
        mgr2 = ConfigManager()
        assert mgr2.config.ollama.api_key == "from-env"


# =============================================================================
# Immutability
# =============================================================================


class TestImmutability:
    """Verify frozen dataclasses prevent accidental mutation."""

    def test_config_dataclasses_frozen(self, isolated_config):
        mgr = ConfigManager()

        with pytest.raises(AttributeError):
            mgr.config.ollama.api_key = "hacked"

        with pytest.raises(AttributeError):
            mgr.config.whisper.model = "hacked"

        with pytest.raises(AttributeError):
            mgr.config.search.max_results = 999

        with pytest.raises(AttributeError):
            mgr.config.projects.active = "hacked"
