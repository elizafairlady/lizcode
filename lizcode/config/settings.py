"""Settings management for LizCode."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """LizCode configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="LIZCODE_",
        env_file=".env",
        extra="ignore",
    )

    # Provider settings
    provider: Literal["openrouter", "ollama"] = Field(
        default="openrouter",
        description="Default model provider",
    )

    # OpenRouter settings
    openrouter_api_key: str | None = Field(
        default=None,
        description="OpenRouter API key",
    )
    openrouter_model: str = Field(
        default="anthropic/claude-sonnet-4",
        description="Default OpenRouter model",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API base URL",
    )

    # Ollama settings
    ollama_host: str = Field(
        default="http://localhost:11434",
        description="Ollama server host",
    )
    ollama_model: str = Field(
        default="llama3.2",
        description="Default Ollama model",
    )

    # Mode settings
    default_mode: Literal["plan", "act"] = Field(
        default="act",
        description="Default mode when starting LizCode",
    )

    # UI settings
    streaming: bool = Field(
        default=True,
        description="Enable streaming responses",
    )

    # Paths
    config_dir: Path = Field(
        default_factory=lambda: Path.home() / ".lizcode",
        description="Configuration directory",
    )

    @classmethod
    def load_from_yaml(cls, config_path: Path | None = None) -> Settings:
        """Load settings from YAML config file, with environment variable overrides."""
        config_path = config_path or Path.home() / ".lizcode" / "config.yaml"

        yaml_config = {}
        if config_path.exists():
            with open(config_path) as f:
                yaml_config = yaml.safe_load(f) or {}

        # Also check for OPENROUTER_API_KEY without prefix (common convention)
        if not yaml_config.get("openrouter_api_key"):
            yaml_config["openrouter_api_key"] = os.environ.get("OPENROUTER_API_KEY")

        return cls(**yaml_config)

    def save_to_yaml(self, config_path: Path | None = None) -> Path:
        """Save settings to YAML config file."""
        config_path = config_path or Path.home() / ".lizcode" / "config.yaml"
        
        # Create config dict from current settings
        config_data = {
            "provider": self.provider,
            "openrouter_model": self.openrouter_model,
            "openrouter_base_url": self.openrouter_base_url,
            "ollama_host": self.ollama_host,
            "ollama_model": self.ollama_model,
            "default_mode": self.default_mode,
            "streaming": self.streaming,
        }
        
        # Only include API key if it's set
        if self.openrouter_api_key:
            config_data["openrouter_api_key"] = self.openrouter_api_key
            
        # Write to file
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            yaml.safe_dump(config_data, f, default_flow_style=False)
            
        return config_path


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings.load_from_yaml()


def create_default_config() -> Path:
    """Create default configuration file if it doesn't exist."""
    config_dir = Path.home() / ".lizcode"
    config_path = config_dir / "config.yaml"

    if not config_dir.exists():
        config_dir.mkdir(parents=True)

    if not config_path.exists():
        default_config = """\
# LizCode Configuration
# See https://github.com/vii/lizcode for documentation

# Model provider: "openrouter" or "ollama"
provider: openrouter

# OpenRouter settings
# Get your API key at https://openrouter.ai/keys
# openrouter_api_key: your-api-key-here
openrouter_model: anthropic/claude-sonnet-4

# Ollama settings (for local models)
ollama_host: http://localhost:11434
ollama_model: llama3.2

# Default mode: "plan" or "act"
default_mode: act

# Enable streaming responses
streaming: true
"""
        config_path.write_text(default_config)

    return config_path
