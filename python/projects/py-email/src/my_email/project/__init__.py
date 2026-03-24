"""
Project identification module.

Provides automatic project discovery and email-to-project assignment
based on topic co-occurrence clustering.
"""

from my_email.project.models import Project, ProjectAssignment

__all__ = ["Project", "ProjectAssignment"]