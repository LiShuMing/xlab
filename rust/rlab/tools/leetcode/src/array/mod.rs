//! Array and String Problems
//!
//! Common problems involving arrays, strings, and two-pointer techniques.

/// LeetCode 1: Two Sum
///
/// Given an array of integers `nums` and an integer `target`, return indices
/// of the two numbers such that they add up to `target`.
///
/// # Example
///
/// ```
/// use leetcode::array::two_sum;
///
/// let nums = vec![2, 7, 11, 15];
/// let target = 9;
/// let result = two_sum(nums, target);
/// assert_eq!(result, vec![0, 1]);
/// ```
pub fn two_sum(nums: Vec<i32>, target: i32) -> Vec<i32> {
    use std::collections::HashMap;
    
    let mut map = HashMap::new();
    for (i, &num) in nums.iter().enumerate() {
        let complement = target - num;
        if let Some(&j) = map.get(&complement) {
            return vec![j as i32, i as i32];
        }
        map.insert(num, i);
    }
    vec![]
}

/// LeetCode 53: Maximum Subarray
///
/// Find the contiguous subarray with the largest sum and return its sum.
pub fn max_sub_array(nums: Vec<i32>) -> i32 {
    if nums.is_empty() {
        return 0;
    }
    
    let mut max_sum = nums[0];
    let mut current_sum = nums[0];
    
    for &num in &nums[1..] {
        current_sum = num.max(current_sum + num);
        max_sum = max_sum.max(current_sum);
    }
    
    max_sum
}

/// LeetCode 121: Best Time to Buy and Sell Stock
///
/// Find the maximum profit from buying and selling a stock once.
pub fn max_profit(prices: Vec<i32>) -> i32 {
    if prices.len() < 2 {
        return 0;
    }
    
    let mut min_price = prices[0];
    let mut max_profit = 0;
    
    for &price in &prices[1..] {
        max_profit = max_profit.max(price - min_price);
        min_price = min_price.min(price);
    }
    
    max_profit
}

/// LeetCode 238: Product of Array Except Self
///
/// Return an array where each element is the product of all other elements.
pub fn product_except_self(nums: Vec<i32>) -> Vec<i32> {
    let n = nums.len();
    let mut result = vec![1; n];
    
    // Left products
    let mut left = 1;
    for i in 0..n {
        result[i] = left;
        left *= nums[i];
    }
    
    // Right products
    let mut right = 1;
    for i in (0..n).rev() {
        result[i] *= right;
        right *= nums[i];
    }
    
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_two_sum() {
        assert_eq!(two_sum(vec![2, 7, 11, 15], 9), vec![0, 1]);
        assert_eq!(two_sum(vec![3, 2, 4], 6), vec![1, 2]);
        assert_eq!(two_sum(vec![3, 3], 6), vec![0, 1]);
    }

    #[test]
    fn test_max_sub_array() {
        assert_eq!(max_sub_array(vec![-2, 1, -3, 4, -1, 2, 1, -5, 4]), 6);
        assert_eq!(max_sub_array(vec![1]), 1);
        assert_eq!(max_sub_array(vec![5, 4, -1, 7, 8]), 23);
    }

    #[test]
    fn test_max_profit() {
        assert_eq!(max_profit(vec![7, 1, 5, 3, 6, 4]), 5);
        assert_eq!(max_profit(vec![7, 6, 4, 3, 1]), 0);
    }

    #[test]
    fn test_product_except_self() {
        assert_eq!(product_except_self(vec![1, 2, 3, 4]), vec![24, 12, 8, 6]);
        assert_eq!(product_except_self(vec![-1, 1, 0, -3, 3]), vec![0, 0, 9, 0, 0]);
    }
}
