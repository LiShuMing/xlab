"""
Tests for micrograd implementation.

This module contains comprehensive tests for the micrograd autograd engine
including Value operations, neural network layers, and optimizers.
"""

import math
from typing import List
import pytest
from micrograd.engine import Value
from micrograd.nn import Neuron, Layer, MLP
from micrograd.optim import SGD


class TestValue:
    """Test Value class operations."""

    def test_value_init(self) -> None:
        """Test Value initialization."""
        a: Value = Value(5.0)
        assert a.data == 5.0
        assert a.grad == 0.0

    def test_value_repr(self) -> None:
        """Test Value string representation."""
        a: Value = Value(5.0)
        assert "5.0" in repr(a)

    def test_addition(self) -> None:
        """Test addition and gradient computation."""
        a: Value = Value(2.0)
        b: Value = Value(3.0)
        c: Value = a + b
        assert c.data == 5.0

        c.backward()
        assert a.grad == 1.0
        assert b.grad == 1.0

    def test_multiplication(self) -> None:
        """Test multiplication and gradient computation."""
        a: Value = Value(2.0)
        b: Value = Value(3.0)
        c: Value = a * b
        assert c.data == 6.0

        c.backward()
        assert a.grad == 3.0
        assert b.grad == 2.0

    def test_power(self) -> None:
        """Test power operation and gradient."""
        a: Value = Value(2.0)
        b: Value = a ** 3
        assert b.data == 8.0

        b.backward()
        assert a.grad == 12.0  # 3 * 2^2

    def test_relu(self) -> None:
        """Test ReLU activation."""
        a: Value = Value(-1.0)
        b: Value = a.relu()
        assert b.data == 0.0

        b.backward()
        assert a.grad == 0.0

        c: Value = Value(2.0)
        d: Value = c.relu()
        assert d.data == 2.0

        d.backward()
        assert c.grad == 1.0

    def test_tanh(self) -> None:
        """Test tanh activation."""
        a: Value = Value(0.0)
        b: Value = a.tanh()
        assert math.isclose(b.data, 0.0, abs_tol=1e-6)

        b.backward()
        assert math.isclose(a.grad, 1.0, abs_tol=1e-6)

    def test_exp(self) -> None:
        """Test exponential."""
        a: Value = Value(1.0)
        b: Value = a.exp()
        assert math.isclose(b.data, math.e, abs_tol=1e-6)

        b.backward()
        assert math.isclose(a.grad, math.e, abs_tol=1e-6)

    def test_log(self) -> None:
        """Test natural logarithm."""
        a: Value = Value(math.e)
        b: Value = a.log()
        assert math.isclose(b.data, 1.0, abs_tol=1e-6)

        b.backward()
        assert math.isclose(a.grad, 1.0 / math.e, abs_tol=1e-6)

    def test_subtraction(self) -> None:
        """Test subtraction."""
        a: Value = Value(5.0)
        b: Value = Value(3.0)
        c: Value = a - b
        assert c.data == 2.0

        c.backward()
        assert a.grad == 1.0
        assert b.grad == -1.0

    def test_division(self) -> None:
        """Test division."""
        a: Value = Value(6.0)
        b: Value = Value(2.0)
        c: Value = a / b
        assert c.data == 3.0

        c.backward()
        assert a.grad == 0.5
        assert b.grad == -1.5

    def test_chain_rule(self) -> None:
        """Test chain rule with complex expression."""
        x: Value = Value(2.0)
        y: Value = Value(3.0)
        z: Value = (x * y + x) ** 2

        z.backward()
        # z = (xy + x)^2
        # dz/dx = 2(xy + x)(y + 1) = 2(6 + 2)(4) = 64
        # dz/dy = 2(xy + x)(x) = 2(8)(2) = 32
        assert x.grad == 64.0
        assert y.grad == 32.0

    def test_scalar_operations(self) -> None:
        """Test operations with scalar values."""
        a: Value = Value(2.0)
        b: Value = a + 3  # __radd__
        assert b.data == 5.0

        c: Value = 3 + a  # __add__
        assert c.data == 5.0

        d: Value = a * 3  # __mul__
        assert d.data == 6.0

        e: Value = 3 * a  # __rmul__
        assert e.data == 6.0


class TestNeuron:
    """Test Neuron class."""

    def test_neuron_init(self) -> None:
        """Test neuron initialization."""
        n: Neuron = Neuron(3)
        assert len(n.w) == 3
        assert hasattr(n, 'b')
        assert n.nonlin is True

    def test_neuron_forward(self) -> None:
        """Test neuron forward pass."""
        n: Neuron = Neuron(3)
        x: List[Value] = [Value(1.0), Value(2.0), Value(3.0)]
        out: Value = n(x)
        assert isinstance(out, Value)
        assert out.data >= 0  # ReLU output

    def test_neuron_parameters(self) -> None:
        """Test neuron parameter collection."""
        n: Neuron = Neuron(3)
        params: List[Value] = n.parameters()
        assert len(params) == 4  # 3 weights + bias


class TestLayer:
    """Test Layer class."""

    def test_layer_init(self) -> None:
        """Test layer initialization."""
        layer: Layer = Layer(3, 4)
        assert len(layer.neurons) == 4

    def test_layer_forward(self) -> None:
        """Test layer forward pass."""
        layer: Layer = Layer(3, 2)
        x: List[Value] = [Value(1.0), Value(2.0), Value(3.0)]
        out = layer(x)
        assert isinstance(out, list)
        assert len(out) == 2
        assert all(isinstance(o, Value) for o in out)

    def test_layer_single_output(self) -> None:
        """Test layer with single output."""
        layer: Layer = Layer(3, 1)
        x: List[Value] = [Value(1.0), Value(2.0), Value(3.0)]
        out = layer(x)
        # Single output should be unwrapped
        assert isinstance(out, Value)

    def test_layer_parameters(self) -> None:
        """Test layer parameter collection."""
        layer: Layer = Layer(3, 2)
        params: List[Value] = layer.parameters()
        assert len(params) == 8  # 2 neurons * (3 weights + 1 bias)


class TestMLP:
    """Test MLP class."""

    def test_mlp_init(self) -> None:
        """Test MLP initialization."""
        mlp: MLP = MLP(3, [4, 2, 1])
        assert len(mlp.layers) == 3

    def test_mlp_forward(self) -> None:
        """Test MLP forward pass."""
        mlp: MLP = MLP(3, [4, 1])
        x: List[Value] = [Value(1.0), Value(2.0), Value(3.0)]
        out: Value = mlp(x)
        assert isinstance(out, Value)

    def test_mlp_parameters(self) -> None:
        """Test MLP parameter collection."""
        mlp: MLP = MLP(3, [4, 1])
        params: List[Value] = mlp.parameters()
        # Layer 1: 4 neurons * (3 weights + 1 bias) = 16
        # Layer 2: 1 neuron * (4 weights + 1 bias) = 5
        assert len(params) == 21


class TestSGD:
    """Test SGD optimizer."""

    def test_sgd_init(self) -> None:
        """Test SGD initialization."""
        model: MLP = MLP(3, [4, 1])
        optimizer: SGD = SGD(model.parameters(), lr=0.01)
        assert optimizer.lr == 0.01
        assert len(optimizer.parameters) > 0

    def test_sgd_step(self) -> None:
        """Test SGD step updates parameters."""
        # Use a simple neuron with guaranteed positive activation
        neuron: Neuron = Neuron(3, nonlin=False)
        optimizer: SGD = SGD(neuron.parameters(), lr=0.01)

        # Forward pass with large positive inputs
        x: List[Value] = [Value(10.0), Value(10.0), Value(10.0)]
        out: Value = neuron(x)

        # Backward pass
        out.backward()

        # Get initial values
        initial_values: List[float] = [p.data for p in neuron.parameters()]

        # Step
        optimizer.step()

        # Check values changed
        changed: bool = False
        for i, p in enumerate(neuron.parameters()):
            if abs(p.data - initial_values[i]) > 1e-10:
                changed = True
                break
        assert changed, "SGD step should change at least one parameter"

    def test_sgd_zero_grad(self) -> None:
        """Test SGD zero_grad clears gradients."""
        # Use a simple neuron with guaranteed positive activation
        neuron: Neuron = Neuron(3, nonlin=False)
        optimizer: SGD = SGD(neuron.parameters(), lr=0.01)

        # Forward pass
        x: List[Value] = [Value(10.0), Value(10.0), Value(10.0)]
        out: Value = neuron(x)
        out.backward()

        # Check at least some gradients are non-zero
        has_nonzero_grad: bool = any(p.grad != 0 for p in neuron.parameters())
        assert has_nonzero_grad, "At least one gradient should be non-zero"

        # Zero gradients
        optimizer.zero_grad()

        # Check gradients are zero
        assert all(p.grad == 0 for p in neuron.parameters())
