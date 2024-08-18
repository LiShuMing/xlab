"""
Module interface defining the contract for neural network components.
"""

from abc import ABC, abstractmethod
from typing import List, Sequence
from .value import ValueInterface


class ModuleInterface(ABC):
    """
    Abstract base class for neural network modules.

    All neural network components (layers, activations, etc.) should
    inherit from this class and implement the forward method.
    """

    @abstractmethod
    def __call__(self, x: Sequence[ValueInterface]) -> ValueInterface:
        """
        Forward pass through the module.

        Args:
            x: Input values

        Returns:
            Output value(s)
        """
        pass

    @abstractmethod
    def parameters(self) -> List[ValueInterface]:
        """
        Get all trainable parameters of this module.

        Returns:
            List of Value objects that are parameters
        """
        pass

    def zero_grad(self) -> None:
        """
        Zero out gradients of all parameters.

        This is a concrete method with a default implementation
        that can be overridden if needed.
        """
        for p in self.parameters():
            p.grad = 0.0


class NeuronInterface(ModuleInterface):
    """Interface for a single neuron."""

    w: List[ValueInterface]
    b: ValueInterface
    nonlin: bool

    @abstractmethod
    def __init__(self, nin: int, nonlin: bool = True) -> None:
        """
        Initialize a neuron.

        Args:
            nin: Number of inputs
            nonlin: Whether to apply nonlinearity (ReLU)
        """
        pass


class LayerInterface(ModuleInterface):
    """Interface for a layer of neurons."""

    neurons: List[NeuronInterface]

    @abstractmethod
    def __init__(self, nin: int, nout: int, **kwargs) -> None:
        """
        Initialize a layer.

        Args:
            nin: Number of inputs
            nout: Number of outputs (neurons in this layer)
            **kwargs: Additional arguments passed to neurons
        """
        pass


class MLPInterface(ModuleInterface):
    """Interface for Multi-Layer Perceptron."""

    layers: List[LayerInterface]

    @abstractmethod
    def __init__(self, nin: int, nouts: List[int]) -> None:
        """
        Initialize an MLP.

        Args:
            nin: Number of inputs
            nouts: List of layer sizes (output sizes)
        """
        pass
