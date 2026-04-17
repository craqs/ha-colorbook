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

_RANDOM_SYSTEM_PROMPT = (
    "Zwróć dokładnie jeden krótki (3-8 słów) pomysł na stronę do kolorowania dla "
    "dziecka w wieku 4-8 lat, po polsku. Temat ma być pozytywny, przyjazny, "
    "konkretny i łatwy do narysowania prostymi liniami. Przykłady: "
    "'lis biegnący przez las', 'przyjazny robot piekący ciasteczka', "
    "'dinozaur na deskorolce'. Bez cudzysłowów, bez numeracji, bez wyjaśnień, "
    "bez kropki na końcu."
)


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
            "Brak klucza OpenAI. Uzupełnij 'openai_api_key' w konfiguracji "
            "dodatku lub ustaw zmienną OPENAI_TOKEN."
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
            raise RuntimeError("OpenAI nie zwróciło obrazka.")
        import urllib.request
        with urllib.request.urlopen(url, timeout=60) as resp:
            return resp.read()
    return base64.b64decode(b64)


def random_topic() -> str:
    """Generate a fresh Polish topic, avoiding recent duplicates."""
    client = _client()
    for _ in range(4):
        resp = client.chat.completions.create(
            model=SETTINGS.openai_chat_model,
            messages=[
                {"role": "system", "content": _RANDOM_SYSTEM_PROMPT},
                {"role": "user", "content": "Podaj jeden losowy pomysł."},
            ],
            temperature=1.1,
            max_tokens=40,
        )
        text = (resp.choices[0].message.content or "").strip()
        # Clean up any stray quotes/trailing punctuation
        text = text.strip().strip('"').strip("'").rstrip(".").strip()
        if text and not _recent_topics.contains(text):
            _recent_topics.add(text)
            return text
    # Give up on uniqueness after a few tries — return last attempt anyway
    _recent_topics.add(text)
    return text or "kotek na łące"
