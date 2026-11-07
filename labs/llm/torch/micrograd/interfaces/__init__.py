"""
Interface definitions for micrograd.

This module defines abstract base classes that specify the contracts
for all micrograd components. Implementation modules should inherit
from these interfaces.
"""

from .value import ValueInterface
from .module import ModuleInterface
from .optimizer import OptimizerInterface

__all__ = ["ValueInterface", "ModuleInterface", "OptimizerInterface"]