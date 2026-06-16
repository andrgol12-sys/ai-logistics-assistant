"""Handlers package — import submodules to register bot handlers."""

from . import start, text, voice, image, document_upload

__all__ = ["start", "text", "voice", "image", "document_upload"]
