"""Tests for YAML config loading."""

import pytest
from pathlib import Path
from keypass_importer.config import AppConfig, MappingRule, load_config


class TestAppConfig:
    def test_minimal_config(self, tmp_path: Path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "tenant_url: https://mytenant.cyberark.cloud\n"
            "client_id: my-oidc-app\n"
        )
        config = load_config(cfg_file)
        assert config.tenant_url == "https://mytenant.cyberark.cloud"
        assert config.client_id == "my-oidc-app"
        assert config.mapping_mode == "single"
        assert config.default_platform is None

    def test_full_config(self, tmp_path: Path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "tenant_url: https://mytenant.cyberark.cloud\n"
            "client_id: my-oidc-app\n"
            "safe: Linux-Accounts\n"
            "mapping_mode: single\n"
            "default_platform: UnixSSH\n"
            "output_dir: ./reports\n"
        )
        config = load_config(cfg_file)
        assert config.safe == "Linux-Accounts"
        assert config.default_platform == "UnixSSH"
        assert config.output_dir == "./reports"

    def test_config_with_mapping_rules(self, tmp_path: Path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "tenant_url: https://t.cyberark.cloud\n"
            "client_id: app\n"
            "mapping_mode: config\n"
            "mapping_rules:\n"
            "  - group: Infrastructure/Linux\n"
            "    safe: Linux-Safe\n"
            "    platform: UnixSSH\n"
            "  - group: Infrastructure/Windows\n"
            "    safe: Windows-Safe\n"
            "    platform: WinServerLocal\n"
        )
        config = load_config(cfg_file)
        assert len(config.mapping_rules) == 2
        assert config.mapping_rules[0].group == "Infrastructure/Linux"
        assert config.mapping_rules[0].safe == "Linux-Safe"
        assert config.mapping_rules[0].platform == "UnixSSH"

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config(Path("/nonexistent/config.yaml"))

    def test_invalid_yaml_raises(self, tmp_path: Path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(": bad: yaml: [[[")
        with pytest.raises(ValueError, match="Invalid YAML"):
            load_config(cfg_file)

    def test_missing_required_fields(self, tmp_path: Path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("safe: OnlySafe\n")
        with pytest.raises(ValueError):
            load_config(cfg_file)


    def test_non_dict_yaml_raises(self, tmp_path: Path):
        """Line 43: YAML that parses to a non-dict raises ValueError."""
        cfg_file = tmp_path / "scalar.yaml"
        cfg_file.write_text('"hello"')
        with pytest.raises(ValueError, match="expected a mapping"):
            load_config(cfg_file)


class TestMappingRule:
    def test_basic_rule(self):
        rule = MappingRule(group="Web/Production", safe="Web-Safe")
        assert rule.group == "Web/Production"
        assert rule.safe == "Web-Safe"
        assert rule.platform is None
