"""steroids-openai-image-gen Hermes plugin."""
from .provider import SteroidsOpenAIImageGenProvider
from .tool_override import register_image_generate_override


def register(ctx) -> None:
    """Register provider and enhanced image_generate schema override."""
    ctx.register_image_gen_provider(SteroidsOpenAIImageGenProvider())
    register_image_generate_override(ctx)
