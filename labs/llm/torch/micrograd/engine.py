"""
Core implementation of the autograd engine.

This module implements a tiny automatic differentiation engine supporting
reverse-mode autodiff (backpropagation) through a dynamic computational graph.
"""

import math
from typing import Set, Tuple, Callable, Union


class Value:
    """
    A scalar value supporting automatic differentiation.

    Wraps a scalar value and tracks operations to build a computational
    graph. Supports reverse-mode automatic differentiation via the
    backward() method.

    Example:
        >>> x = Value(2.0, label='x')
        >>> y = Value(3.0, label='y')
        >>> z = x * y + x**2
        >>> z.backward()
        >>> print(x.grad)  # dz/dx
    """

    def __init__(
        self,
        data: float,
        _children: Tuple["Value", ...] = (),
        _op: str = "",
        label: str = ""
    ) -> None:
        """
        Initialize a Value.

        Args:
            data: The scalar value to wrap
            _children: Parent nodes in the computational graph
            _op: Operation that created this value (for visualization)
            label: Human-readable identifier (for debugging)
        """
        self.data: float = data
        self.grad: float = 0.0
        self._backward: Callable[[], None] = lambda: None
        self._prev: Set[Value] = set(_children)
        self._op: str = _op
        self.label: str = label

    def __repr__(self) -> str:
        """Return string representation of the Value."""
        return f"Value(data={self.data}, grad={self.grad})"

    def __add__(self, other: Union["Value", float]) -> "Value":
        """
        Add two values.

        Args:
            other: Value or scalar to add

        Returns:
            New Value representing the sum
        """
        other = other if isinstance(other, Value) else Value(other)
        out = Value(self.data + other.data, (self, other), '+')

        def _backward() -> None:
            self.grad += out.grad
            other.grad += out.grad
        out._backward = _backward

        return out

    def __mul__(self, other: Union["Value", float]) -> "Value":
        """
        Multiply two values.

        Args:
            other: Value or scalar to multiply

        Returns:
            New Value representing the product
        """
        other = other if isinstance(other, Value) else Value(other)
        out = Value(self.data * other.data, (self, other), '*')

        def _backward() -> None:
            self.grad += other.data * out.grad
            other.grad += self.data * out.grad
        out._backward = _backward

        return out

    def __pow__(self, other: Union[int, float]) -> "Value":
        """
        Raise to a power.

        Args:
            other: Exponent (int or float)

        Returns:
            New Value representing self**other

        Raises:
            AssertionError: If other is not int or float
        """
        assert isinstance(other, (int, float)), "only supporting int/float powers"
        out = Value(self.data**other, (self,), f'**{other}')

        def _backward() -> None:
            self.grad += (other * self.data**(other-1)) * out.grad
        out._backward = _backward

        return out

    def relu(self) -> "Value":
        """
        Apply ReLU activation.

        Returns:
            New Value with ReLU applied: max(0, self)
        """
        out = Value(0 if self.data < 0 else self.data, (self,), 'ReLU')

        def _backward() -> None:
            self.grad += (out.data > 0) * out.grad
        out._backward = _backward

        return out

    def tanh(self) -> "Value":
        """
        Apply tanh activation.

        Returns:
            New Value with tanh applied
        """
        x = self.data
        t = (math.exp(2*x) - 1) / (math.exp(2*x) + 1)
        out = Value(t, (self,), 'tanh')

        def _backward() -> None:
            self.grad += (1 - t**2) * out.grad
        out._backward = _backward

        return out

    def exp(self) -> "Value":
        """
        Compute exponential.

        Returns:
            New Value representing exp(self)
        """
        x = self.data
        out = Value(math.exp(x), (self,), 'exp')

        def _backward() -> None:
            self.grad += out.data * out.grad
        out._backward = _backward

        return out

    def log(self) -> "Value":
        """
        Compute natural logarithm.

        Returns:
            New Value representing log(self)
        """
        x = self.data
        out = Value(math.log(x), (self,), 'log')

        def _backward() -> None:
            self.grad += (1 / x) * out.grad
        out._backward = _backward

        return out

    def backward(self) -> None:
        """
        Perform reverse-mode automatic differentiation.

        Computes gradients for all nodes in the computational graph
        by traversing the graph in reverse topological order and
        applying the chain rule at each node.
        """
        topo: list[Value] = []
        visited: set[Value] = set()

        def build_topo(v: Value) -> None:
            if v not in visited:
                visited.add(v)
                for child in v._prev:
                    build_topo(child)
                topo.append(v)

        build_topo(self)

        self.grad = 1.0
        for node in reversed(topo):
            node._backward()

    def __neg__(self) -> "Value":
        """Unary negation."""
        return self * -1

    def __radd__(self, other: float) -> "Value":
        """Right addition (for scalar + Value)."""
        return self + other

    def __sub__(self, other: Union["Value", float]) -> "Value":
        """Subtraction."""
        return self + (-other)

    def __rsub__(self, other: float) -> "Value":
        """Right subtraction (for scalar - Value)."""
        return other + (-self)

    def __rmul__(self, other: float) -> "Value":
        """Right multiplication (for scalar * Value)."""
        return self * other

    def __truediv__(self, other: Union["Value", float]) -> "Value":
        """Division (implemented as multiplication by reciprocal)."""
        return self * other**-1

    def __rtruediv__(self, other: float) -> "Value":
        """Right division (for scalar / Value)."""
        return other * self**-1
