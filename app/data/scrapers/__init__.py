"""Specialised scraping helpers.

This package defines high level wrappers around :mod:`app.data.scraper` for
collecting domain specific texts. The functions are intentionally lightweight so
that they can be easily swapped or extended.
"""

from .french import fetch_french_corpus
from .programming import fetch_programming_docs

__all__ = ["fetch_french_corpus", "fetch_programming_docs"]
