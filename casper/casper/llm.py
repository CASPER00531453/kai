"""Claude ile konuşma: tek bir yerde, hata mesajları Türkçe."""

from __future__ import annotations

from . import db, secrets

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(Exception):
    pass


def _client():
    try:
        import anthropic
    except ImportError as exc:
        raise LLMError("anthropic paketi kurulu değil: pip install anthropic") from exc
    key = secrets.load_api_key()
    if not key:
        raise LLMError("Claude API anahtarı yok. Ayarlar sekmesinden ekle.")
    return anthropic.Anthropic(api_key=key, max_retries=3)


def _supports_fallback(model: str) -> bool:
    # Haiku'da sunucu taraflı yedek model yok.
    return not model.startswith("claude-haiku")


def ask(
    *,
    model_key: str,
    system: list[dict] | str,
    messages: list[dict],
    effort: str = "medium",
    max_tokens: int = 16000,
) -> str:
    """Bir istek gönderir, yanıtın metnini döndürür."""
    import anthropic

    client = _client()
    model = db.get_setting(model_key) or db.DEFAULTS[model_key]
    params = dict(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
        output_config={"effort": effort},
    )
    try:
        if _supports_fallback(model):
            response = client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **params)
        else:
            response = client.messages.create(**params)
    except anthropic.AuthenticationError as exc:
        raise LLMError("API anahtarı geçersiz. Ayarlardan kontrol et.") from exc
    except anthropic.PermissionDeniedError as exc:
        raise LLMError("Bu API anahtarının bu modele izni yok.") from exc
    except anthropic.NotFoundError as exc:
        raise LLMError(f"Model bulunamadı: {model}. Ayarlardan modeli değiştir.") from exc
    except anthropic.RateLimitError as exc:
        raise LLMError("Çok sık istek gönderildi (limit). Biraz bekleyip tekrar dene.") from exc
    except anthropic.BadRequestError as exc:
        raise LLMError(f"İstek reddedildi: {exc.message}") from exc
    except anthropic.APIStatusError as exc:
        raise LLMError(f"Claude hatası ({exc.status_code}). Biraz sonra tekrar dene.") from exc
    except anthropic.APIConnectionError as exc:
        raise LLMError("İnternet bağlantısı yok ya da Claude'a ulaşılamıyor.") from exc

    if response.stop_reason == "refusal":
        return "Bu konuda yorum yapamıyorum."
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if response.stop_reason == "max_tokens":
        text += "\n\n(yanıt uzunluk sınırında kesildi)"
    return text
