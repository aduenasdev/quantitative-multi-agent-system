"""Quantitative multi-agent system: red-team trading hypotheses before trusting them."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("qmas")
except PackageNotFoundError:  # pragma: no cover - only when running from an uninstalled tree
    __version__ = "0.0.0"

__all__ = ["__version__"]
