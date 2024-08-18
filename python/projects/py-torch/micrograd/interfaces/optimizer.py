"""
Optimizer interface defining the contract for optimization algorithms.
"""

from abc import ABC, abstractmethod
from typing import List
from .value import ValueInterface


class OptimizerInterface(ABC):
    """
    Abstract base class for optimizers.

    Optimizers update model parameters based on computed gradients
    during training.
    """

    parameters: List[ValueInterface]
    lr: float

    @abstractmethod
    def __init__(self, parameters: List[ValueInterface], lr: float = 0.01) -> None:
        """
        Initialize the optimizer.

        Args:
            parameters: List of Value objects to optimize
            lr: Learning rate
        """
        pass

    @abstractmethod
    def step(self) -> None:
        """
        Perform a single optimization step.

        Updates all parameters based on their gradients.
        """
        pass

    def zero_grad(self) -> None:
        """
        Zero out gradients of all parameters.

        Should be called before backward pass in training loop.
        """
        for p in self.parameters:
            p.grad = 0.0
