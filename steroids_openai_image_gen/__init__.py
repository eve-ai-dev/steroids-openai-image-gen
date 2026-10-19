"""steroids-openai-image-gen Hermes plugin."""
from .provider import SteroidsOpenAIImageGenProvider
from .tool_override import register_image_tools


def register(ctx) -> None:
    """Register provider and non-colliding advanced image tools."""
    ctx.register_image_gen_provider(SteroidsOpenAIImageGenProvider())
    register_image_tools(ctx)
