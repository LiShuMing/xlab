"""
PyTorch Tutorial 5: Complete CIFAR-10 Example
Based on PyTorch 60-Minute Blitz

This tutorial covers a complete training pipeline on CIFAR-10.
"""

import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


class CIFAR10Net(nn.Module):
    """CNN for CIFAR-10 classification."""
    
    def __init__(self):
        super(CIFAR10Net, self).__init__()
        # Convolutional layers
        self.conv1 = nn.Conv2d(3, 32, 3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, 3, padding=1)
        self.conv3 = nn.Conv2d(64, 128, 3, padding=1)
        
        # Pooling and dropout
        self.pool = nn.MaxPool2d(2, 2)
        self.dropout = nn.Dropout(0.25)
        
        # Fully connected layers
        # After 3 poolings: 32x32 -> 16x16 -> 8x8 -> 4x4
        self.fc1 = nn.Linear(128 * 4 * 4, 512)
        self.fc2 = nn.Linear(512, 10)
        
        self.bn1 = nn.BatchNorm2d(32)
        self.bn2 = nn.BatchNorm2d(64)
        self.bn3 = nn.BatchNorm2d(128)
    
    def forward(self, x):
        # Conv block 1: 32x32 -> 16x16
        x = self.pool(torch.relu(self.bn1(self.conv1(x))))
        # Conv block 2: 16x16 -> 8x8
        x = self.pool(torch.relu(self.bn2(self.conv2(x))))
        # Conv block 3: 8x8 -> 4x4
        x = self.pool(torch.relu(self.bn3(self.conv3(x))))
        
        # Flatten
        x = x.view(x.size(0), -1)
        
        # FC layers
        x = self.dropout(x)
        x = torch.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        return x


def train_epoch(model, loader, criterion, optimizer, device):
    """Train for one epoch."""
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0
    
    for batch_idx, (inputs, targets) in enumerate(loader):
        inputs, targets = inputs.to(device), targets.to(device)
        
        # Forward pass
        outputs = model(inputs)
        loss = criterion(outputs, targets)
        
        # Backward pass
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        # Statistics
        running_loss += loss.item()
        _, predicted = outputs.max(1)
        total += targets.size(0)
        correct += predicted.eq(targets).sum().item()
        
        if batch_idx % 100 == 0:
            print(f'      Batch {batch_idx}/{len(loader)}, '
                  f'Loss: {loss.item():.4f}')
    
    epoch_loss = running_loss / len(loader)
    epoch_acc = 100. * correct / total
    return epoch_loss, epoch_acc


def evaluate(model, loader, criterion, device):
    """Evaluate model on validation/test set."""
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    
    with torch.no_grad():
        for inputs, targets in loader:
            inputs, targets = inputs.to(device), targets.to(device)
            
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            
            running_loss += loss.item()
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()
    
    epoch_loss = running_loss / len(loader)
    epoch_acc = 100. * correct / total
    return epoch_loss, epoch_acc


def main():
    section("CIFAR-10 CLASSIFICATION")
    
    # Configuration
    batch_size = 128
    num_epochs = 5
    learning_rate = 0.001
    
    print(f"\nConfiguration:")
    print(f"   Batch size: {batch_size}")
    print(f"   Epochs: {num_epochs}")
    print(f"   Learning rate: {learning_rate}")
    
    # Device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"   Device: {device}")
    
    section("DATA PREPARATION")
    
    # Data augmentation for training
    transform_train = transforms.Compose([
        transforms.RandomCrop(32, padding=4),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize((0.4914, 0.4822, 0.4465), 
                            (0.2023, 0.1994, 0.2010)),
    ])
    
    # Simple transform for test
    transform_test = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.4914, 0.4822, 0.4465), 
                            (0.2023, 0.1994, 0.2010)),
    ])
    
    print("\nDownloading CIFAR-10 dataset...")
    
    # Datasets
    trainset = torchvision.datasets.CIFAR10(
        root='./data', train=True, download=True, transform=transform_train)
    testset = torchvision.datasets.CIFAR10(
        root='./data', train=False, download=True, transform=transform_test)
    
    # Dataloaders
    trainloader = DataLoader(trainset, batch_size=batch_size, 
                             shuffle=True, num_workers=2)
    testloader = DataLoader(testset, batch_size=batch_size, 
                            shuffle=False, num_workers=2)
    
    print(f"   Train samples: {len(trainset)}")
    print(f"   Test samples: {len(testset)}")
    print(f"   Classes: {trainset.classes}")
    
    section("MODEL")
    
    model = CIFAR10Net().to(device)
    print(f"\nModel architecture:")
    print(model)
    
    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() 
                          if p.requires_grad)
    print(f"\nTotal parameters: {total_params:,}")
    print(f"Trainable parameters: {trainable_params:,}")
    
    section("TRAINING")
    
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=2, gamma=0.1)
    
    print(f"\nLoss: CrossEntropyLoss")
    print(f"Optimizer: Adam (lr={learning_rate})")
    print(f"Scheduler: StepLR (step=2, gamma=0.1)")
    
    best_acc = 0.0
    
    for epoch in range(num_epochs):
        print(f"\n   Epoch {epoch+1}/{num_epochs}")
        print(f"   LR: {scheduler.get_last_lr()[0]:.6f}")
        
        # Train
        train_loss, train_acc = train_epoch(
            model, trainloader, criterion, optimizer, device)
        
        # Evaluate
        test_loss, test_acc = evaluate(model, testloader, criterion, device)
        
        # Scheduler step
        scheduler.step()
        
        print(f"   Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.2f}%")
        print(f"   Test Loss: {test_loss:.4f}, Test Acc: {test_acc:.2f}%")
        
        # Save best model
        if test_acc > best_acc:
            best_acc = test_acc
            torch.save(model.state_dict(), '/tmp/cifar10_best.pth')
            print(f"   *** Best model saved! ***")
    
    section("RESULTS")
    
    print(f"\nBest test accuracy: {best_acc:.2f}%")
    
    # Final evaluation with best model
    model.load_state_dict(torch.load('/tmp/cifar10_best.pth', weights_only=True))
    final_loss, final_acc = evaluate(model, testloader, criterion, device)
    print(f"Final test accuracy: {final_acc:.2f}%")
    
    # Per-class accuracy
    print("\nPer-class accuracy:")
    class_correct = list(0. for _ in range(10))
    class_total = list(0. for _ in range(10))
    
    model.eval()
    with torch.no_grad():
        for inputs, targets in testloader:
            inputs, targets = inputs.to(device), targets.to(device)
            outputs = model(inputs)
            _, predicted = outputs.max(1)
            c = (predicted == targets).squeeze()
            for i in range(len(targets)):
                label = targets[i]
                class_correct[label] += c[i].item()
                class_total[label] += 1
    
    for i, classname in enumerate(trainset.classes):
        accuracy = 100 * class_correct[i] / class_total[i]
        print(f"   {classname:12s}: {accuracy:.2f}%")
    
    section("SUMMARY")
    print("""
    Key takeaways:
    1. Data augmentation improves generalization
    2. Normalization helps training stability
    3. Learning rate scheduling improves convergence
    4. Validation set prevents overfitting
    5. Save best model based on validation accuracy
    6. Per-class accuracy reveals class-specific issues
    """)


if __name__ == "__main__":
    main()
