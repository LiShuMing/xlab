"""
Neural network layers for micrograd.

This module provides implementations of common neural network components
including neurons, layers, and multi-layer perceptrons (MLPs).
"""

import random
from typing import List, Sequence, Union
from micrograd.engine import Value


class Module:
    """
    Base class for all neural network modules.

    All neural network components should inherit from this class
    and implement the parameters() and __call__() methods.
    """

    def zero_grad(self) -> None:
        """Zero out gradients of all parameters."""
        for p in self.parameters():
            p.grad = 0.0

    def parameters(self) -> List[Value]:
        """Return list of all trainable parameters."""
        return []


class Neuron(Module):
    """
    A single neuron implementing: output = activation(sum(w * x) + b)

    The neuron computes a weighted sum of inputs, adds a bias term,
    and optionally applies ReLU activation.
    """

    def __init__(self, nin: int, nonlin: bool = True) -> None:
        """
        Initialize a neuron.

        Args:
            nin: Number of input features
            nonlin: If True, apply ReLU activation; else linear output
        """
        self.w: List[Value] = [Value(random.uniform(-1, 1)) for _ in range(nin)]
        self.b: Value = Value(0.0)
        self.nonlin: bool = nonlin

    def __call__(self, x: Sequence[Value]) -> Value:
        """
        Forward pass through the neuron.

        Args:
            x: Input values (sequence of Value objects)

        Returns:
            Output value after weighted sum and optional activation
        """
        act: Value = sum((wi * xi for wi, xi in zip(self.w, x)), self.b)
        return act.relu() if self.nonlin else act

    def parameters(self) -> List[Value]:
        """Return weights and bias."""
        return self.w + [self.b]

    def __repr__(self) -> str:
        return f"{'ReLU' if self.nonlin else 'Linear'}Neuron({len(self.w)})"


class Layer(Module):
    """
    A layer consisting of multiple neurons.

    Each neuron in the layer receives the same inputs but has
    independent weights and biases.
    """

    def __init__(self, nin: int, nout: int, **kwargs) -> None:
        """
        Initialize a layer.

        Args:
            nin: Number of input features per neuron
            nout: Number of neurons (outputs) in this layer
            **kwargs: Additional arguments passed to Neuron constructor
        """
        self.neurons: List[Neuron] = [Neuron(nin, **kwargs) for _ in range(nout)]

    def __call__(self, x: Sequence[Value]) -> Union[Value, List[Value]]:
        """
        Forward pass through the layer.

        Args:
            x: Input values

        Returns:
            Single Value if layer has 1 neuron, else list of Values
        """
        outs: List[Value] = [n(x) for n in self.neurons]
        return outs[0] if len(outs) == 1 else outs

    def parameters(self) -> List[Value]:
        """Return parameters of all neurons."""
        return [p for n in self.neurons for p in n.parameters()]

    def __repr__(self) -> str:
        return f"Layer of [{', '.join(str(n) for n in self.neurons)}]"


class MLP(Module):
    """
    Multi-Layer Perceptron (fully connected neural network).

    A feedforward neural network consisting of multiple layers
    where each layer's output is fed into the next layer.
    """

    def __init__(self, nin: int, nouts: List[int]) -> None:
        """
        Initialize an MLP.

        Args:
            nin: Number of input features
            nouts: List of layer sizes (number of neurons per layer).
                  The last layer typically has no activation.
        """
        sz: List[int] = [nin] + nouts
        self.layers: List[Layer] = [
            Layer(sz[i], sz[i+1], nonlin=i != len(nouts)-1)
            for i in range(len(nouts))
        ]

    def __call__(self, x: Sequence[Value]) -> Value:
        """
        Forward pass through the network.

        Args:
            x: Input values

        Returns:
            Output of the final layer
        """
        out: Union[Value, List[Value]] = x
        for layer in self.layers:
            out = layer(out)
        assert isinstance(out, Value), "MLP output should be a single Value"
        return out

    def parameters(self) -> List[Value]:
        """Return parameters of all layers."""
        return [p for layer in self.layers for p in layer.parameters()]

    def __repr__(self) -> str:
        return f"MLP of [{', '.join(str(layer) for layer in self.layers)}]"
