# PyTorch Learning Project

A comprehensive PyTorch learning project implementing Karpathy's micrograd autograd engine from scratch and PyTorch 60-minute blitz tutorials. This project follows modern Python best practices with strong typing and interface-first architecture.

## Features

- **Micrograd**: Complete autograd engine with reverse-mode automatic differentiation
- **Neural Networks**: From-scratch implementation of neurons, layers, and MLPs
- **PyTorch Tutorials**: Progressive learning path from tensors to complete CNNs
- **Strong Typing**: All code uses Python type hints
- **Interface-First Design**: Clear separation between interfaces and implementations
- **Comprehensive Tests**: Full test coverage for all components

## Project Structure

```
py-torch/
├── micrograd/              # Autograd engine from scratch
│   ├── interfaces/         # Abstract base classes (contracts)
│   │   ├── value.py        # ValueInterface
│   │   ├── module.py       # ModuleInterface
│   │   └── optimizer.py    # OptimizerInterface
│   ├── engine.py           # Value class with autograd
│   ├── nn.py               # Neural network layers
│   ├── optim.py            # SGD optimizer
│   └── utils.py            # Visualization utilities
├── tutorials/              # PyTorch 60 min blitz
│   ├── 01_tensors.py       # Tensor basics
│   ├── 02_autograd.py      # Automatic differentiation
│   ├── 03_nn.py            # Neural networks
│   ├── 04_training.py      # Training loops
│   └── 05_cifar10.py       # Complete CIFAR-10 example
├── tests/                  # Unit tests
├── examples/               # Demo scripts
├── ARCHITECTURE.md         # Implementation documentation
├── CHANGES_LOG.md          # Change history
├── TASKS.md                # Task tracking
└── requirements.txt        # Dependencies
```

## Installation

```bash
# Using the project virtual environment (recommended)
source /home/lism/.venv/general-3.12/bin/activate
pip install -r requirements.txt
```

## Quick Start

### Micrograd Example

```python
from micrograd.engine import Value
from micrograd.nn import MLP
from micrograd.optim import SGD

# Create a simple neural network
model = MLP(2, [4, 1])  # 2 inputs, 4 hidden, 1 output
optimizer = SGD(model.parameters(), lr=0.01)

# Training loop
for epoch in range(100):
    # Forward pass
    x = [Value(1.0), Value(2.0)]
    output = model(x)
    loss = (output - target) ** 2
    
    # Backward pass
    optimizer.zero_grad()
    loss.backward()
    
    # Update weights
    optimizer.step()
```

### Running Tutorials

```bash
# Tensor basics
python tutorials/01_tensors.py

# Autograd
python tutorials/02_autograd.py

# Neural networks
python tutorials/03_nn.py

# Training
python tutorials/04_training.py

# Complete CIFAR-10 example
python tutorials/05_cifar10.py
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_micrograd.py -v

# Run with coverage
pytest tests/ --cov=micrograd --cov-report=html
```

## Micrograd Demo

```bash
python examples/micrograd_demo.py
```

This demonstrates:
- Automatic differentiation from scratch
- Chain rule application
- Neural network training
- Comparison with PyTorch

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)**: Implementation details and design decisions
- **[CHANGES_LOG.md](CHANGES_LOG.md)**: Change history and development log
- **[TASKS.md](TASKS.md)**: Task tracking and progress

## Learning Path

1. **Micrograd** (`micrograd/`): Understand automatic differentiation from scratch
   - Read `engine.py` to see how autograd works
   - Study `nn.py` for neural network implementation
   - Run `examples/micrograd_demo.py` for hands-on examples

2. **Tutorials** (`tutorials/`): Learn PyTorch's high-level APIs
   - Start with `01_tensors.py` for basics
   - Progress through `02_autograd.py` and `03_nn.py`
   - Complete `05_cifar10.py` for a full example

3. **Examples** (`examples/`): See complete working examples

## Code Quality

This project follows these principles:

- **Strong Typing**: All functions have type annotations
- **Interface-First**: Abstract base classes define contracts
- **Documentation**: Comprehensive docstrings for all public APIs
- **Testing**: Full test coverage with pytest
- **English Comments**: All comments in English for accessibility

## Resources

- [PyTorch 60-Minute Blitz](https://pytorch.org/tutorials/beginner/deep_learning_60min_blitz.html)
- [Karpathy's Micrograd](https://github.com/karpathy/micrograd)
- [PyTorch Documentation](https://pytorch.org/docs/stable/index.html)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)

## License

MIT License - See LICENSE file for details.
