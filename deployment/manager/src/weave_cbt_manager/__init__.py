"""WEAVE CBT Manager package."""

try:
    from .generated_build import MANAGER_VERSION as __version__
except ImportError:
    __version__ = "0.1.11"
