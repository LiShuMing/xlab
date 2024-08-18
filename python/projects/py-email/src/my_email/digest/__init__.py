"""
Digest generation module.

Builds daily digests from summarized emails with topic clustering.
"""

from my_email.digest.builder import DailyDigest, TopicCluster, build_digest
from my_email.digest.renderer import build_html_digest, TemplateError

__all__ = [
    "DailyDigest",
    "TopicCluster",
    "build_digest",
    "build_html_digest",
    "TemplateError",
]
