"""
Thin LLM abstraction so the rest of the app calls one interface regardless
of whether Groq or OpenAI is configured as the provider.
"""
from __future__ import annotations

from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class LLMProviderError(Exception):
    """Raised when the LLM provider itself is the problem (rate limit, auth,
    quota) rather than a transient network blip — callers should surface
    this to the user as a clear message instead of a generic 500."""


class LLMRateLimitError(LLMProviderError):
    pass


def _is_rate_limit_error(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    return status == 429 or "rate_limit" in str(exc).lower() or "429" in str(exc)


class LLMClient:
    def __init__(self) -> None:
        self.provider = settings.LLM_PROVIDER
        if self.provider == "groq":
            from groq import Groq
            self._client = Groq(api_key=settings.GROQ_API_KEY)
            self._model = settings.GROQ_MODEL
            self._extraction_model = settings.GROQ_EXTRACTION_MODEL
        else:
            from openai import OpenAI
            self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self._model = settings.OPENAI_MODEL
            self._extraction_model = settings.OPENAI_EXTRACTION_MODEL

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        # Don't burn retries against a rate limit that won't clear for
        # minutes — fail fast with a clear error instead.
        retry=retry_if_not_exception_type(LLMRateLimitError),
    )
    def complete(self, system: str, user: str, temperature: float = 0.2, json_mode: bool = False,
                 max_tokens: int = 2000, use_extraction_model: bool = False) -> str:
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        model = self._extraction_model if use_extraction_model else self._model
        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("llm_call_failed", provider=self.provider, model=model, error=str(exc))
            if _is_rate_limit_error(exc):
                raise LLMRateLimitError(
                    f"{self.provider} rate/quota limit reached. Wait for it to reset, "
                    f"switch LLM_PROVIDER in .env, or upgrade your plan. Details: {exc}"
                ) from exc
            raise


_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
