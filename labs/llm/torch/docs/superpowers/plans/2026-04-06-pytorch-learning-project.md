# PyTorch Learning Project Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete PyTorch learning project including Karpathy's micrograd autograd implementation and PyTorch 60 min blitz tutorials.

**Architecture:** The project has two main components: 1) A from-scratch autograd engine (micrograd) demonstrating automatic differentiation principles, and 2) PyTorch official tutorial implementations organized by topic. Both include comprehensive tests and documentation.

**Tech Stack:** Python 3.8+, PyTorch, NumPy, Matplotlib, pytest

---

## File Structure

```
py-torch/
├── micrograd/                  # Karpathy's autograd from scratch
│   ├── __init__.py
│   ├── engine.py               # Core Value class with autograd
│   ├── nn.py                   # Neural network layers
│   ├── optim.py                # Optimizers (SGD)
│   └── utils.py                # Visualization helpers
├── tutorials/                  # PyTorch 60 min blitz
│   ├── 01_tensors.py           # Tensor basics
│   ├── 02_autograd.py          # Automatic differentiation
│   ├── 03_nn.py                # Neural networks
│   ├── 04_training.py          # Training loops
│   └── 05_cifar10.py           # Complete example
├── tests/
│   ├── test_micrograd.py       # Micrograd unit tests
│   └── test_tutorials.py       # Tutorial validation tests
├── requirements.txt
└── README.md
```

---

## Task 1: Project Structure and Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `README.md`
- Create: `micrograd/__init__.py`
- Create: `tutorials/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
torch>=2.0.0
numpy>=1.24.0
matplotlib>=3.7.0
pytest>=7.4.0
```

- [ ] **Step 2: Create README.md**

Create comprehensive README with:
- Project overview
- Installation instructions (`pip install -r requirements.txt`)
- How to run tutorials (`python tutorials/01_tensors.py`)
- How to run tests (`pytest tests/`)
- Project structure explanation

- [ ] **Step 3: Create __init__.py files**

Create empty `__init__.py` files in micrograd/, tutorials/, and tests/ directories.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt README.md micrograd/__init__.py tutorials/__init__.py tests/__init__.py
git commit -m "chore: initial project structure"
```

---

## Task 2: Micrograd Engine - Core Value Class

**Files:**
- Create: `micrograd/engine.py`
- Test: `tests/test_micrograd.py`

- [ ] **Step 1: Write test for Value class initialization**

```python
def test_value_init():
    from micrograd.engine import Value
    a = Value(5.0)
    assert a.data == 5.0
    assert a.grad == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_micrograd.py::test_value_init -v
```
Expected: FAIL - ImportError

- [ ] **Step 3: Implement Value class with basic operations**

```python
class Value:
    def __init__(self, data, _children=(), _op='', label=''):
        self.data = data
        self.grad = 0.0
        self._backward = lambda: None
        self._prev = set(_children)
        self._op = _op
        self.label = label
    
    def __repr__(self):
        return f"Value(data={self.data})"
    
    def __add__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        out = Value(self.data + other.data, (self, other), '+')
        def _backward():
            self.grad += out.grad
            other.grad += out.grad
        out._backward = _backward
        return out
```

- [ ] **Step 4: Add multiply operation**

```python
def __mul__(self, other):
    other = other if isinstance(other, Value) else Value(other)
    out = Value(self.data * other.data, (self, other), '*')
    def _backward():
        self.grad += other.data * out.grad
        other.grad += self.data * out.grad
    out._backward = _backward
    return out
```

- [ ] **Step 5: Add power operation**

```python
def __pow__(self, other):
    assert isinstance(other, (int, float)), "only supporting int/float powers"
    out = Value(self.data**other, (self,), f'**{other}')
    def _backward():
        self.grad += (other * self.data**(other-1)) * out.grad
    out._backward = _backward
    return out
```

- [ ] **Step 6: Add ReLU activation**

```python
def relu(self):
    out = Value(0 if self.data < 0 else self.data, (self,), 'ReLU')
    def _backward():
        self.grad += (out.data > 0) * out.grad
    out._backward = _backward
    return out
```

- [ ] **Step 7: Add backward pass (autograd)**

```python
def backward(self):
    topo = []
    visited = set()
    def build_topo(v):
        if v not in visited:
            visited.add(v)
            for child in v._prev:
                build_topo(child)
            topo.append(v)
    build_topo(self)
    
    self.grad = 1.0
    for node in reversed(topo):
        node._backward()
```

- [ ] **Step 8: Run all tests**

```bash
pytest tests/test_micrograd.py -v
```
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add micrograd/engine.py tests/test_micrograd.py
git commit -m "feat(micrograd): implement core Value class with autograd"
```

---

## Task 3: Micrograd Neural Network Module

**Files:**
- Create: `micrograd/nn.py`
- Modify: `tests/test_micrograd.py`

- [ ] **Step 1: Write test for Neuron**

```python
def test_neuron():
    from micrograd.nn import Neuron
    n = Neuron(3)
    x = [Value(1.0), Value(2.0), Value(3.0)]
    out = n(x)
    assert isinstance(out, Value)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_micrograd.py::test_neuron -v
```
Expected: FAIL - ImportError

- [ ] **Step 3: Implement Neuron class**

```python
import random
from micrograd.engine import Value

class Neuron:
    def __init__(self, nin, nonlin=True):
        self.w = [Value(random.uniform(-1, 1)) for _ in range(nin)]
        self.b = Value(0)
        self.nonlin = nonlin
    
    def __call__(self, x):
        act = sum((wi*xi for wi, xi in zip(self.w, x)), self.b)
        return act.relu() if self.nonlin else act
    
    def parameters(self):
        return self.w + [self.b]
```

- [ ] **Step 4: Implement Layer class**

```python
class Layer:
    def __init__(self, nin, nout, **kwargs):
        self.neurons = [Neuron(nin, **kwargs) for _ in range(nout)]
    
    def __call__(self, x):
        outs = [n(x) for n in self.neurons]
        return outs[0] if len(outs) == 1 else outs
    
    def parameters(self):
        return [p for n in self.neurons for p in n.parameters()]
```

- [ ] **Step 5: Implement MLP class**

```python
class MLP:
    def __init__(self, nin, nouts):
        sz = [nin] + nouts
        self.layers = [Layer(sz[i], sz[i+1], nonlin=i!=len(nouts)-1) 
                       for i in range(len(nouts))]
    
    def __call__(self, x):
        for layer in self.layers:
            x = layer(x)
        return x
    
    def parameters(self):
        return [p for layer in self.layers for p in layer.parameters()]
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_micrograd.py -v
```
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add micrograd/nn.py tests/test_micrograd.py
git commit -m "feat(micrograd): implement neural network layers (Neuron, Layer, MLP)"
```

---

## Task 4: Micrograd Optimizer

**Files:**
- Create: `micrograd/optim.py`
- Modify: `tests/test_micrograd.py`

- [ ] **Step 1: Write test for SGD**

```python
def test_sgd():
    from micrograd.nn import MLP
    from micrograd.optim import SGD
    model = MLP(3, [4, 1])
    optimizer = SGD(model.parameters(), lr=0.01)
    # Test step runs without error
    optimizer.step()
    optimizer.zero_grad()
```

- [ ] **Step 2: Implement SGD optimizer**

```python
class SGD:
    def __init__(self, parameters, lr=0.01):
        self.parameters = parameters
        self.lr = lr
    
    def step(self):
        for p in self.parameters:
            p.data -= self.lr * p.grad
    
    def zero_grad(self):
        for p in self.parameters:
            p.grad = 0
```

- [ ] **Step 3: Run tests and commit**

```bash
pytest tests/test_micrograd.py::test_sgd -v
git add micrograd/optim.py tests/test_micrograd.py
git commit -m "feat(micrograd): add SGD optimizer"
```

---

## Task 5: Micrograd Visualization Utils

**Files:**
- Create: `micrograd/utils.py`

- [ ] **Step 1: Implement trace function for graph visualization**

```python
def trace(root):
    nodes, edges = set(), set()
    def build(v):
        if v not in nodes:
            nodes.add(v)
            for child in v._prev:
                edges.add((child, v))
                build(child)
    build(root)
    return nodes, edges
```

- [ ] **Step 2: Implement draw_dot function**

```python
def draw_dot(root):
    from graphviz import Digraph
    dot = Digraph(format='svg', graph_attr={'rankdir': 'LR'})
    nodes, edges = trace(root)
    
    for n in nodes:
        uid = str(id(n))
        dot.node(name=uid, label=f"{n.label}| data {n.data:.4f} | grad {n.grad:.4f}", 
                 shape='record')
        if n._op:
            dot.node(name=uid + n._op, label=n._op)
            dot.edge(uid + n._op, uid)
    
    for n1, n2 in edges:
        dot.edge(str(id(n1)), str(id(n2)) + n2._op)
    
    return dot
```

- [ ] **Step 3: Commit**

```bash
git add micrograd/utils.py
git commit -m "feat(micrograd): add visualization utilities"
```

---

## Task 6: PyTorch Tutorial 1 - Tensors

**Files:**
- Create: `tutorials/01_tensors.py`

- [ ] **Step 1: Write tensor basics tutorial**

Cover:
- Tensor initialization (zeros, ones, rand, from data)
- Tensor attributes (shape, dtype, device)
- Tensor operations (add, mul, matmul)
- In-place operations
- NumPy bridge
- GPU tensors (if available)

- [ ] **Step 2: Add test**

```python
def test_tensors_tutorial():
    import torch
    # Test basic tensor creation
    x = torch.zeros(2, 3)
    assert x.shape == (2, 3)
    # Test operations
    y = torch.ones(2, 3)
    z = x + y
    assert torch.all(z == 1)
```

- [ ] **Step 3: Commit**

```bash
git add tutorials/01_tensors.py tests/test_tutorials.py
git commit -m "feat(tutorials): add tensor basics tutorial"
```

---

## Task 7: PyTorch Tutorial 2 - Autograd

**Files:**
- Create: `tutorials/02_autograd.py`

- [ ] **Step 1: Write autograd tutorial**

Cover:
- requires_grad flag
- Computing gradients with backward()
- Computational graph
- Detaching tensors
- Gradient accumulation and zero_grad

- [ ] **Step 2: Commit**

```bash
git add tutorials/02_autograd.py
git commit -m "feat(tutorials): add autograd tutorial"
```

---

## Task 8: PyTorch Tutorial 3 - Neural Networks

**Files:**
- Create: `tutorials/03_nn.py`

- [ ] **Step 1: Write neural networks tutorial**

Cover:
- nn.Module base class
- Layers (Linear, Conv2d, etc.)
- Activation functions
- Building a simple network
- Moving to GPU

- [ ] **Step 2: Commit**

```bash
git add tutorials/03_nn.py
git commit -m "feat(tutorials): add neural networks tutorial"
```

---

## Task 9: PyTorch Tutorial 4 - Training

**Files:**
- Create: `tutorials/04_training.py`

- [ ] **Step 1: Write training tutorial**

Cover:
- Loss functions (MSELoss, CrossEntropyLoss)
- Optimizers (SGD, Adam)
- Training loop structure
- Evaluation mode
- Saving/loading models

- [ ] **Step 2: Commit**

```bash
git add tutorials/04_training.py
git commit -m "feat(tutorials): add training tutorial"
```

---

## Task 10: PyTorch Tutorial 5 - Complete CIFAR-10 Example

**Files:**
- Create: `tutorials/05_cifar10.py`

- [ ] **Step 1: Write complete training example**

Implement:
- Data loading (using torchvision)
- CNN architecture
- Training loop with progress tracking
- Validation
- Accuracy metrics

- [ ] **Step 2: Commit**

```bash
git add tutorials/05_cifar10.py
git commit -m "feat(tutorials): add complete CIFAR-10 example"
```

---

## Task 11: Micrograd Demo Script

**Files:**
- Create: `examples/micrograd_demo.py`

- [ ] **Step 1: Create comprehensive demo**

Show:
- Value operations
- Backward pass visualization
- Training a simple classifier
- Comparison with PyTorch results

- [ ] **Step 2: Commit**

```bash
git add examples/micrograd_demo.py
git commit -m "feat(examples): add micrograd demonstration script"
```

---

## Final Verification

- [ ] Run all tests: `pytest tests/ -v`
- [ ] Run tutorials: `python tutorials/01_tensors.py`
- [ ] Run demo: `python examples/micrograd_demo.py`

---

## Spec Coverage Checklist

- [x] Karpathy micrograd autograd implementation
- [x] PyTorch 60 min blitz tutorials
- [x] Neural network layers (Neuron, Layer, MLP)
- [x] Optimizer (SGD)
- [x] Training loop examples
- [x] Complete CIFAR-10 example
- [x] Comprehensive tests
- [x] Documentation and README
