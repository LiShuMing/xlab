"""
Tests for PyTorch tutorials.
"""

import torch
import torch.nn as nn
import pytest


def test_tensor_creation():
    """Test basic tensor creation."""
    x = torch.zeros(2, 3)
    assert x.shape == (2, 3)
    
    y = torch.ones(3, 4)
    assert y.shape == (3, 4)
    assert y.sum().item() == 12


def test_tensor_operations():
    """Test tensor operations."""
    x = torch.tensor([[1, 2], [3, 4]], dtype=torch.float32)
    y = torch.tensor([[5, 6], [7, 8]], dtype=torch.float32)
    
    # Addition
    z = x + y
    expected = torch.tensor([[6, 8], [10, 12]], dtype=torch.float32)
    assert torch.allclose(z, expected)
    
    # Matrix multiplication
    a = torch.tensor([[1, 2, 3], [4, 5, 6]], dtype=torch.float32)
    b = torch.tensor([[7, 8], [9, 10], [11, 12]], dtype=torch.float32)
    c = a @ b
    assert c.shape == (2, 2)


def test_autograd():
    """Test automatic differentiation."""
    x = torch.tensor(2.0, requires_grad=True)
    y = x ** 3
    
    y.backward()
    
    # dy/dx = 3 * x^2 = 3 * 4 = 12
    assert x.grad.item() == 12.0


def test_neural_network():
    """Test neural network creation."""
    class SimpleNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc1 = nn.Linear(10, 5)
            self.fc2 = nn.Linear(5, 2)
        
        def forward(self, x):
            x = torch.relu(self.fc1(x))
            x = self.fc2(x)
            return x
    
    model = SimpleNet()
    
    # Test forward pass
    input_data = torch.randn(4, 10)
    output = model(input_data)
    assert output.shape == (4, 2)
    
    # Test parameter count
    params = sum(p.numel() for p in model.parameters())
    # fc1: 10*5 + 5 = 55, fc2: 5*2 + 2 = 12, total = 67
    assert params == 67


def test_optimizer():
    """Test optimizer step."""
    model = nn.Linear(10, 1)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    
    # Get initial weights
    initial_weight = model.weight.clone()
    
    # Forward, backward, step
    x = torch.randn(5, 10)
    y = torch.randn(5, 1)
    
    loss = nn.MSELoss()(model(x), y)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    
    # Weights should have changed
    assert not torch.equal(model.weight, initial_weight)


def test_training_loop():
    """Test a simple training loop."""
    # Simple model
    model = nn.Linear(5, 1)
    criterion = nn.MSELoss()
    optimizer = torch.optim.SGD(model.parameters(), lr=0.1)
    
    # Synthetic data
    X = torch.randn(100, 5)
    y = torch.randn(100, 1)
    
    # Initial loss
    initial_loss = criterion(model(X), y).item()
    
    # Train for a few steps
    for _ in range(100):
        optimizer.zero_grad()
        output = model(X)
        loss = criterion(output, y)
        loss.backward()
        optimizer.step()
    
    # Loss should decrease
    final_loss = criterion(model(X), y).item()
    assert final_loss < initial_loss


def test_model_save_load():
    """Test saving and loading model state."""
    model = nn.Linear(10, 5)
    
    # Get initial state
    initial_weight = model.weight.clone()
    
    # Save
    torch.save(model.state_dict(), '/tmp/test_model.pth')
    
    # Modify
    model.weight.data += 1.0
    assert not torch.equal(model.weight, initial_weight)
    
    # Load
    model.load_state_dict(torch.load('/tmp/test_model.pth', weights_only=True))
    assert torch.equal(model.weight, initial_weight)
