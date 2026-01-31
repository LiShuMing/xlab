//! Sorting and Searching Problems
//!
//! Problems that can be solved using sorting or binary search.

/// LeetCode 912: Sort an Array
///
/// Sort an array using your preferred algorithm.
pub fn sort_array(nums: Vec<i32>) -> Vec<i32> {
    let mut arr = nums;
    rlab::sort::quick_sort(&mut arr);
    arr
}

/// LeetCode 88: Merge Sorted Array
///
/// Merge two sorted arrays into one sorted array (in-place for nums1).
pub fn merge(nums1: &mut Vec<i32>, m: i32, nums2: &mut Vec<i32>, n: i32) {
    let (mut m, mut n) = (m as usize, n as usize);
    let mut k = m + n;
    
    while n > 0 {
        if m > 0 && nums1[m - 1] > nums2[n - 1] {
            nums1[k - 1] = nums1[m - 1];
            m -= 1;
        } else {
            nums1[k - 1] = nums2[n - 1];
            n -= 1;
        }
        k -= 1;
    }
}

/// LeetCode 704: Binary Search
///
/// Given a sorted array and target, return the index of target or -1.
pub fn search(nums: Vec<i32>, target: i32) -> i32 {
    let mut left = 0i32;
    let mut right = nums.len() as i32 - 1;
    
    while left <= right {
        let mid = left + (right - left) / 2;
        let mid_val = nums[mid as usize];
        
        if mid_val == target {
            return mid;
        } else if mid_val < target {
            left = mid + 1;
        } else {
            right = mid - 1;
        }
    }
    
    -1
}

/// LeetCode 74: Search a 2D Matrix
///
/// Search for a value in an m x n matrix with sorted rows and columns.
pub fn search_matrix(matrix: Vec<Vec<i32>>, target: i32) -> bool {
    if matrix.is_empty() || matrix[0].is_empty() {
        return false;
    }
    
    let (m, n) = (matrix.len(), matrix[0].len());
    let mut left = 0i32;
    let mut right = (m * n) as i32 - 1;
    
    while left <= right {
        let mid = left + (right - left) / 2;
        let mid_val = matrix[(mid / n as i32) as usize][(mid % n as i32) as usize];
        
        if mid_val == target {
            return true;
        } else if mid_val < target {
            left = mid + 1;
        } else {
            right = mid - 1;
        }
    }
    
    false
}

/// LeetCode 215: Kth Largest Element in an Array
///
/// Find the kth largest element in an unsorted array.
pub fn find_kth_largest(nums: Vec<i32>, k: i32) -> i32 {
    use std::collections::BinaryHeap;
    
    let mut heap = BinaryHeap::new();
    
    for num in nums {
        heap.push(num);
    }
    
    for _ in 0..k - 1 {
        heap.pop();
    }
    
    heap.pop().unwrap()
}

/// LeetCode 347: Top K Frequent Elements
///
/// Return the k most frequent elements.
pub fn top_k_frequent(nums: Vec<i32>, k: i32) -> Vec<i32> {
    use std::collections::HashMap;
    
    let mut freq = HashMap::new();
    for num in nums {
        *freq.entry(num).or_insert(0) += 1;
    }
    
    let mut pairs: Vec<(i32, i32)> = freq.into_iter().collect();
    pairs.sort_by(|a, b| b.1.cmp(&a.1));
    
    pairs.into_iter().take(k as usize).map(|(num, _)| num).collect()
}

/// LeetCode 33: Search in Rotated Sorted Array
///
/// Search for a target in a rotated sorted array.
pub fn search_rotated(nums: Vec<i32>, target: i32) -> i32 {
    if nums.is_empty() {
        return -1;
    }
    
    let mut left = 0i32;
    let mut right = nums.len() as i32 - 1;
    
    while left <= right {
        let mid = left + (right - left) / 2;
        let mid_val = nums[mid as usize];
        
        if mid_val == target {
            return mid;
        }
        
        // Check which half is sorted
        if nums[left as usize] <= mid_val {
            // Left half is sorted
            if target >= nums[left as usize] && target < mid_val {
                right = mid - 1;
            } else {
                left = mid + 1;
            }
        } else {
            // Right half is sorted
            if target > mid_val && target <= nums[right as usize] {
                left = mid + 1;
            } else {
                right = mid - 1;
            }
        }
    }
    
    -1
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sort_array() {
        assert_eq!(sort_array(vec![5, 2, 3, 1]), vec![1, 2, 3, 5]);
        assert_eq!(sort_array(vec![5, 1, 1, 2, 0, 0]), vec![0, 0, 1, 1, 2, 5]);
    }

    #[test]
    fn test_merge() {
        let mut nums1 = vec![1, 2, 3, 0, 0, 0];
        let mut nums2 = vec![2, 5, 6];
        merge(&mut nums1, 3, &mut nums2, 3);
        assert_eq!(nums1, vec![1, 2, 2, 3, 5, 6]);
    }

    #[test]
    fn test_search() {
        assert_eq!(search(vec![-1, 0, 3, 5, 9, 12], 9), 4);
        assert_eq!(search(vec![-1, 0, 3, 5, 9, 12], 2), -1);
    }

    #[test]
    fn test_search_matrix() {
        let matrix = vec![
            vec![1, 3, 5, 7],
            vec![10, 11, 16, 20],
            vec![23, 30, 34, 60],
        ];
        assert!(search_matrix(matrix.clone(), 3));
        assert!(!search_matrix(matrix, 13));
    }

    #[test]
    fn test_find_kth_largest() {
        assert_eq!(find_kth_largest(vec![3, 2, 1, 5, 6, 4], 2), 5);
        assert_eq!(find_kth_largest(vec![3, 2, 3, 1, 2, 4, 5, 5, 6], 4), 4);
    }

    #[test]
    fn test_top_k_frequent() {
        let mut result = top_k_frequent(vec![1, 1, 1, 2, 2, 3], 2);
        result.sort();
        assert_eq!(result, vec![1, 2]);
    }

    #[test]
    fn test_search_rotated() {
        assert_eq!(search_rotated(vec![4, 5, 6, 7, 0, 1, 2], 0), 4);
        assert_eq!(search_rotated(vec![4, 5, 6, 7, 0, 1, 2], 3), -1);
    }
}
