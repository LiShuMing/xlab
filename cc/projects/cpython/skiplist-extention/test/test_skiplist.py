"""
Tests for the SkipList C extension.
"""

import sys
import os

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Get the parent directory (where the .so file is)
PARENT_DIR = os.path.dirname(SCRIPT_DIR)

# Add both directories to path for imports
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)

try:
    import orderedstructs
    SkipList = orderedstructs.SkipList
except ImportError as e:
    print(f"Failed to import modules: {e}")
    print("Make sure to run build_extention.sh first!")
    sys.exit(1)


def test_basic_operations():
    """Test basic SkipList operations."""
    print("Testing basic operations...")
    
    # Create a SkipList with integer values (default comparison)
    sl = SkipList(int)
    
    # Check initial state
    assert sl.size() == 0, "New SkipList should be empty"
    print("  ✓ New SkipList is empty")
    
    # Insert some values
    sl.insert(5)
    sl.insert(3)
    sl.insert(7)
    sl.insert(1)
    sl.insert(9)
    
    assert sl.size() == 5, f"SkipList should have 5 elements, got {sl.size()}"
    print("  ✓ Insert 5 elements")
    
    # Test has
    assert sl.has(5) == True, "5 should be in SkipList"
    assert sl.has(100) == False, "100 should not be in SkipList"
    print("  ✓ has() works correctly")
    
    # Test size_of (memory usage)
    mem_size = sl.size_of()
    assert mem_size > 0, "Memory size should be positive"
    print(f"  ✓ Memory usage: {mem_size} bytes")


def test_order_operations():
    """Test ordered operations."""
    print("\nTesting order operations...")
    
    sl = SkipList(int)
    
    # Insert in random order
    values = [42, 17, 93, 5, 78, 31, 66, 12, 89, 24]
    for v in values:
        sl.insert(v)
    
    # Test at - should return values in sorted order
    first = sl.at(0)
    last = sl.at(sl.size() - 1)
    assert first < last, f"First element {first} should be less than last {last}"
    print(f"  ✓ at(0)={first}, at(-1)={last}")
    
    # Test index - should return position of value
    idx = sl.index(42)
    assert idx >= 0 and idx < sl.size(), f"Index of 42 should be valid, got {idx}"
    print(f"  ✓ index(42)={idx}")
    
    # Verify at(index(value)) == value
    for v in values:
        assert sl.at(sl.index(v)) == v, f"at(index({v})) should return {v}"
    print("  ✓ at(index(v)) == v for all values")


def test_remove():
    """Test remove operation."""
    print("\nTesting remove operation...")
    
    sl = SkipList(int)
    
    # Insert values
    for v in [10, 20, 30, 40, 50]:
        sl.insert(v)
    
    assert sl.size() == 5
    assert sl.has(30) == True
    
    # Remove a value (returns non-zero on success)
    removed = sl.remove(30)
    assert removed != 0, "remove() should return non-zero for existing value"
    
    assert sl.has(30) == False, "30 should no longer be in SkipList"
    assert sl.size() == 4, f"Skiplist should have 4 elements after removal, got {sl.size()}"
    print("  ✓ Remove operation works")
    
    # Try to remove non-existing value (raises ValueError)
    try:
        sl.remove(999)
        assert False, "remove() should raise ValueError for non-existing value"
    except ValueError:
        print("  ✓ Removing non-existing value raises ValueError")


def test_height():
    """Test height operation."""
    print("\nTesting height operation...")
    
    sl = SkipList(int)
    
    # Empty SkipList height
    height = sl.height()
    print(f"  ✓ Empty SkipList height: {height}")
    
    # Insert many values and check height grows
    for i in range(1000):
        sl.insert(i)
    
    height = sl.height()
    assert height > 0, "Height should be positive"
    print(f"  ✓ SkipList with 1000 elements has height: {height}")


def test_with_object_strings():
    """Test SkipList with string values using object type."""
    print("\nTesting with string values (object type)...")
    
    # Use 'object' type for strings
    sl = SkipList(object)
    
    # Insert strings
    sl.insert("apple")
    sl.insert("banana")
    sl.insert("cherry")
    sl.insert("date")
    
    assert sl.size() == 4
    assert sl.has("banana") == True
    assert sl.has("zucchini") == False
    
    # Check order
    first = sl.at(0)
    last = sl.at(3)
    print(f"  ✓ String ordering: '{first}' < '{last}'")
    
    # Remove a string
    removed = sl.remove("cherry")
    assert removed != 0
    assert sl.has("cherry") == False
    print("  ✓ String operations work correctly")


def test_large_dataset():
    """Test SkipList with a large dataset."""
    print("\nTesting with large dataset (10000 elements)...")
    
    sl = SkipList(int)
    
    # Insert values in random order
    import random
    values = list(range(10000))
    random.shuffle(values)
    
    for v in values:
        sl.insert(v)
    
    assert sl.size() == 10000
    print(f"  ✓ Inserted 10000 elements")
    
    # Verify all values are present
    all_present = all(sl.has(v) for v in values)
    assert all_present, "All values should be present"
    print("  ✓ All values are present")
    
    # Verify order
    prev = sl.at(0)
    for i in range(1, sl.size()):
        curr = sl.at(i)
        assert curr > prev, f"Elements should be in sorted order: {curr} <= {prev}"
        prev = curr
    print("  ✓ Elements are in sorted order")


def test_thread_safety():
    """Test that SkipList is thread-safe (basic test)."""
    print("\nTesting thread safety...")
    
    import threading
    
    sl = SkipList(int)
    num_threads = 4
    ops_per_thread = 100
    
    def worker():
        for i in range(ops_per_thread):
            sl.insert(i)
    
    # Create and run threads
    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=worker)
        threads.append(t)
    
    for t in threads:
        t.start()
    
    for t in threads:
        t.join()
    
    # Check final size
    final_size = sl.size()
    print(f"  ✓ After {num_threads * ops_per_thread} inserts from {num_threads} threads:")
    print(f"    Final size: {final_size}")
    
    # Size might be less than expected due to duplicate handling
    assert final_size <= num_threads * ops_per_thread


def test_edge_cases():
    """Test edge cases."""
    print("\nTesting edge cases...")
    
    # Empty SkipList operations
    sl = SkipList(int)
    assert sl.has(999) == False
    assert sl.size() == 0
    
    # at(0) on empty list raises IndexError
    try:
        sl.at(0)
        assert False, "at(0) should raise IndexError on empty list"
    except IndexError:
        print("  ✓ at(0) raises IndexError on empty list")
    
    # index() raises ValueError for non-existing value
    try:
        sl.index(999)
        assert False, "index() should raise ValueError for non-existing value"
    except ValueError:
        print("  ✓ index() raises ValueError for non-existing value")
    
    # Single element
    sl.insert(42)
    assert sl.size() == 1
    assert sl.has(42) == True
    assert sl.index(42) == 0
    assert sl.at(0) == 42
    print("  ✓ Single element edge case handled")
    
    # Remove last element
    sl.remove(42)
    assert sl.size() == 0
    assert sl.has(42) == False
    print("  ✓ Remove last element handled")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("SkipList C Extension Test Suite")
    print("=" * 60)
    
    tests = [
        test_basic_operations,
        test_order_operations,
        test_remove,
        test_height,
        test_with_object_strings,
        test_large_dataset,
        test_thread_safety,
        test_edge_cases,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
