from __future__ import annotations

import streamlit as st
from openai import OpenAI


# Try these OpenRouter models in order.
#
# Important:
# Free-model availability can change over time.
# openrouter/free is kept as the final fallback.
MODELS = [
    "stealth/union-alpha",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "openrouter/free",
]


class AIProviderError(RuntimeError):
    pass


def get_ai_client() -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=st.secrets["OPENROUTER_API_KEY"],
        timeout=20.0,
        max_retries=0,
    )


def complete(
    messages: list[dict],
    temperature: float = 0.0,
) -> str:

    client = get_ai_client()

    errors = []

    for model in MODELS:

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=1200,
            )

            if not response.choices:
                errors.append(
                    f"{model}: no choices returned"
                )
                continue

            content = response.choices[0].message.content

            if content and content.strip():
                return content.strip()

            errors.append(
                f"{model}: empty response"
            )

        except Exception as exc:

            errors.append(
                f"{model}: "
                f"{type(exc).__name__}: {exc}"
            )

            # Immediately move to the next model.
            continue

    # All models failed.
    raise AIProviderError(
        "All OpenRouter AI models are currently unavailable. "
        + " | ".join(errors)
    )