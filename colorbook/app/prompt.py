"""Build the image-generation prompt from a user topic.

The prompt sent to the image model is always English — models respond best to it.
The user topic may be in any language; the template instructs the model to
translate if needed.
"""

from __future__ import annotations

COLORBOOK_TEMPLATE = (
    "Black-and-white line art coloring book page for young children. "
    "Thick, clean, smooth outlines only. No shading, no gradients, no color fills. "
    "Pure white background. Simple, recognizable shapes suitable for a 4-8 year old "
    "to color. Centered composition with some empty space around the subject. "
    "Subject (translate to English if needed): {topic}."
)


def build_prompt(topic: str, refinement: str | None = None) -> str:
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("Topic cannot be empty.")
    prompt = COLORBOOK_TEMPLATE.format(topic=topic)
    refinement = (refinement or "").strip()
    if refinement:
        prompt += f" Additional guidance: {refinement}."
    return prompt
