"""
Value interface defining the contract for scalar values with automatic differentiation.
"""

from abc import ABC, abstractmethod
from typing import Set, Tuple, Callable, Optional, Union


class ValueInterface(ABC):
    """
    Abstract base class for scalar values supporting automatic differentiation.

    A Value wraps a scalar and keeps track of the computational graph
    to enable reverse-mode automatic differentiation via backpropagation.
    """

    # Core attributes
    data: float
    grad: float
    _backward: Callable[[], None]
    _prev: Set["ValueInterface"]
    _op: str
    label: str

    @abstractmethod
    def __init__(
        self,
        data: float,
        _children: Tuple["ValueInterface", ...] = (),
        _op: str = "",
        label: str = ""
    ) -> None:
        """
        Initialize a Value.

        Args:
            data: The scalar value
            _children: Parent nodes in the computational graph
            _op: Operation that created this value
            label: Human-readable label for debugging
        """
        pass

    @abstractmethod
    def __add__(self, other: Union["ValueInterface", float]) -> "ValueInterface":
        """Add two values."""
        pass

    @abstractmethod
    def __mul__(self, other: Union["ValueInterface", float]) -> "ValueInterface":
        """Multiply two values."""
        pass

    @abstractmethod
    def __pow__(self, other: Union[int, float]) -> "ValueInterface":
        """Raise to a power."""
        pass

    @abstractmethod
    def relu(self) -> "ValueInterface":
        """Apply ReLU activation."""
        pass

    @abstractmethod
    def tanh(self) -> "ValueInterface":
        """Apply tanh activation."""
        pass

    @abstractmethod
    def exp(self) -> "ValueInterface":
        """Compute exponential."""
        pass

    @abstractmethod
    def log(self) -> "ValueInterface":
        """Compute natural logarithm."""
        pass

    @abstractmethod
    def backward(self) -> None:
        """
        Perform reverse-mode automatic differentiation.

        Computes gradients for all nodes in the computational graph
        using the chain rule.
        """
        pass
