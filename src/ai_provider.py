from __future__ import annotations

import streamlit as st
from openai import OpenAI


# Current free model with strong availability.
PRIMARY_MODEL = "inclusionai/ling-3.0-flash-vl:free"


class AIProviderError(RuntimeError):
    pass


def get_ai_client() -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=st.secrets["OPENROUTER_API_KEY"],
        timeout=45.0,
        max_retries=1,
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

            # This task needs a short final answer, not chain-of-thought.
            extra_body={
                "reasoning": {
                    "effort": "none"
                }
            },
        )

    except Exception as exc:
        raise AIProviderError(
            f"The AI service is temporarily unavailable: {exc}"
        ) from exc

    message = response.choices[0].message

    content = message.content

    if not content or not content.strip():
        raise AIProviderError(
            "The AI model returned an empty response."
        )

    return content.strip()