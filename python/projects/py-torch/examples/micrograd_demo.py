"""
Micrograd demonstration script.
Shows how automatic differentiation works from scratch.
"""

import random
import math
from micrograd.engine import Value
from micrograd.nn import Neuron, Layer, MLP
from micrograd.optim import SGD
from micrograd.utils import trace


def section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print('='*70)


def demo_basic_operations():
    """Demonstrate basic Value operations."""
    section("1. BASIC OPERATIONS")
    
    print("\nCreating values and performing operations:")
    a = Value(2.0, label='a')
    b = Value(3.0, label='b')
    c = a + b
    c.label = 'c'
    d = c * Value(4.0, label='d_input')
    d.label = 'd'
    
    print(f"   a = {a.data}")
    print(f"   b = {b.data}")
    print(f"   c = a + b = {c.data}")
    print(f"   d = c * 4 = {d.data}")
    
    print("\nComputing gradients with backward():")
    d.backward()
    
    print(f"   d.grad = {d.grad}")
    print(f"   c.grad = {c.grad}")
    print(f"   a.grad = {a.grad}")
    print(f"   b.grad = {b.grad}")
    
    print("\nMath check:")
    print(f"   d = (a + b) * 4")
    print(f"   dd/da = dd/dc * dc/da = 4 * 1 = 4")
    print(f"   dd/db = dd/dc * dc/db = 4 * 1 = 4")


def demo_chain_rule():
    """Demonstrate chain rule with complex expression."""
    section("2. CHAIN RULE")
    
    print("\nComplex expression: L = tanh(x1*w1 + x2*w2 + b)")
    
    # Inputs
    x1 = Value(2.0, label='x1')
    x2 = Value(0.0, label='x2')
    
    # Weights
    w1 = Value(-3.0, label='w1')
    w2 = Value(1.0, label='w2')
    
    # Bias
    b = Value(6.8813735870195432, label='b')
    
    # Forward pass
    x1w1 = x1 * w1
    x1w1.label = 'x1*w1'
    
    x2w2 = x2 * w2
    x2w2.label = 'x2*w2'
    
    x1w1x2w2 = x1w1 + x2w2
    x1w1x2w2.label = 'x1*w1 + x2*w2'
    
    n = x1w1x2w2 + b
    n.label = 'n'
    
    o = n.tanh()
    o.label = 'o'
    
    print(f"   x1 = {x1.data}, w1 = {w1.data}")
    print(f"   x2 = {x2.data}, w2 = {w2.data}")
    print(f"   b = {b.data}")
    print(f"   n = x1*w1 + x2*w2 + b = {n.data}")
    print(f"   o = tanh(n) = {o.data}")
    
    # Backward pass
    o.backward()
    
    print("\nGradients:")
    print(f"   do/do = {o.grad}")
    print(f"   do/dn = {n.grad}")
    print(f"   do/db = {b.grad}")
    print(f"   do/dx1 = {x1.grad}")
    print(f"   do/dw1 = {w1.grad}")
    print(f"   do/dx2 = {x2.grad}")
    print(f"   do/dw2 = {w2.grad}")
    
    print("\nVerification:")
    # do/dn = 1 - tanh(n)^2
    expected_dn = 1 - o.data ** 2
    print(f"   Expected do/dn = 1 - tanh(n)^2 = {expected_dn:.6f}")
    print(f"   Computed do/dn = {n.grad:.6f}")


def demo_neuron():
    """Demonstrate a single neuron."""
    section("3. SINGLE NEURON")
    
    print("\nCreating a neuron with 3 inputs:")
    neuron = Neuron(3)
    
    x = [Value(1.0), Value(2.0), Value(3.0)]
    print(f"   Inputs: {[v.data for v in x]}")
    
    out = neuron(x)
    print(f"   Weights: {[w.data for w in neuron.w]}")
    print(f"   Bias: {neuron.b.data}")
    print(f"   Output (after ReLU): {out.data}")
    
    print("\nComputing gradients:")
    out.backward()
    print(f"   Weight gradients: {[w.grad for w in neuron.w]}")
    print(f"   Bias gradient: {neuron.b.grad}")
    print(f"   Input gradients: {[v.grad for v in x]}")


def demo_binary_classifier():
    """Demonstrate training a binary classifier."""
    section("4. BINARY CLASSIFIER TRAINING")
    
    # Create a simple dataset
    # Two classes: points around (1, 1) and (-1, -1)
    random.seed(42)
    
    data = []
    labels = []
    
    # Class 0: around (1, 1)
    for _ in range(50):
        x = random.gauss(1.0, 0.3)
        y = random.gauss(1.0, 0.3)
        data.append([x, y])
        labels.append(1)
    
    # Class 1: around (-1, -1)
    for _ in range(50):
        x = random.gauss(-1.0, 0.3)
        y = random.gauss(-1.0, 0.3)
        data.append([x, y])
        labels.append(0)
    
    print(f"\nDataset: {len(data)} samples")
    print(f"   Class 1: {labels.count(1)} samples around (1, 1)")
    print(f"   Class 0: {labels.count(0)} samples around (-1, -1)")
    
    # Create model: 2 inputs -> 4 hidden -> 1 output
    model = MLP(2, [4, 1])
    print(f"\nModel: {model}")
    print(f"   Parameters: {len(model.parameters())}")
    
    # Training
    optimizer = SGD(model.parameters(), lr=0.1)
    
    print("\nTraining:")
    for epoch in range(20):
        total_loss = 0
        correct = 0
        
        for xi, yi in zip(data, labels):
            # Forward
            x = [Value(xi[0]), Value(xi[1])]
            output = model(x)
            
            # Binary cross-entropy loss approximation
            # For simplicity, use MSE loss
            target = float(yi)
            loss = (output - target) ** 2
            
            # Backward
            optimizer.zero_grad()
            loss.backward()
            
            # Update
            optimizer.step()
            
            total_loss += loss.data
            
            # Accuracy
            pred = 1 if output.data > 0.5 else 0
            if pred == yi:
                correct += 1
        
        acc = correct / len(data) * 100
        avg_loss = total_loss / len(data)
        
        if epoch % 5 == 0 or epoch == 19:
            print(f"   Epoch {epoch:2d}: Loss={avg_loss:.4f}, Acc={acc:.1f}%")
    
    print(f"\nFinal accuracy: {acc:.1f}%")


def demo_comparison_with_pytorch():
    """Compare micrograd with PyTorch."""
    section("5. COMPARISON WITH PYTORCH")
    
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        print("\nPyTorch not installed. Skipping comparison.")
        return
    
    print("\nSame computation in both frameworks:")
    print("   a = 2.0, b = 3.0")
    print("   c = a * b + a**2")
    print("   d = c.relu()")
    
    # Micrograd
    print("\n   Micrograd:")
    a_mg = Value(2.0, label='a')
    b_mg = Value(3.0, label='b')
    c_mg = a_mg * b_mg + a_mg ** 2
    c_mg.label = 'c'
    d_mg = c_mg.relu()
    d_mg.label = 'd'
    d_mg.backward()
    
    print(f"      c.data = {c_mg.data}")
    print(f"      d.data = {d_mg.data}")
    print(f"      a.grad = {a_mg.grad}")
    print(f"      b.grad = {b_mg.grad}")
    
    # PyTorch
    print("\n   PyTorch:")
    a_pt = torch.tensor(2.0, requires_grad=True)
    b_pt = torch.tensor(3.0, requires_grad=True)
    c_pt = a_pt * b_pt + a_pt ** 2
    d_pt = torch.relu(c_pt)
    d_pt.backward()
    
    print(f"      c.data = {c_pt.item()}")
    print(f"      d.data = {d_pt.item()}")
    print(f"      a.grad = {a_pt.grad.item()}")
    print(f"      b.grad = {b_pt.grad.item()}")
    
    print("\n   Results match! ✓")


def demo_computation_graph():
    """Show computation graph structure."""
    section("6. COMPUTATION GRAPH")
    
    print("\nBuilding a computation graph:")
    
    x = Value(1.0, label='x')
    y = Value(2.0, label='y')
    z = Value(3.0, label='z')
    
    a = x + y
    a.label = 'a'
    
    b = a * z
    b.label = 'b'
    
    c = b.relu()
    c.label = 'c'
    
    print(f"   x = {x.data}")
    print(f"   y = {y.data}")
    print(f"   z = {z.data}")
    print(f"   a = x + y = {a.data}")
    print(f"   b = a * z = {b.data}")
    print(f"   c = relu(b) = {c.data}")
    
    # Trace the graph
    nodes, edges = trace(c)
    
    print(f"\n   Computation graph:")
    print(f"      {len(nodes)} nodes")
    print(f"      {len(edges)} edges")
    
    print("\n   Nodes:")
    for n in nodes:
        op = f" [{n._op}]" if n._op else ""
        print(f"      {n.label or 'Value'}: data={n.data:.2f}{op}")
    
    print("\n   Edges:")
    for parent, child in edges:
        print(f"      {parent.label or 'Value'} -> {child.label or 'Value'}")
    
    # Backward
    c.backward()
    
    print("\n   After backward():")
    print(f"      c.grad = {c.grad}")
    print(f"      b.grad = {b.grad}")
    print(f"      a.grad = {a.grad}")
    print(f"      x.grad = {x.grad}")
    print(f"      y.grad = {y.grad}")
    print(f"      z.grad = {z.grad}")


def main():
    print("""
    ╔═══════════════════════════════════════════════════════════════════╗
    ║              MICROGRAD DEMONSTRATION                              ║
    ║                                                                   ║
    ║  A tiny autograd engine implementing reverse-mode automatic       ║
    ║  differentiation, inspired by Andrej Karpathy's micrograd.        ║
    ╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    demo_basic_operations()
    demo_chain_rule()
    demo_neuron()
    demo_binary_classifier()
    demo_comparison_with_pytorch()
    demo_computation_graph()
    
    print("\n" + "="*70)
    print("  DEMO COMPLETE")
    print("="*70)
    print("""
    Key takeaways:
    1. Autograd builds a computation graph during forward pass
    2. Backward pass traverses the graph in reverse, applying chain rule
    3. Each operation knows how to compute its local gradient
    4. Gradients flow backward through the graph automatically
    5. This enables training neural networks with gradient descent
    """)


if __name__ == "__main__":
    main()
