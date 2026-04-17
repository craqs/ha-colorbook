"""Thin wrappers over the OpenAI SDK for image generation and random topics."""

from __future__ import annotations

import base64
import logging
import threading
from collections import deque
from typing import Deque

from openai import OpenAI

from .config import SETTINGS

log = logging.getLogger(__name__)

_RANDOM_SYSTEM_PROMPTS: dict[str, str] = {
    "en": (
        "Return exactly one short (3-8 word) topic for a children's coloring page, in English. "
        "The topic must be positive, friendly, concrete, and easy to draw with simple lines. "
        "Examples: 'a fox running through the forest', 'a friendly robot baking cookies', "
        "'a dinosaur on a skateboard'. No quotes, no numbering, no explanation, no trailing period."
    ),
    "pl": (
        "Zwróć dokładnie jeden krótki (3-8 słów) pomysł na stronę do kolorowania dla "
        "dziecka w wieku 4-8 lat, po polsku. Temat ma być pozytywny, przyjazny, "
        "konkretny i łatwy do narysowania prostymi liniami. Przykłady: "
        "'lis biegnący przez las', 'przyjazny robot piekący ciasteczka', "
        "'dinozaur na deskorolce'. Bez cudzysłowów, bez numeracji, bez wyjaśnień, "
        "bez kropki na końcu."
    ),
}

_RANDOM_USER_PROMPTS: dict[str, str] = {
    "en": "Give me one random topic.",
    "pl": "Podaj jeden losowy pomysł.",
}

_FALLBACK_TOPICS: dict[str, str] = {
    "en": "a kitten in a meadow",
    "pl": "kotek na łące",
}


class _Recent:
    """Tiny thread-safe ring buffer to deduplicate recent random topics."""

    def __init__(self, maxlen: int = 20) -> None:
        self._dq: Deque[str] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def contains(self, value: str) -> bool:
        with self._lock:
            return value in self._dq

    def add(self, value: str) -> None:
        with self._lock:
            self._dq.append(value)


_recent_topics = _Recent(maxlen=20)


def _client() -> OpenAI:
    if not SETTINGS.openai_api_key:
        raise RuntimeError(
            "OpenAI API key is not configured. Set 'openai_api_key' in the "
            "add-on options or provide the OPENAI_TOKEN environment variable."
        )
    return OpenAI(api_key=SETTINGS.openai_api_key)


def generate_image(prompt: str) -> bytes:
    """Generate a PNG image; returns raw bytes."""
    client = _client()
    log.info("Generating image (model=%s size=%s quality=%s)",
             SETTINGS.openai_image_model, SETTINGS.image_size, SETTINGS.image_quality)
    result = client.images.generate(
        model=SETTINGS.openai_image_model,
        prompt=prompt,
        size=SETTINGS.image_size,
        quality=SETTINGS.image_quality,
        n=1,
    )
    # gpt-image-1 returns b64_json by default
    b64 = result.data[0].b64_json
    if not b64:
        # dall-e-3 fallback: URL-based response
        url = getattr(result.data[0], "url", None)
        if not url:
            raise RuntimeError("OpenAI returned no image data.")
        import urllib.request
        with urllib.request.urlopen(url, timeout=60) as resp:
            return resp.read()
    return base64.b64decode(b64)


def random_topic(language: str = "en") -> str:
    """Generate a fresh topic in the requested language, avoiding recent duplicates."""
    lang = language if language in _RANDOM_SYSTEM_PROMPTS else "en"
    client = _client()
    text = ""
    for _ in range(4):
        resp = client.chat.completions.create(
            model=SETTINGS.openai_chat_model,
            messages=[
                {"role": "system", "content": _RANDOM_SYSTEM_PROMPTS[lang]},
                {"role": "user",   "content": _RANDOM_USER_PROMPTS[lang]},
            ],
            temperature=1.1,
            max_tokens=40,
        )
        text = (resp.choices[0].message.content or "").strip()
        # Strip stray quotes / trailing punctuation
        text = text.strip('"').strip("'").rstrip(".").strip()
        if text and not _recent_topics.contains(text):
            _recent_topics.add(text)
            return text
    # Give up on uniqueness — return last attempt anyway
    _recent_topics.add(text)
    return text or _FALLBACK_TOPICS[lang]
