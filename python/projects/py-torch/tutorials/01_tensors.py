"""
PyTorch Tutorial 1: Tensors
Based on PyTorch 60-Minute Blitz

This tutorial covers:
- Tensor initialization
- Tensor operations
- NumPy bridge
- GPU tensors
"""

import torch
import numpy as np


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def main():
    section("TENSOR BASICS")
    
    # Initialize empty tensor
    print("\n1. Empty tensor (uninitialized):")
    x = torch.empty(3, 4)
    print(f"   torch.empty(3, 4):\n{x}")
    
    # Initialize with random values
    print("\n2. Random initialization:")
    x = torch.rand(3, 4)
    print(f"   torch.rand(3, 4):\n{x}")
    
    # Initialize with zeros
    print("\n3. Zeros initialization:")
    x = torch.zeros(3, 4, dtype=torch.long)
    print(f"   torch.zeros(3, 4, dtype=torch.long):\n{x}")
    
    # Initialize from data
    print("\n4. From data:")
    data = [[1, 2], [3, 4], [5, 6]]
    x = torch.tensor(data)
    print(f"   torch.tensor({data}):\n{x}")
    print(f"   dtype: {x.dtype}")
    
    section("TENSOR ATTRIBUTES")
    
    x = torch.rand(3, 4, 5)
    print(f"\nTensor: torch.rand(3, 4, 5)")
    print(f"   Shape: {x.shape}")
    print(f"   Dtype: {x.dtype}")
    print(f"   Device: {x.device}")
    
    section("TENSOR OPERATIONS")
    
    # Addition
    x = torch.tensor([[1, 2], [3, 4]])
    y = torch.tensor([[5, 6], [7, 8]])
    
    print(f"\n5. Addition:")
    print(f"   x =\n{x}")
    print(f"   y =\n{y}")
    print(f"   x + y =\n{x + y}")
    print(f"   torch.add(x, y) =\n{torch.add(x, y)}")
    
    # In-place addition
    print(f"\n   In-place: y.add_(x) modifies y")
    y_copy = y.clone()
    y_copy.add_(x)
    print(f"   After add_: {y_copy}")
    
    # Matrix multiplication
    print(f"\n6. Matrix multiplication:")
    a = torch.tensor([[1, 2, 3], [4, 5, 6]])
    b = torch.tensor([[7, 8], [9, 10], [11, 12]])
    print(f"   a @ b =\n{a @ b}")
    print(f"   torch.matmul(a, b) =\n{torch.matmul(a, b)}")
    
    # Element-wise multiplication
    print(f"\n7. Element-wise multiplication:")
    print(f"   x * y =\n{x * y}")
    
    # Broadcasting
    print(f"\n8. Broadcasting:")
    x = torch.tensor([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    y = torch.tensor([10, 20, 30])
    print(f"   x =\n{x}")
    print(f"   y = {y}")
    print(f"   x + y =\n{x + y}")
    
    section("RESHAPING")
    
    x = torch.randn(4, 4)
    print(f"\nOriginal shape: {x.shape}")
    
    y = x.view(16)
    print(f"view(16): {y.shape}")
    
    y = x.view(-1, 8)  # -1 lets PyTorch infer the size
    print(f"view(-1, 8): {y.shape}")
    
    y = x.view(2, 2, 4)
    print(f"view(2, 2, 4): {y.shape}")
    
    section("NUMPY BRIDGE")
    
    # Torch to NumPy
    print("\n9. Torch to NumPy:")
    a = torch.ones(5)
    print(f"   Torch tensor: {a}")
    b = a.numpy()
    print(f"   NumPy array: {b}")
    
    # Note: They share memory
    a.add_(1)
    print(f"   After add_(1) to tensor:")
    print(f"   Torch tensor: {a}")
    print(f"   NumPy array: {b}")
    
    # NumPy to Torch
    print("\n10. NumPy to Torch:")
    a = np.ones(5)
    print(f"   NumPy array: {a}")
    b = torch.from_numpy(a)
    print(f"   Torch tensor: {b}")
    
    np.add(a, 1, out=a)
    print(f"   After adding 1 to NumPy array:")
    print(f"   NumPy array: {a}")
    print(f"   Torch tensor: {b}")
    
    section("CUDA TENSORS (if available)")
    
    if torch.cuda.is_available():
        print(f"\nCUDA is available!")
        print(f"CUDA device: {torch.cuda.get_device_name(0)}")
        
        # Create tensor on GPU
        x = torch.ones(3, 3, device='cuda')
        print(f"\nTensor on GPU:\n{x}")
        print(f"Device: {x.device}")
        
        # Move tensor to GPU
        y = torch.ones(3, 3)
        y = y.to('cuda')
        print(f"\nMoved to GPU:\n{y}")
        
        # Operations on GPU
        z = x + y
        print(f"\nGPU operation result:\n{z}")
        
        # Move back to CPU
        z_cpu = z.to('cpu')
        print(f"\nBack on CPU: {z_cpu.device}")
    else:
        print("\nCUDA not available. Install PyTorch with CUDA for GPU support.")
    
    section("SUMMARY")
    print("""
    Key takeaways:
    1. Tensors are the fundamental data structure in PyTorch
    2. Similar to NumPy arrays but with GPU support and autograd
    3. Operations have both functional (torch.add) and method (tensor.add) forms
    4. In-place operations end with underscore (add_)
    5. Tensors can share memory with NumPy arrays
    6. Easy to move between CPU and GPU with .to() method
    """)


if __name__ == "__main__":
    main()
