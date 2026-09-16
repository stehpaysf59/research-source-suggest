from __future__ import annotations

import streamlit as st
from openai import OpenAI


PRIMARY_MODEL = "dots-studio/dots-3-note-preview:free"

FALLBACK_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "openrouter/free",
]


class AIProviderError(RuntimeError):
    pass


def get_ai_client() -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=st.secrets["OPENROUTER_API_KEY"],
        timeout=45.0,
        max_retries=0,
    )


def complete(
    messages: list[dict],
    temperature: float = 0.0,
) -> str:

    client = get_ai_client()

    try:
        response = client.chat.completions.create(
            model=PRIMARY_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=1000,

            # OpenRouter tries these if the primary model
            # is unavailable / rate-limited.
            extra_body={
                "models": FALLBACK_MODELS,
            },
        )

    except Exception as exc:
        print("\n=== AI PROVIDER ERROR ===")
        print(f"Type: {type(exc).__name__}")
        print(f"Message: {exc}")
        print("=== END AI PROVIDER ERROR ===\n")

        raise AIProviderError(
            "The AI service is temporarily unavailable."
        ) from exc

    message = response.choices[0].message
    content = message.content

    if not content:
        raise AIProviderError(
            "The AI model returned an empty response."
        )

    return content