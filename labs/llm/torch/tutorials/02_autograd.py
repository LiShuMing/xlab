"""
PyTorch Tutorial 2: Autograd
Based on PyTorch 60-Minute Blitz

This tutorial covers:
- Automatic differentiation
- Computational graphs
- Backward pass
- Detaching tensors
"""

import torch


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def main():
    section("AUTOMATIC DIFFERENTIATION BASICS")
    
    # Create a tensor with requires_grad=True
    print("\n1. Creating tensors with gradient tracking:")
    x = torch.ones(2, 2, requires_grad=True)
    print(f"   x = torch.ones(2, 2, requires_grad=True)")
    print(f"   x =\n{x}")
    print(f"   x.requires_grad = {x.requires_grad}")
    
    # Perform operations
    print("\n2. Performing operations:")
    y = x + 2
    print(f"   y = x + 2 =\n{y}")
    print(f"   y.requires_grad = {y.requires_grad}")
    print(f"   y.grad_fn = {y.grad_fn}")
    
    z = y * y * 3
    out = z.mean()
    
    print(f"\n   z = y * y * 3 =\n{z}")
    print(f"   z.grad_fn = {z.grad_fn}")
    print(f"\n   out = z.mean() = {out}")
    print(f"   out.grad_fn = {out.grad_fn}")
    
    section("BACKWARD PASS")
    
    print("\n3. Computing gradients:")
    print(f"   Before backward: x.grad = {x.grad}")
    
    # Compute gradients
    out.backward()
    
    print(f"   After backward: x.grad =\n{x.grad}")
    
    # Mathematical explanation
    print("\n   Math check:")
    print("   out = 1/4 * sum(z)")
    print("   z = 3 * y^2 = 3 * (x+2)^2")
    print("   d(out)/dx = 1/4 * 6 * (x+2) = 3/2 * (x+2)")
    print(f"   With x=1: d(out)/dx = 3/2 * 3 = 4.5")
    
    section("VECTOR-JACOBIAN PRODUCT")
    
    print("\n4. Non-scalar output backward:")
    x = torch.randn(3, requires_grad=True)
    print(f"   x = {x}")
    
    y = x * 2
    print(f"\n   y = x * 2 = {y}")
    
    # For non-scalar output, we need to pass a gradient vector
    v = torch.tensor([1.0, 2.0, 3.0])
    y.backward(v)
    
    print(f"\n   y.backward({v})")
    print(f"   x.grad = {x.grad}")
    print("   (This is the vector-Jacobian product)")
    
    section("STOPPING GRADIENT TRACKING")
    
    print("\n5. Ways to stop gradient tracking:")
    
    x = torch.ones(2, 2, requires_grad=True)
    print(f"   x.requires_grad = {x.requires_grad}")
    
    # Method 1: torch.no_grad()
    print("\n   Method 1: with torch.no_grad():")
    with torch.no_grad():
        y = x + 2
        print(f"      y.requires_grad = {y.requires_grad}")
    
    # Method 2: detach()
    print("\n   Method 2: .detach():")
    z = x.detach()
    print(f"      z.requires_grad = {z.requires_grad}")
    print(f"      z shares memory with x: {z.data_ptr() == x.data_ptr()}")
    
    # Method 3: Set requires_grad=False
    print("\n   Method 3: Set requires_grad=False:")
    w = x.clone()
    w.requires_grad = False
    print(f"      w.requires_grad = {w.requires_grad}")
    
    section("IN-PLACE OPERATIONS")
    
    print("\n6. In-place operations and autograd:")
    x = torch.ones(2, 2, requires_grad=True)
    print(f"   x = {x}")
    
    try:
        y = x + 2
        x.add_(1)  # In-place operation
        y.backward(torch.ones_like(y))
    except RuntimeError as e:
        print(f"   Error: {e}")
    
    print("\n   In-place ops can cause issues with autograd if they modify")
    print("   tensors needed for backward pass.")
    
    section("COMPUTATIONAL GRAPH VISUALIZATION")
    
    print("\n7. Building a computational graph:")
    
    # Reset
    x = torch.tensor(2.0, requires_grad=True)
    w = torch.tensor(3.0, requires_grad=True)
    b = torch.tensor(1.0, requires_grad=True)
    
    # Forward pass
    u = w * x
    v = u + b
    a = torch.relu(v)
    
    print(f"   x = {x.item()}")
    print(f"   w = {w.item()}")
    print(f"   b = {b.item()}")
    print(f"\n   u = w * x = {u.item()}")
    print(f"   v = u + b = {v.item()}")
    print(f"   a = relu(v) = {a.item()}")
    
    print("\n   Computational graph:")
    print("   x, w, b -> [mul] -> u -> [add] -> v -> [relu] -> a")
    
    # Backward
    a.backward()
    
    print("\n   Gradients:")
    print(f"   da/dx = {x.grad.item()}")
    print(f"   da/dw = {w.grad.item()}")
    print(f"   da/db = {b.grad.item()}")
    
    section("SUMMARY")
    print("""
    Key takeaways:
    1. Set requires_grad=True to track operations on a tensor
    2. .backward() computes gradients using reverse-mode autodiff
    3. .grad contains the gradient of the output w.r.t. the tensor
    4. Computational graph is built dynamically during forward pass
    5. Use torch.no_grad() or .detach() to disable gradient tracking
    6. In-place operations can cause issues with autograd
    """)


if __name__ == "__main__":
    main()
