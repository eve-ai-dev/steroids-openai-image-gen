"""Hermes plugin entry point for steroids-openai-image-gen."""
from __future__ import annotations

try:
    from .steroids_openai_image_gen import register
except ImportError:  # direct plugin loading without package context
    from steroids_openai_image_gen import register
