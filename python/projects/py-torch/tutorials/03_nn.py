"""
PyTorch Tutorial 3: Neural Networks
Based on PyTorch 60-Minute Blitz

This tutorial covers:
- nn.Module
- Common layers
- Activation functions
- Building custom networks
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


class SimpleNet(nn.Module):
    """A simple neural network example."""
    
    def __init__(self, input_size, hidden_size, num_classes):
        super(SimpleNet, self).__init__()
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_size, num_classes)
    
    def forward(self, x):
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        return x


class ConvNet(nn.Module):
    """A simple CNN for image classification."""
    
    def __init__(self, num_classes=10):
        super(ConvNet, self).__init__()
        self.conv1 = nn.Conv2d(1, 16, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.pool = nn.MaxPool2d(2, 2)
        self.fc1 = nn.Linear(32 * 7 * 7, 128)
        self.fc2 = nn.Linear(128, num_classes)
        self.dropout = nn.Dropout(0.5)
    
    def forward(self, x):
        # Conv block 1
        x = self.pool(F.relu(self.conv1(x)))  # 28x28 -> 14x14
        # Conv block 2
        x = self.pool(F.relu(self.conv2(x)))  # 14x14 -> 7x7
        # Flatten
        x = x.view(x.size(0), -1)
        # FC layers
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        return x


def main():
    section("NN.MODULE BASICS")
    
    print("\n1. Defining a neural network:")
    print("""
    class SimpleNet(nn.Module):
        def __init__(self, input_size, hidden_size, num_classes):
            super(SimpleNet, self).__init__()
            self.fc1 = nn.Linear(input_size, hidden_size)
            self.relu = nn.ReLU()
            self.fc2 = nn.Linear(hidden_size, num_classes)
        
        def forward(self, x):
            x = self.fc1(x)
            x = self.relu(x)
            x = self.fc2(x)
            return x
    """)
    
    net = SimpleNet(784, 256, 10)
    print(f"\n   Created network: {net}")
    print(f"\n   Parameters:")
    total_params = 0
    for name, param in net.named_parameters():
        params = param.numel()
        total_params += params
        print(f"      {name}: {param.shape} ({params:,} parameters)")
    print(f"\n   Total parameters: {total_params:,}")
    
    section("FORWARD PASS")
    
    # Create random input
    batch_size = 4
    input_data = torch.randn(batch_size, 784)
    print(f"\n2. Forward pass with batch of {batch_size}:")
    print(f"   Input shape: {input_data.shape}")
    
    output = net(input_data)
    print(f"   Output shape: {output.shape}")
    print(f"   Output sample:\n{output[0]}")
    
    section("COMMON LAYERS")
    
    print("\n3. Linear layer:")
    linear = nn.Linear(10, 5)
    x = torch.randn(2, 10)
    y = linear(x)
    print(f"   Input: {x.shape} -> Output: {y.shape}")
    
    print("\n4. Convolutional layer:")
    conv = nn.Conv2d(3, 16, kernel_size=3, padding=1)
    x = torch.randn(1, 3, 32, 32)
    y = conv(x)
    print(f"   Input: {x.shape} -> Output: {y.shape}")
    
    print("\n5. Pooling layers:")
    maxpool = nn.MaxPool2d(2, 2)
    avgpool = nn.AvgPool2d(2, 2)
    x = torch.randn(1, 16, 32, 32)
    print(f"   MaxPool2d(2, 2): {x.shape} -> {maxpool(x).shape}")
    print(f"   AvgPool2d(2, 2): {x.shape} -> {avgpool(x).shape}")
    
    print("\n6. Batch Normalization:")
    bn = nn.BatchNorm2d(16)
    x = torch.randn(4, 16, 32, 32)
    y = bn(x)
    print(f"   BatchNorm2d: {x.shape} -> {y.shape}")
    
    print("\n7. Dropout:")
    dropout = nn.Dropout(0.5)
    x = torch.randn(2, 100)
    net.train()  # Enable dropout
    y1 = dropout(x)
    y2 = dropout(x)
    print(f"   Dropout(0.5): {x.shape} -> {y1.shape}")
    print(f"   (Different output each forward pass in train mode)")
    print(f"   Output difference: {(y1 - y2).abs().sum().item():.4f}")
    
    section("ACTIVATION FUNCTIONS")
    
    x = torch.linspace(-3, 3, 7)
    print(f"\n8. Input: {x}")
    print(f"   ReLU:    {F.relu(x)}")
    print(f"   Sigmoid: {torch.sigmoid(x)}")
    print(f"   Tanh:    {torch.tanh(x)}")
    print(f"   GELU:    {F.gelu(x)}")
    
    section("CONVNET EXAMPLE")
    
    print("\n9. CNN for MNIST:")
    cnn = ConvNet(num_classes=10)
    print(f"   {cnn}")
    
    # Test forward pass
    x = torch.randn(4, 1, 28, 28)
    y = cnn(x)
    print(f"\n   Input: {x.shape}")
    print(f"   Output: {y.shape}")
    
    section("MOVING TO GPU")
    
    if torch.cuda.is_available():
        print("\n10. Moving network to GPU:")
        device = torch.device("cuda")
        net_gpu = SimpleNet(784, 256, 10).to(device)
        print(f"    Network on GPU: {next(net_gpu.parameters()).device}")
        
        x = torch.randn(4, 784).to(device)
        y = net_gpu(x)
        print(f"    Input device: {x.device}")
        print(f"    Output device: {y.device}")
    else:
        print("\n10. CUDA not available")
    
    section("SUMMARY")
    print("""
    Key takeaways:
    1. Define networks by subclassing nn.Module
    2. Define layers in __init__, forward pass in forward()
    3. Common layers: Linear, Conv2d, MaxPool2d, BatchNorm, Dropout
    4. Activation functions: ReLU, Sigmoid, Tanh, GELU
    5. Use .to(device) to move models and tensors to GPU
    6. Call .train() and .eval() for training/evaluation modes
    """)


if __name__ == "__main__":
    main()
