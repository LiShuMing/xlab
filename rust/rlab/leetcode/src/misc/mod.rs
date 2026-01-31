//! Miscellaneous Problems
//!
//! Problems that don't fit into other categories.

/// LeetCode 7: Reverse Integer
///
/// Given a signed 32-bit integer x, return x with its digits reversed.
pub fn reverse(x: i32) -> i32 {
    let mut x = x as i64;
    let mut result: i64 = 0;
    
    while x != 0 {
        result = result * 10 + x % 10;
        x /= 10;
    }
    
    if result < i32::MIN as i64 || result > i32::MAX as i64 {
        0
    } else {
        result as i32
    }
}

/// LeetCode 9: Palindrome Number
///
/// Determine whether an integer is a palindrome.
pub fn is_palindrome(x: i32) -> bool {
    if x < 0 {
        return false;
    }
    
    let mut original = x;
    let mut reversed: i64 = 0;
    
    while original > 0 {
        reversed = reversed * 10 + (original % 10) as i64;
        original /= 10;
    }
    
    x as i64 == reversed
}

/// LeetCode 136: Single Number
///
/// Given a non-empty array of integers where every element appears twice
/// except for one, find that single one.
pub fn single_number(nums: Vec<i32>) -> i32 {
    nums.iter().fold(0, |acc, &x| acc ^ x)
}

/// LeetCode 169: Majority Element
///
/// Given an array of size n, find the majority element that appears more than n/2 times.
pub fn majority_element(nums: Vec<i32>) -> i32 {
    // Boyer-Moore Voting Algorithm
    let mut candidate = nums[0];
    let mut count = 0;
    
    for &num in &nums {
        if count == 0 {
            candidate = num;
        }
        count += if num == candidate { 1 } else { -1 };
    }
    
    candidate
}

/// LeetCode 287: Find the Duplicate Number
///
/// Given an array containing n+1 integers where each integer is between 1 and n,
/// prove that at least one duplicate number must exist and find it.
pub fn find_duplicate(nums: Vec<i32>) -> i32 {
    // Floyd's Tortoise and Hare
    let mut slow = nums[0];
    let mut fast = nums[0];
    
    // Find intersection point
    loop {
        slow = nums[slow as usize];
        fast = nums[nums[fast as usize] as usize];
        if slow == fast {
            break;
        }
    }
    
    // Find entrance to the cycle
    slow = nums[0];
    while slow != fast {
        slow = nums[slow as usize];
        fast = nums[fast as usize];
    }
    
    slow
}

/// LeetCode 200: Number of Islands
///
/// Given a 2D grid map of '1's (land) and '0's (water), count the number of islands.
pub fn num_islands(grid: Vec<Vec<char>>) -> i32 {
    if grid.is_empty() || grid[0].is_empty() {
        return 0;
    }
    
    let (m, n) = (grid.len(), grid[0].len());
    let mut grid = grid;
    let mut count = 0;
    
    fn dfs(grid: &mut Vec<Vec<char>>, i: usize, j: usize) {
        if i >= grid.len() || j >= grid[0].len() || grid[i][j] == '0' {
            return;
        }
        
        grid[i][j] = '0'; // Mark as visited
        
        // Check all 4 directions
        dfs(grid, i.saturating_sub(1), j);
        dfs(grid, i + 1, j);
        dfs(grid, i, j.saturating_sub(1));
        dfs(grid, i, j + 1);
    }
    
    for i in 0..m {
        for j in 0..n {
            if grid[i][j] == '1' {
                count += 1;
                dfs(&mut grid, i, j);
            }
        }
    }
    
    count
}

/// LeetCode 42: Trapping Rain Water
///
/// Given n non-negative integers representing an elevation map, compute how
/// much water it can trap after raining.
pub fn trap(height: Vec<i32>) -> i32 {
    if height.len() < 3 {
        return 0;
    }
    
    let mut left = 0;
    let mut right = height.len() - 1;
    let mut left_max = 0;
    let mut right_max = 0;
    let mut water = 0;
    
    while left < right {
        if height[left] < height[right] {
            if height[left] >= left_max {
                left_max = height[left];
            } else {
                water += left_max - height[left];
            }
            left += 1;
        } else {
            if height[right] >= right_max {
                right_max = height[right];
            } else {
                water += right_max - height[right];
            }
            right -= 1;
        }
    }
    
    water
}

/// LeetCode 20: Valid Parentheses
///
/// Given a string containing just the characters '(', ')', '{', '}', '[' and ']',
/// determine if the input string is valid.
pub fn is_valid(s: String) -> bool {
    let mut stack = vec![];
    
    for c in s.chars() {
        match c {
            '(' | '{' | '[' => stack.push(c),
            ')' => if stack.pop() != Some('(') { return false; },
            '}' => if stack.pop() != Some('{') { return false; },
            ']' => if stack.pop() != Some('[') { return false; },
            _ => {}
        }
    }
    
    stack.is_empty()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_reverse() {
        assert_eq!(reverse(123), 321);
        assert_eq!(reverse(-123), -321);
        assert_eq!(reverse(120), 21);
    }

    #[test]
    fn test_is_palindrome() {
        assert!(is_palindrome(121));
        assert!(!is_palindrome(-121));
        assert!(!is_palindrome(10));
    }

    #[test]
    fn test_single_number() {
        assert_eq!(single_number(vec![2, 2, 1]), 1);
        assert_eq!(single_number(vec![4, 1, 2, 1, 2]), 4);
    }

    #[test]
    fn test_majority_element() {
        assert_eq!(majority_element(vec![3, 2, 3]), 3);
        assert_eq!(majority_element(vec![2, 2, 1, 1, 1, 2, 2]), 2);
    }

    #[test]
    fn test_find_duplicate() {
        assert_eq!(find_duplicate(vec![1, 3, 4, 2, 2]), 2);
        assert_eq!(find_duplicate(vec![3, 1, 3, 4, 2]), 3);
    }

    #[test]
    fn test_num_islands() {
        let grid = vec![
            vec!['1', '1', '1', '1', '0'],
            vec!['1', '1', '0', '1', '0'],
            vec!['1', '1', '0', '0', '0'],
            vec!['0', '0', '0', '0', '0'],
        ];
        assert_eq!(num_islands(grid), 1);
    }

    #[test]
    fn test_trap() {
        assert_eq!(trap(vec![0, 1, 0, 2, 1, 0, 1, 3, 2, 1, 2, 1]), 6);
        assert_eq!(trap(vec![4, 2, 0, 3, 2, 5]), 9);
    }

    #[test]
    fn test_is_valid() {
        assert!(is_valid("()".to_string()));
        assert!(is_valid("()[]{}".to_string()));
        assert!(is_valid("{[]}".to_string()));
        assert!(!is_valid("(]".to_string()));
    }
}
