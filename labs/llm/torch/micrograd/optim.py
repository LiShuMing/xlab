"""
Optimizers for micrograd.

This module provides optimization algorithms for training neural networks.
"""

from typing import Iterable, List
from micrograd.engine import Value


class SGD:
    """
    Stochastic Gradient Descent optimizer.

    Updates parameters using the formula:
        param = param - lr * param.grad

    This is the simplest optimization algorithm that follows the
    negative gradient direction.
    """

    def __init__(self, parameters: Iterable[Value], lr: float = 0.01) -> None:
        """
        Initialize SGD optimizer.

        Args:
            parameters: Iterable of Value objects to optimize
            lr: Learning rate (step size)
        """
        self.parameters: List[Value] = list(parameters)
        self.lr: float = lr

    def step(self) -> None:
        """
        Perform a single optimization step.

        Updates all parameters based on their current gradients.
        """
        for p in self.parameters:
            p.data -= self.lr * p.grad

    def zero_grad(self) -> None:
        """
        Zero out gradients of all parameters.

        Should be called before backward pass in training loop.
        """
        for p in self.parameters:
            p.grad = 0.0

    def __repr__(self) -> str:
        return f"SGD(lr={self.lr}, params={len(self.parameters)})"
