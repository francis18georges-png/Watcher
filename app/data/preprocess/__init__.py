"""Preprocessing utilities for text data.

This subpackage provides simple text cleaning and tokenization steps that can be
composed into data pipelines. Each module exposes a callable implementing the
:class:`~app.data.pipeline.PipelineStep` protocol so that they can be referenced
from configuration files.
"""

from .cleaning import HtmlCleaner
from .tokenizer import SimpleTokenizer

__all__ = ["HtmlCleaner", "SimpleTokenizer"]
