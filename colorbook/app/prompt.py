"""Build the image-generation prompt from a user topic.

The user types the topic in Polish (to match the Polish UI), but the prompt
sent to the image model stays in English because image models follow English
prompts most reliably.
"""

from __future__ import annotations

COLORBOOK_TEMPLATE = (
    "Black-and-white line art coloring book page for young children. "
    "Thick, clean, smooth outlines only. No shading, no gradients, no color fills. "
    "Pure white background. Simple, recognizable shapes suitable for a 4-8 year old "
    "to color. Centered composition with some empty space around the subject. "
    "Subject (translated from Polish if needed): {topic}."
)


def build_prompt(topic: str, refinement: str | None = None) -> str:
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("Temat nie może być pusty.")
    prompt = COLORBOOK_TEMPLATE.format(topic=topic)
    refinement = (refinement or "").strip()
    if refinement:
        prompt += f" Additional guidance: {refinement}."
    return prompt
