//! Dynamic Programming Problems
//!
//! Classic dynamic programming problems and patterns.

/// LeetCode 70: Climbing Stairs
///
/// You are climbing a staircase with n steps. Each time you can climb 1 or 2 steps.
/// Return the number of distinct ways to climb to the top.
///
/// # Example
///
/// ```
/// use leetcode::dp::climb_stairs;
///
/// assert_eq!(climb_stairs(2), 2);
/// assert_eq!(climb_stairs(3), 3);
/// assert_eq!(climb_stairs(4), 5);
/// ```
pub fn climb_stairs(n: i32) -> i32 {
    if n <= 2 {
        return n;
    }
    
    let mut prev2 = 1; // dp[i-2]
    let mut prev1 = 2; // dp[i-1]
    
    for _ in 3..=n {
        let current = prev1 + prev2;
        prev2 = prev1;
        prev1 = current;
    }
    
    prev1
}

/// LeetCode 198: House Robber
///
/// Given an array representing money in each house, return the maximum amount
/// that can be robbed without robbing adjacent houses.
pub fn rob(nums: Vec<i32>) -> i32 {
    if nums.is_empty() {
        return 0;
    }
    if nums.len() == 1 {
        return nums[0];
    }
    
    let mut prev2 = 0; // dp[i-2]
    let mut prev1 = 0; // dp[i-1]
    
    for &num in &nums {
        let current = prev1.max(prev2 + num);
        prev2 = prev1;
        prev1 = current;
    }
    
    prev1
}

/// LeetCode 1143: Longest Common Subsequence
///
/// Given two strings, return the length of their longest common subsequence.
pub fn longest_common_subsequence(text1: String, text2: String) -> i32 {
    let s1: Vec<char> = text1.chars().collect();
    let s2: Vec<char> = text2.chars().collect();
    let (m, n) = (s1.len(), s2.len());
    
    // Space-optimized: only need previous row
    let mut prev = vec![0; n + 1];
    let mut curr = vec![0; n + 1];
    
    for i in 1..=m {
        for j in 1..=n {
            if s1[i - 1] == s2[j - 1] {
                curr[j] = prev[j - 1] + 1;
            } else {
                curr[j] = curr[j - 1].max(prev[j]);
            }
        }
        std::mem::swap(&mut prev, &mut curr);
    }
    
    prev[n]
}

/// LeetCode 300: Longest Increasing Subsequence
///
/// Return the length of the longest strictly increasing subsequence.
pub fn length_of_lis(nums: Vec<i32>) -> i32 {
    if nums.is_empty() {
        return 0;
    }
    
    // dp[i] = smallest tail of all increasing subsequences of length i+1
    let mut tails = vec![nums[0]];
    
    for &num in &nums[1..] {
        if num > *tails.last().unwrap() {
            tails.push(num);
        } else {
            // Binary search for the first element >= num
            let idx = tails.binary_search(&num).unwrap_or_else(|x| x);
            tails[idx] = num;
        }
    }
    
    tails.len() as i32
}

/// LeetCode 322: Coin Change
///
/// Return the fewest number of coins needed to make up the amount.
pub fn coin_change(coins: Vec<i32>, amount: i32) -> i32 {
    let amount = amount as usize;
    let mut dp = vec![amount as i32 + 1; amount + 1];
    dp[0] = 0;
    
    for i in 1..=amount {
        for &coin in &coins {
            if coin as usize <= i {
                dp[i] = dp[i].min(dp[i - coin as usize] + 1);
            }
        }
    }
    
    if dp[amount] > amount as i32 {
        -1
    } else {
        dp[amount]
    }
}

/// LeetCode 62: Unique Paths
///
/// Count unique paths from top-left to bottom-right in a m x n grid
/// (can only move right or down).
pub fn unique_paths(m: i32, n: i32) -> i32 {
    let (m, n) = (m as usize, n as usize);
    let mut dp = vec![1; n]; // First row is all 1s
    
    for _ in 1..m {
        for j in 1..n {
            dp[j] += dp[j - 1];
        }
    }
    
    dp[n - 1]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_climb_stairs() {
        assert_eq!(climb_stairs(2), 2);
        assert_eq!(climb_stairs(3), 3);
        assert_eq!(climb_stairs(4), 5);
        assert_eq!(climb_stairs(5), 8);
    }

    #[test]
    fn test_rob() {
        assert_eq!(rob(vec![1, 2, 3, 1]), 4);
        assert_eq!(rob(vec![2, 7, 9, 3, 1]), 12);
    }

    #[test]
    fn test_longest_common_subsequence() {
        assert_eq!(longest_common_subsequence("abcde".to_string(), "ace".to_string()), 3);
        assert_eq!(longest_common_subsequence("abc".to_string(), "abc".to_string()), 3);
        assert_eq!(longest_common_subsequence("abc".to_string(), "def".to_string()), 0);
    }

    #[test]
    fn test_length_of_lis() {
        assert_eq!(length_of_lis(vec![10, 9, 2, 5, 3, 7, 101, 18]), 4);
        assert_eq!(length_of_lis(vec![0, 1, 0, 3, 2, 3]), 4);
    }

    #[test]
    fn test_coin_change() {
        assert_eq!(coin_change(vec![1, 2, 5], 11), 3); // 5 + 5 + 1
        assert_eq!(coin_change(vec![2], 3), -1);
        assert_eq!(coin_change(vec![1], 0), 0);
    }

    #[test]
    fn test_unique_paths() {
        assert_eq!(unique_paths(3, 7), 28);
        assert_eq!(unique_paths(3, 2), 3);
    }
}
