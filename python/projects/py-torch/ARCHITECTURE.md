# PyTorch Learning Project - Architecture

## Overview

This project is organized into two main components:
1. **micrograd**: A from-scratch autograd engine implementing reverse-mode automatic differentiation
2. **tutorials**: PyTorch tutorials based on the official 60-Minute Blitz

## Design Principles

### 1. Interface-First Architecture

All components are designed using interface-first approach:
- Interfaces define contracts in `micrograd/interfaces/`
- Implementations fulfill these contracts
- Clear separation between specification and implementation

### 2. Strong Typing

All code uses Python type hints:
- Explicit type annotations for all function parameters and return values
- Type checking with mypy (recommended)
- Clear interfaces make the code self-documenting

### 3. English Comments

All comments and documentation are in English for international accessibility.

## Module Structure

### micrograd/

```
micrograd/
├── interfaces/          # Abstract base classes (contracts)
│   ├── __init__.py
│   ├── value.py        # ValueInterface
│   ├── module.py       # ModuleInterface, NeuronInterface, etc.
│   └── optimizer.py    # OptimizerInterface
├── engine.py           # Value implementation (autograd core)
├── nn.py               # Neural network layers
├── optim.py            # Optimizers (SGD)
└── utils.py            # Visualization utilities
```

#### engine.py

The core autograd implementation:

- **Value**: Scalar value with automatic differentiation
  - Wraps a float and tracks operations
  - Builds computational graph dynamically
  - Implements `backward()` for reverse-mode autodiff
  - Supports: +, *, **, ReLU, tanh, exp, log

Key algorithm:
```python
def backward(self) -> None:
    # 1. Build topological order (DAG traversal)
    # 2. Initialize output gradient to 1.0
    # 3. Visit nodes in reverse order, applying chain rule
```

#### nn.py

Neural network layers:

- **Module**: Base class for all neural network components
  - `parameters()`: Return trainable parameters
  - `zero_grad()`: Zero out gradients

- **Neuron**: Single neuron with weights and bias
  - Computes: `relu(sum(w * x) + b)`

- **Layer**: Collection of neurons
  - Same input fed to multiple neurons

- **MLP**: Multi-layer perceptron
  - Feedforward network with multiple layers

#### optim.py

Optimization algorithms:

- **SGD**: Stochastic Gradient Descent
  - Update rule: `param = param - lr * param.grad`
  - Simple but effective for many problems

### tutorials/

Progressive PyTorch tutorials:

1. **01_tensors.py**: Tensor basics
   - Creation, operations, broadcasting
   - NumPy bridge
   - GPU tensors

2. **02_autograd.py**: Automatic differentiation
   - requires_grad, backward()
   - Computational graph
   - Detaching tensors

3. **03_nn.py**: Neural networks
   - nn.Module
   - Layers and activations
   - Building custom networks

4. **04_training.py**: Training
   - Loss functions
   - Optimizers
   - Training loops

5. **05_cifar10.py**: Complete example
   - CIFAR-10 classification
   - CNN architecture
   - Training and evaluation

## Type System

### Core Types

```python
# Value: Scalar with autograd support
class Value:
    data: float
    grad: float
    _backward: Callable[[], None]
    _prev: Set[Value]

# Module: Neural network component
class Module:
    def parameters(self) -> List[Value]: ...
    def __call__(self, x: Sequence[Value]) -> Value: ...
```

### Type Aliases

Common type patterns used throughout:
- `Union[Value, float]`: Value or scalar
- `Sequence[Value]`: Input to layers
- `List[Value]`: Parameters collection

## Testing

Test organization:
- `TestValue`: Core autograd operations
- `TestNeuron`: Single neuron
- `TestLayer`: Layer of neurons
- `TestMLP`: Full network
- `TestSGD`: Optimizer

All tests include:
- Forward pass verification
- Gradient computation checks
- Mathematical correctness validation

## Usage Example

```python
from micrograd.engine import Value
from micrograd.nn import MLP
from micrograd.optim import SGD

# Create model
model: MLP = MLP(2, [4, 1])
optimizer: SGD = SGD(model.parameters(), lr=0.01)

# Training loop
for epoch in range(100):
    # Forward
    x = [Value(1.0), Value(2.0)]
    out: Value = model(x)
    loss: Value = (out - target) ** 2
    
    # Backward
    optimizer.zero_grad()
    loss.backward()
    
    # Update
    optimizer.step()
```

## Future Improvements

1. Add more activation functions (sigmoid, GELU)
2. Implement additional optimizers (Adam, RMSprop)
3. Add batch processing support
4. Create more visualization tools
5. Add performance benchmarks
