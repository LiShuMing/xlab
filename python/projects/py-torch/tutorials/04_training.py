"""
PyTorch Tutorial 4: Training
Based on PyTorch 60-Minute Blitz

This tutorial covers:
- Loss functions
- Optimizers
- Training loops
- Model saving/loading
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


class SimpleClassifier(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(10, 50)
        self.fc2 = nn.Linear(50, 20)
        self.fc3 = nn.Linear(20, 2)
    
    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        x = self.fc3(x)
        return x


def main():
    section("LOSS FUNCTIONS")
    
    print("\n1. Common loss functions:")
    
    # MSE Loss (for regression)
    mse_loss = nn.MSELoss()
    predictions = torch.randn(3, 5)
    targets = torch.randn(3, 5)
    loss = mse_loss(predictions, targets)
    print(f"   MSELoss: {loss.item():.4f}")
    
    # Cross Entropy Loss (for classification)
    ce_loss = nn.CrossEntropyLoss()
    predictions = torch.randn(3, 5)  # Raw logits
    targets = torch.tensor([1, 0, 4])  # Class indices
    loss = ce_loss(predictions, targets)
    print(f"   CrossEntropyLoss: {loss.item():.4f}")
    
    # BCE Loss (for binary classification)
    bce_loss = nn.BCELoss()
    predictions = torch.sigmoid(torch.randn(3))  # Probabilities
    targets = torch.tensor([1.0, 0.0, 1.0])
    loss = bce_loss(predictions, targets)
    print(f"   BCELoss: {loss.item():.4f}")
    
    # L1 Loss
    l1_loss = nn.L1Loss()
    predictions = torch.randn(3, 5)
    targets = torch.randn(3, 5)
    loss = l1_loss(predictions, targets)
    print(f"   L1Loss: {loss.item():.4f}")
    
    section("OPTIMIZERS")
    
    print("\n2. Common optimizers:")
    
    model = SimpleClassifier()
    
    # SGD
    optimizer_sgd = optim.SGD(model.parameters(), lr=0.01)
    print(f"   SGD: lr=0.01")
    
    # SGD with momentum
    optimizer_momentum = optim.SGD(model.parameters(), lr=0.01, momentum=0.9)
    print(f"   SGD with momentum: lr=0.01, momentum=0.9")
    
    # Adam
    optimizer_adam = optim.Adam(model.parameters(), lr=0.001)
    print(f"   Adam: lr=0.001")
    
    # AdamW
    optimizer_adamw = optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.01)
    print(f"   AdamW: lr=0.001, weight_decay=0.01")
    
    # RMSprop
    optimizer_rms = optim.RMSprop(model.parameters(), lr=0.01)
    print(f"   RMSprop: lr=0.01")
    
    section("TRAINING LOOP")
    
    print("\n3. Basic training loop structure:")
    print("""
    for epoch in range(num_epochs):
        for batch_idx, (data, target) in enumerate(train_loader):
            # 1. Forward pass
            output = model(data)
            
            # 2. Compute loss
            loss = criterion(output, target)
            
            # 3. Backward pass
            optimizer.zero_grad()  # Clear gradients
            loss.backward()        # Compute gradients
            
            # 4. Update weights
            optimizer.step()       # Update parameters
    """)
    
    # Create synthetic dataset
    print("\n4. Training example with synthetic data:")
    X = torch.randn(1000, 10)
    y = torch.randint(0, 2, (1000,))
    
    dataset = TensorDataset(X, y)
    train_loader = DataLoader(dataset, batch_size=32, shuffle=True)
    
    model = SimpleClassifier()
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.01)
    
    print(f"   Dataset size: {len(dataset)}")
    print(f"   Batch size: 32")
    print(f"   Batches per epoch: {len(train_loader)}")
    
    # Train for a few epochs
    num_epochs = 3
    model.train()
    
    for epoch in range(num_epochs):
        total_loss = 0
        correct = 0
        total = 0
        
        for batch_idx, (data, target) in enumerate(train_loader):
            # Forward
            output = model(data)
            loss = criterion(output, target)
            
            # Backward
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            # Statistics
            total_loss += loss.item()
            _, predicted = output.max(1)
            total += target.size(0)
            correct += predicted.eq(target).sum().item()
            
            if batch_idx % 10 == 0:
                print(f"   Epoch {epoch+1}/{num_epochs}, "
                      f"Batch {batch_idx}/{len(train_loader)}, "
                      f"Loss: {loss.item():.4f}")
        
        avg_loss = total_loss / len(train_loader)
        accuracy = 100. * correct / total
        print(f"   === Epoch {epoch+1} Summary: Loss={avg_loss:.4f}, "
              f"Accuracy={accuracy:.2f}% ===")
    
    section("EVALUATION")
    
    print("\n5. Evaluation mode:")
    
    model.eval()
    print("   model.eval()  # Set evaluation mode")
    
    with torch.no_grad():
        print("   with torch.no_grad():")
        test_output = model(X[:10])
        _, predicted = test_output.max(1)
        print(f"   Predictions: {predicted.tolist()}")
        print(f"   Actual:      {y[:10].tolist()}")
    
    section("LEARNING RATE SCHEDULING")
    
    print("\n6. Learning rate schedulers:")
    
    model = SimpleClassifier()
    optimizer = optim.SGD(model.parameters(), lr=0.1)
    
    # StepLR
    scheduler_step = optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.1)
    print(f"   StepLR: step_size=10, gamma=0.1")
    
    # ExponentialLR
    scheduler_exp = optim.lr_scheduler.ExponentialLR(optimizer, gamma=0.95)
    print(f"   ExponentialLR: gamma=0.95")
    
    # CosineAnnealingLR
    scheduler_cos = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=100)
    print(f"   CosineAnnealingLR: T_max=100")
    
    section("MODEL SAVING AND LOADING")
    
    print("\n7. Save and load entire model:")
    
    # Save
    torch.save(model, '/tmp/model_complete.pth')
    print("   torch.save(model, 'model_complete.pth')")
    
    # Load
    loaded_model = torch.load('/tmp/model_complete.pth', weights_only=False)
    print("   model = torch.load('model_complete.pth')")
    
    print("\n8. Save and load only state dict (recommended):")
    
    # Save
    torch.save(model.state_dict(), '/tmp/model_state.pth')
    print("   torch.save(model.state_dict(), 'model_state.pth')")
    
    # Load
    model = SimpleClassifier()
    model.load_state_dict(torch.load('/tmp/model_state.pth', weights_only=True))
    print("   model.load_state_dict(torch.load('model_state.pth'))")
    
    print("\n9. Save checkpoint with optimizer:")
    checkpoint = {
        'epoch': 10,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'loss': 0.5,
    }
    torch.save(checkpoint, '/tmp/checkpoint.pth')
    print("   Saved checkpoint with epoch, model, optimizer, and loss")
    
    # Load checkpoint
    checkpoint = torch.load('/tmp/checkpoint.pth', weights_only=False)
    model.load_state_dict(checkpoint['model_state_dict'])
    optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
    epoch = checkpoint['epoch']
    loss = checkpoint['loss']
    print(f"   Loaded: epoch={epoch}, loss={loss}")
    
    section("SUMMARY")
    print("""
    Key takeaways:
    1. Loss functions: MSELoss (regression), CrossEntropyLoss (classification)
    2. Optimizers: SGD, Adam, AdamW - each with different characteristics
    3. Training loop: forward -> loss -> zero_grad -> backward -> step
    4. Use model.train() for training, model.eval() for evaluation
    5. Use torch.no_grad() during evaluation to save memory
    6. Save/load state_dict for portability, entire model for simplicity
    7. Learning rate schedulers adjust LR during training
    """)


if __name__ == "__main__":
    main()
