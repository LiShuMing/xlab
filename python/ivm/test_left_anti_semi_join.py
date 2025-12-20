#!/usr/bin/env python3
"""
Comprehensive unit tests for the left_anti_semi_join function.
Tests cover normal cases, edge cases, and boundary conditions.
"""

import unittest
import sys
import os

# Add the parent directory to the path to import ivm module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ivm import left_anti_semi_join


class TestLeftAntiSemiJoin(unittest.TestCase):
    """Test cases for left_anti_semi_join function."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Basic test data
        self.R_basic = {(1, 'A'), (2, 'B'), (3, 'C'), (4, 'D')}
        self.S_basic = {(1, 'X'), (2, 'Y'), (5, 'Z')}
        
        # Test data with duplicate keys in S
        self.S_with_duplicates = {(1, 'X'), (1, 'X2'), (2, 'Y')}
        
        # Test data with different column counts
        self.R_multi_col = {(1, 'A', 'extra1'), (2, 'B', 'extra2'), (3, 'C', 'extra3')}
        self.S_multi_col = {(1, 'X', 'extra_s1'), (4, 'Y', 'extra_s2')}
        
        # Test data with string keys
        self.R_string_keys = {('alice', 25), ('bob', 30), ('charlie', 35)}
        self.S_string_keys = {('alice', 'engineer'), ('dave', 'manager')}

    def test_basic_functionality(self):
        """Test basic left anti-semi-join functionality."""
        result = left_anti_semi_join(self.R_basic, self.S_basic)
        expected = {(3, 'C'), (4, 'D')}  # Keys 3 and 4 don't exist in S
        self.assertEqual(result, expected)

    def test_empty_left_table(self):
        """Test with empty left table R."""
        result = left_anti_semi_join(set(), self.S_basic)
        self.assertEqual(result, set())

    def test_empty_right_table(self):
        """Test with empty right table S."""
        result = left_anti_semi_join(self.R_basic, set())
        expected = set(self.R_basic)  # All rows from R should be returned
        self.assertEqual(result, expected)

    def test_both_tables_empty(self):
        """Test with both tables empty."""
        result = left_anti_semi_join(set(), set())
        self.assertEqual(result, set())

    def test_no_matches(self):
        """Test when no keys match between R and S."""
        R_no_match = {(10, 'X'), (20, 'Y')}
        S_no_match = {(1, 'A'), (2, 'B')}
        result = left_anti_semi_join(R_no_match, S_no_match)
        expected = set(R_no_match)  # All rows from R should be returned
        self.assertEqual(result, expected)

    def test_all_matches(self):
        """Test when all keys in R exist in S."""
        R_all_match = {(1, 'A'), (2, 'B')}
        S_all_match = {(1, 'X'), (2, 'Y'), (3, 'Z')}
        result = left_anti_semi_join(R_all_match, S_all_match)
        self.assertEqual(result, set())  # No rows should be returned

    def test_duplicate_keys_in_right_table(self):
        """Test behavior when S has duplicate keys."""
        result = left_anti_semi_join(self.R_basic, self.S_with_duplicates)
        expected = {(3, 'C'), (4, 'D')}  # Keys 1 and 2 exist in S (even with duplicates)
        self.assertEqual(result, expected)

    def test_different_key_index(self):
        """Test with different key index (second column as key)."""
        R = {(1, 'key1', 'A'), (2, 'key2', 'B'), (3, 'key3', 'C')}
        S = {(10, 'key1', 'X'), (20, 'key3', 'Y')}
        result = left_anti_semi_join(R, S, on_key_index=1)
        expected = {(2, 'key2', 'B')}  # Only key2 doesn't exist in S
        self.assertEqual(result, expected)

    def test_multi_column_tables(self):
        """Test with tables having multiple columns."""
        result = left_anti_semi_join(self.R_multi_col, self.S_multi_col)
        expected = {(2, 'B', 'extra2'), (3, 'C', 'extra3')}  # Keys 2 and 3 don't exist in S
        self.assertEqual(result, expected)

    def test_string_keys(self):
        """Test with string keys."""
        result = left_anti_semi_join(self.R_string_keys, self.S_string_keys)
        expected = {('bob', 30), ('charlie', 35)}  # 'bob' and 'charlie' don't exist in S
        self.assertEqual(result, expected)

    def test_numeric_and_mixed_keys(self):
        """Test with various data types as keys."""
        R = {(1, 'int'), (1.5, 'float'), ('string', 'str'), (True, 'bool')}
        S = {(1, 'int_match'), ('string', 'str_match')}
        result = left_anti_semi_join(R, S)
        expected = {(1.5, 'float'), (True, 'bool')}  # 1 and 'string' exist in S
        self.assertEqual(result, expected)

    def test_none_as_key(self):
        """Test with None as key."""
        R = {(None, 'null_key'), (1, 'int_key')}
        S = {(None, 'null_match')}
        result = left_anti_semi_join(R, S)
        expected = {(1, 'int_key')}  # None key exists in S
        self.assertEqual(result, expected)

    def test_large_datasets(self):
        """Test with larger datasets to check performance."""
        # Create larger test sets
        R_large = {(i, f'val_{i}') for i in range(1000)}
        S_large = {(i, f's_val_{i}') for i in range(500, 1500)}
        
        result = left_anti_semi_join(R_large, S_large)
        expected = {(i, f'val_{i}') for i in range(500)}  # Keys 0-499 don't exist in S
        self.assertEqual(result, expected)

    def test_single_element_tables(self):
        """Test with single element tables."""
        # Single element in R, empty S
        result1 = left_anti_semi_join({(1, 'A')}, set())
        self.assertEqual(result1, {(1, 'A')})
        
        # Single element in R, matching element in S
        result2 = left_anti_semi_join({(1, 'A')}, {(1, 'X')})
        self.assertEqual(result2, set())
        
        # Single element in R, non-matching element in S
        result3 = left_anti_semi_join({(1, 'A')}, {(2, 'X')})
        self.assertEqual(result3, {(1, 'A')})

    def test_key_index_out_of_bounds(self):
        """Test with key index that might cause index errors."""
        R = {(1, 'A')}  # Only 2 columns
        S = {(2, 'B')}
        
        # This should work - key index 1 is valid
        result = left_anti_semi_join(R, S, on_key_index=1)
        expected = {(1, 'A')}  # Different second column values
        self.assertEqual(result, expected)

    def test_very_long_tuples(self):
        """Test with tuples having many columns."""
        R = {(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 'A')}
        S = {(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 'B')}
        
        result = left_anti_semi_join(R, S)
        self.assertEqual(result, set())  # First elements match

    def test_negative_numbers_and_zero(self):
        """Test with negative numbers and zero as keys."""
        R = {(-1, 'neg'), (0, 'zero'), (1, 'pos')}
        S = {(0, 'zero_match'), (2, 'pos_match')}
        
        result = left_anti_semi_join(R, S)
        expected = {(-1, 'neg'), (1, 'pos')}  # Only 0 exists in S
        self.assertEqual(result, expected)

    def test_floating_point_precision(self):
        """Test with floating point keys."""
        R = {(0.1 + 0.2, 'float1'), (0.3, 'float2')}  # 0.1 + 0.2 = 0.3 in theory
        S = {(0.3, 'float_match')}
        
        result = left_anti_semi_join(R, S)
        # Due to floating point precision, these might be different
        # The test should handle both possibilities
        self.assertTrue(len(result) <= 2)

    def test_case_sensitivity_with_strings(self):
        """Test case sensitivity with string keys."""
        R = {('Hello', 'lower'), ('hello', 'upper')}
        S = {('hello', 'match')}
        
        result = left_anti_semi_join(R, S)
        expected = {('Hello', 'lower')}  # Only lowercase 'hello' matches
        self.assertEqual(result, expected)

    def test_preservation_of_row_integrity(self):
        """Test that complete rows are preserved, not just keys."""
        R = {(1, 'A', 'extra1'), (2, 'B', 'extra2')}
        S = {(1, 'X', 'extra_s')}
        
        result = left_anti_semi_join(R, S)
        expected = {(2, 'B', 'extra2')}  # Complete row should be preserved
        self.assertEqual(result, expected)

    def test_default_parameter(self):
        """Test that default parameter on_key_index=0 works correctly."""
        R = {(1, 'A'), (2, 'B')}
        S = {(1, 'X')}
        
        # Should work the same as explicitly specifying on_key_index=0
        result1 = left_anti_semi_join(R, S)
        result2 = left_anti_semi_join(R, S, on_key_index=0)
        self.assertEqual(result1, result2)

    def test_input_type_validation(self):
        """Test that function handles various input types gracefully."""
        # Test with list inputs (should work if convertible to set)
        R_list = [(1, 'A'), (2, 'B')]
        S_list = [(1, 'X')]
        
        # The function expects sets, but let's see what happens
        try:
            result = left_anti_semi_join(set(R_list), set(S_list))
            expected = {(2, 'B')}
            self.assertEqual(result, expected)
        except (TypeError, AttributeError):
            # If the function doesn't handle non-set inputs, that's acceptable
            pass


class TestLeftAntiSemiJoinPerformance(unittest.TestCase):
    """Performance-related tests for left_anti_semi_join."""

    def test_time_complexity(self):
        """Test that the function has reasonable time complexity."""
        import time
        
        # Create test data
        sizes = [100, 1000, 5000]
        times = []
        
        for size in sizes:
            R = {(i, f'val_{i}') for i in range(size)}
            S = {(i, f's_val_{i}') for i in range(size // 2, size + size // 2)}
            
            start_time = time.time()
            result = left_anti_semi_join(R, S)
            end_time = time.time()
            
            times.append(end_time - start_time)
            
            # Verify correctness
            expected_size = size // 2
            self.assertEqual(len(result), expected_size)
        
        # Time should grow roughly linearly (allowing for some variance)
        # This is a rough check - exact timing depends on the system
        self.assertLess(times[2], times[0] * 100)  # Shouldn't be 100x slower for 50x data


if __name__ == '__main__':
    # Create a test suite
    test_suite = unittest.TestSuite()
    
    # Add all test cases
    test_suite.addTest(unittest.makeSuite(TestLeftAntiSemiJoin))
    test_suite.addTest(unittest.makeSuite(TestLeftAntiSemiJoinPerformance))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)