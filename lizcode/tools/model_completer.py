"""Model tab completion for LizCode CLI."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Iterable

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

if TYPE_CHECKING:
    from lizcode.config.settings import Settings


class ModelCompleter(Completer):
    """Tab completer for model names with provider prefix support."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._model_cache: dict[str, list[str]] = {}
        self._cache_refresh_task: asyncio.Task | None = None

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """Provide completions for /model commands."""
        text = document.text_before_cursor
        
        # Only complete if we're in a /model command
        if not text.startswith("/model"):
            return
        
        # Get the part after "/model "
        if len(text) <= 7:  # "/model" length
            return
        
        if text[6] != " ":  # Should have space after /model
            return
            
        incomplete = text[7:]  # Everything after "/model "
        
        # Generate completions
        for completion in self._get_model_completions(incomplete):
            yield completion

    def _get_model_completions(self, incomplete: str) -> Iterable[Completion]:
        """Generate model completions based on incomplete text."""
        # Handle provider prefix completion
        if "/" not in incomplete:
            # Complete provider names
            providers = ["openrouter", "ollama"]
            for provider in providers:
                if provider.startswith(incomplete.lower()):
                    yield Completion(
                        text=f"{provider}/",
                        start_position=-len(incomplete),
                        display=f"{provider}/",
                        display_meta="Provider"
                    )
        else:
            # Complete specific models within provider
            provider_prefix, model_partial = incomplete.split("/", 1)
            provider = provider_prefix.lower()
            
            if provider == "openrouter":
                models = self._get_cached_models("openrouter")
                for model_id in models:
                    if model_id.startswith(f"{provider_prefix}/{model_partial}"):
                        # Extract just the model part after provider/
                        model_name = model_id[len(f"{provider_prefix}/"):]
                        yield Completion(
                            text=model_name,
                            start_position=-len(model_partial),
                            display=model_name,
                            display_meta="OpenRouter model"
                        )
            elif provider == "ollama":
                models = self._get_cached_models("ollama")
                for model_name in models:
                    if model_name.startswith(model_partial):
                        yield Completion(
                            text=model_name,
                            start_position=-len(model_partial),
                            display=model_name,
                            display_meta="Ollama model"
                        )

    def _get_cached_models(self, provider: str) -> list[str]:
        """Get cached model list for a provider."""
        if provider not in self._model_cache:
            # Start background refresh if not already running
            if self._cache_refresh_task is None or self._cache_refresh_task.done():
                self._cache_refresh_task = asyncio.create_task(self._refresh_model_cache())
            return []
        
        return self._model_cache.get(provider, [])

    async def _refresh_model_cache(self) -> None:
        """Refresh model cache from providers."""
        try:
            # Create providers to fetch models
            if self.settings.provider == "openrouter":
                if self.settings.openrouter_api_key:
                    from lizcode.core.providers.openrouter import OpenRouterProvider
                    provider = OpenRouterProvider(
                        api_key=self.settings.openrouter_api_key,
                        model=self.settings.openrouter_model,
                        base_url=self.settings.openrouter_base_url,
                    )
                    try:
                        models = await provider.list_models()
                        self._model_cache["openrouter"] = models
                    finally:
                        await provider.close()

            # Always try to get Ollama models if possible
            try:
                from lizcode.core.providers.ollama import OllamaProvider
                ollama_provider = OllamaProvider(
                    model=self.settings.ollama_model,
                    host=self.settings.ollama_host,
                )
                try:
                    if await ollama_provider.is_available():
                        models = await ollama_provider.list_models()
                        self._model_cache["ollama"] = models
                finally:
                    await ollama_provider.close()
            except Exception:
                # Ollama might not be available, that's ok
                pass

        except Exception:
            # Don't crash completion on network errors
            pass

    async def close(self) -> None:
        """Cleanup completer resources."""
        if self._cache_refresh_task and not self._cache_refresh_task.done():
            self._cache_refresh_task.cancel()