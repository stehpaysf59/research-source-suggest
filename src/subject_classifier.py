from __future__ import annotations

import json

from src.ai_provider import complete
from src.database import get_qs_subjects


MAX_RESEARCH_CHARS = 10000
MAX_SUBJECTS = 5


def _extract_json(raw: str) -> dict:
    if not raw:
        raise ValueError("AI returned an empty response.")

    cleaned = raw.strip()

    cleaned = cleaned.replace("```json", "")
    cleaned = cleaned.replace("```JSON", "")
    cleaned = cleaned.replace("```", "")
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError(
            f"No valid JSON object found in AI response:\n{cleaned}"
        )

    return json.loads(cleaned[start : end + 1])


def classify_qs_subjects(text: str) -> dict:
    text = (text or "").strip()

    if not text:
        return {
            "subjects": [],
            "subject_codes": [],
            "reason": "No research text was provided.",
        }

    text = text[:MAX_RESEARCH_CHARS]

    subjects_df = get_qs_subjects().copy()

    subjects_df["qs_subject_code"] = (
        subjects_df["qs_subject_code"]
        .astype(str)
        .str.strip()
    )

    subjects_df["qs_subject_name"] = (
        subjects_df["qs_subject_name"]
        .astype(str)
        .str.strip()
    )

    taxonomy = "\n".join(
        f"- {row.qs_subject_code} | {row.qs_subject_name}"
        for row in subjects_df.itertuples()
    )

    prompt = f"""
You classify academic research into the official QS Subject taxonomy.

Choose between 1 and {MAX_SUBJECTS} relevant QS Subjects.

STRICT RULES:

1. You MUST choose only subject codes from the allowed taxonomy below.
2. Do not create new subject codes.
3. Do not rename or paraphrase subjects.
4. Choose only genuinely relevant subjects.
5. If the input is unrelated to academic research or journal discovery,
   return an empty subject_codes list.
6. Return only one JSON object.

ALLOWED QS SUBJECT TAXONOMY:

{taxonomy}

RESEARCH TEXT:

{text}

Return exactly this JSON structure:

{{
  "subject_codes": [
    "EXACT_CODE_1",
    "EXACT_CODE_2"
  ],
  "reason": "One short sentence explaining the classification."
}}
"""

    raw = complete(
        messages=[
            {
                "role": "system",
                "content": (
                    "You classify academic research into a controlled "
                    "QS taxonomy. Return JSON only."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.0,
    )


    try:
        parsed = _extract_json(raw)

    except Exception as exc:
        print("JSON parsing error:", exc)

        return {
            "subjects": [],
            "subject_codes": [],
            "reason": "The AI response could not be parsed.",
        }

    code_to_name = dict(
        zip(
            subjects_df["qs_subject_code"],
            subjects_df["qs_subject_name"],
        )
    )

    valid_codes = []

    for code in parsed.get("subject_codes", []):
        code = str(code).strip()

        if code in code_to_name and code not in valid_codes:
            valid_codes.append(code)

    valid_codes = valid_codes[:MAX_SUBJECTS]

    valid_subjects = [
        code_to_name[code]
        for code in valid_codes
    ]

    return {
        "subjects": valid_subjects,
        "subject_codes": valid_codes,
        "reason": str(parsed.get("reason", "")).strip(),
    }