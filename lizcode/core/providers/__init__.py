"""Model providers for LizCode."""

from lizcode.core.providers.base import Provider
from lizcode.core.providers.ollama import OllamaProvider
from lizcode.core.providers.openrouter import OpenRouterProvider

__all__ = ["Provider", "OpenRouterProvider", "OllamaProvider"]


def get_provider(provider_name: str, **kwargs) -> Provider:
    """Factory function to get a provider by name."""
    providers = {
        "openrouter": OpenRouterProvider,
        "ollama": OllamaProvider,
    }

    if provider_name not in providers:
        raise ValueError(f"Unknown provider: {provider_name}. Available: {list(providers.keys())}")

    return providers[provider_name](**kwargs)
