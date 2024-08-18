//! Linear-time integer sorting algorithms
//!
//! These algorithms work specifically with integers and can achieve
//! O(n + k) or O(n) time complexity where k is the range of input.

/// Counting Sort
///
/// Non-comparison-based sort that works by counting the number of objects
/// having distinct key values, then calculating the positions of each key.
///
/// # Requirements
///
/// - Elements must be convertible to non-negative integers
/// - Range of values should be reasonably small
///
/// # Performance
///
/// - Time: O(n + k) where k is the range of input
/// - Space: O(n + k)
/// - Stable: Yes
///
/// # Examples
///
/// ```
/// use rlab::common::sort::counting_sort;
///
/// let mut arr = [4, 2, 2, 8, 3, 3, 1];
/// counting_sort(&mut arr, 8); // max value is 8
/// assert_eq!(arr, [1, 2, 2, 3, 3, 4, 8]);
/// ```
pub fn counting_sort(arr: &mut [i32], max_val: i32) {
    if arr.len() <= 1 || max_val <= 0 {
        return;
    }

    // Count occurrences of each value
    let mut count = vec![0; (max_val + 1) as usize];

    for &val in arr.iter() {
        debug_assert!(val >= 0 && val <= max_val, "Value {} out of range [0, {}]", val, max_val);
        count[val as usize] += 1;
    }

    // Calculate cumulative counts
    for i in 1..count.len() {
        count[i] += count[i - 1];
    }

    // Build output array (stable)
    let mut output = vec![0; arr.len()];
    for &val in arr.iter().rev() {
        count[val as usize] -= 1;
        output[count[val as usize]] = val;
    }

    // Copy back to original array
    arr.copy_from_slice(&output);
}

/// Counting Sort (generic version)
///
/// Generic version that works with any type implementing the required traits.
/// The key_fn extracts an integer key from each element.
///
/// # Examples
///
/// ```
/// use rlab::common::sort::counting_sort_by_key;
///
/// #[derive(Debug, Clone, PartialEq)]
/// struct Person { age: i32, name: &'static str }
///
/// let mut people = [
///     Person { age: 30, name: "Alice" },
///     Person { age: 25, name: "Bob" },
///     Person { age: 30, name: "Charlie" },
/// ];
///
/// counting_sort_by_key(&mut people, 30, |p| p.age);
///
/// assert_eq!(people[0].age, 25);
/// assert_eq!(people[1].age, 30);
/// assert_eq!(people[2].age, 30);
/// ```
pub fn counting_sort_by_key<T: Clone>(
    arr: &mut [T],
    max_key: i32,
    key_fn: impl Fn(&T) -> i32,
) {
    if arr.len() <= 1 || max_key <= 0 {
        return;
    }

    // Count occurrences
    let mut count = vec![0; (max_key + 1) as usize];
    for item in arr.iter() {
        let key = key_fn(item);
        count[key as usize] += 1;
    }

    // Cumulative counts
    for i in 1..count.len() {
        count[i] += count[i - 1];
    }

    // Build output (stable)
    let mut output = arr.to_vec();
    for item in arr.iter().rev() {
        let key = key_fn(item);
        count[key as usize] -= 1;
        output[count[key as usize]] = item.clone();
    }

    arr.clone_from_slice(&output);
}

/// Radix Sort (LSD - Least Significant Digit)
///
/// Non-comparison sort that processes digits from least significant to most.
/// Uses counting sort as a subroutine for each digit.
///
/// # Performance
///
/// - Time: O(d * (n + b)) where d is digits, b is base
/// - Space: O(n + b)
/// - Stable: Yes
///
/// # Examples
///
/// ```
/// use rlab::common::sort::radix_sort_lsd;
///
/// let mut arr = [170, 45, 75, 90, 2, 802, 24, 66];
/// radix_sort_lsd(&mut arr);
/// assert_eq!(arr, [2, 24, 45, 66, 75, 90, 170, 802]);
/// ```
pub fn radix_sort_lsd(arr: &mut [i32]) {
    if arr.len() <= 1 {
        return;
    }

    // Handle negative numbers by finding minimum
    let min_val = *arr.iter().min().unwrap_or(&0);
    let max_val = *arr.iter().max().unwrap_or(&0);

    // Shift to make all values non-negative
    if min_val < 0 {
        for val in arr.iter_mut() {
            *val -= min_val;
        }
    }

    let max_val = max_val - min_val;

    // Do counting sort for every digit (base 256 for efficiency)
    const BASE: i32 = 256;
    let mut exp = 1;

    while max_val / exp > 0 {
        counting_sort_by_digit(arr, exp, BASE);
        exp *= BASE;
    }

    // Shift back
    if min_val < 0 {
        for val in arr.iter_mut() {
            *val += min_val;
        }
    }
}

/// Counting sort for a specific digit
fn counting_sort_by_digit(arr: &mut [i32], exp: i32, base: i32) {
    let n = arr.len();
    let mut output = vec![0; n];
    let mut count = vec![0; base as usize];

    // Count occurrences of each digit
    for &val in arr.iter() {
        let digit = ((val / exp) % base) as usize;
        count[digit] += 1;
    }

    // Cumulative count
    for i in 1..count.len() {
        count[i] += count[i - 1];
    }

    // Build output (stable - iterate from end)
    for &val in arr.iter().rev() {
        let digit = ((val / exp) % base) as usize;
        count[digit] -= 1;
        output[count[digit]] = val;
    }

    arr.copy_from_slice(&output);
}

/// Radix Sort (MSD - Most Significant Digit)
///
/// Recursive radix sort that processes digits from most significant to least.
/// Often more cache-friendly than LSD for large datasets.
pub fn radix_sort_msd(arr: &mut [i32]) {
    if arr.len() <= 1 {
        return;
    }

    // Handle negative numbers by shifting to positive range using i64
    let min_val = *arr.iter().min().unwrap_or(&0) as i64;
    let max_val = *arr.iter().max().unwrap_or(&0) as i64;
    
    // Shift to make all values non-negative
    let offset = if min_val < 0 { -min_val } else { 0 };
    let shifted_max = max_val + offset;

    // Create working array with shifted i64 values
    let mut work: Vec<i64> = arr.iter().map(|&v| v as i64 + offset).collect();

    // Find the most significant digit position
    let mut max_digit = 1i64;
    while shifted_max / max_digit > 0 {
        max_digit *= 256;
    }
    max_digit /= 256;

    if max_digit > 0 {
        radix_sort_msd_helper(&mut work, max_digit);
    }

    // Copy back with offset removed
    for (i, &val) in work.iter().enumerate() {
        arr[i] = (val - offset) as i32;
    }
}

fn radix_sort_msd_helper(arr: &mut [i64], digit: i64) {
    if arr.len() <= 1 || digit == 0 {
        return;
    }

    // Count sort by current digit
    const BASE: usize = 256;
    let mut count = [0usize; BASE];

    for &val in arr.iter() {
        let d = ((val / digit) % 256) as usize;
        count[d] += 1;
    }

    // Compute end positions (prefix sum)
    let mut end = [0usize; BASE];
    let mut cumsum = 0;
    for i in 0..BASE {
        cumsum += count[i];
        end[i] = cumsum;
    }

    // Stable partition - iterate in reverse and place elements
    let mut temp = arr.to_vec();
    for &val in arr.iter().rev() {
        let d = ((val / digit) % 256) as usize;
        end[d] -= 1;
        temp[end[d]] = val;
    }

    arr.copy_from_slice(&temp);

    // Recursively sort each bucket
    let next_digit = digit / 256;
    if next_digit > 0 {
        let mut start = 0;
        for i in 0..BASE {
            let bucket_end = start + count[i];
            if bucket_end > start {
                radix_sort_msd_helper(&mut arr[start..bucket_end], next_digit);
            }
            start = bucket_end;
        }
    }
}

/// Bucket Sort
///
/// Distributes elements into a number of buckets, then sorts each bucket
/// individually (typically with insertion sort).
///
/// Best when input is uniformly distributed over a range.
///
/// # Performance
///
/// - Average: O(n + k) where k is number of buckets
/// - Worst: O(n²) when all elements go into one bucket
/// - Space: O(n + k)
pub fn bucket_sort(arr: &mut [i32]) {
    if arr.len() <= 1 {
        return;
    }

    let n = arr.len();
    let min_val = *arr.iter().min().unwrap_or(&0);
    let max_val = *arr.iter().max().unwrap_or(&0);

    if min_val == max_val {
        return;
    }

    // Create buckets
    let num_buckets = n.max(2);
    let range = (max_val - min_val + 1) as f64;
    let mut buckets: Vec<Vec<i32>> = vec![Vec::new(); num_buckets];

    // Distribute elements into buckets
    for &val in arr.iter() {
        let idx = (((val - min_val) as f64 / range) * (num_buckets - 1) as f64) as usize;
        buckets[idx].push(val);
    }

    // Sort each bucket and concatenate
    let mut idx = 0;
    for bucket in buckets.iter_mut() {
        // Use insertion sort for small buckets
        insertion_sort(bucket);
        for &val in bucket.iter() {
            arr[idx] = val;
            idx += 1;
        }
    }
}

fn insertion_sort(arr: &mut [i32]) {
    for i in 1..arr.len() {
        let mut j = i;
        while j > 0 && arr[j - 1] > arr[j] {
            arr.swap(j - 1, j);
            j -= 1;
        }
    }
}

/// Flash Sort
///
/// Distribution-based sort that classifies elements into m classes
/// based on their value. Very efficient when data is uniformly distributed.
///
/// # Performance
///
/// - Average: O(n) for uniform distribution
/// - Worst: O(n²)
/// - Space: O(m) where m is number of classes (typically 0.1n to 0.5n)
pub fn flash_sort(arr: &mut [i32]) {
    let n = arr.len();
    if n <= 1 {
        return;
    }

    // Number of classes
    let m = (0.1 * n as f64).max(2.0) as usize;

    // Find min and max
    let (mut min_val, mut max_val) = (arr[0], arr[0]);
    for &val in arr.iter() {
        if val < min_val {
            min_val = val;
        }
        if val > max_val {
            max_val = val;
        }
    }

    if min_val == max_val {
        return;
    }

    // Classify elements
    let mut count = vec![0; m];
    let c = (m - 1) as f64 / (max_val - min_val) as f64;

    for &val in arr.iter() {
        let k = (c * (val - min_val) as f64) as usize;
        count[k.min(m - 1)] += 1;
    }

    // Prefix sum for bucket boundaries
    for i in 1..m {
        count[i] += count[i - 1];
    }

    // Permutation
    let mut move_pos = 0;
    let mut j = 0;

    while move_pos < n {
        // Find the class of arr[j]
        let mut k = ((c * (arr[j] - min_val) as f64) as usize).min(m - 1);
        
        // Skip elements already in correct position
        while j >= count[k] {
            j += 1;
            if j >= n {
                break;
            }
            k = ((c * (arr[j] - min_val) as f64) as usize).min(m - 1);
        }
        
        if j >= n {
            break;
        }

        let mut flash = arr[j];
        while j < count[k] {
            k = ((c * (flash - min_val) as f64) as usize).min(m - 1);
            if count[k] == 0 || count[k] > n {
                break;
            }
            count[k] -= 1;
            std::mem::swap(&mut flash, &mut arr[count[k]]);
            move_pos += 1;
        }
    }

    // Final insertion sort pass
    insertion_sort(arr);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_counting_sort() {
        let mut arr = [4, 2, 2, 8, 3, 3, 1];
        counting_sort(&mut arr, 8);
        assert_eq!(arr, [1, 2, 2, 3, 3, 4, 8]);
    }

    #[test]
    fn test_counting_sort_by_key() {
        #[derive(Debug, Clone, PartialEq)]
        struct Person {
            age: i32,
            name: &'static str,
        }

        let mut people = [
            Person { age: 30, name: "Alice" },
            Person { age: 25, name: "Bob" },
            Person { age: 30, name: "Charlie" },
        ];

        counting_sort_by_key(&mut people, 30, |p| p.age);

        assert_eq!(people[0].age, 25);
        assert_eq!(people[1].age, 30);
        assert_eq!(people[1].name, "Alice"); // Stable sort preserves order
        assert_eq!(people[2].name, "Charlie");
    }

    #[test]
    fn test_radix_sort_lsd() {
        let mut arr = [170, 45, 75, 90, 2, 802, 24, 66];
        radix_sort_lsd(&mut arr);
        assert_eq!(arr, [2, 24, 45, 66, 75, 90, 170, 802]);
    }

    #[test]
    fn test_radix_sort_lsd_with_negatives() {
        let mut arr = [170, -45, 75, -90, 2, -802, 24, -66];
        radix_sort_lsd(&mut arr);
        assert_eq!(arr, [-802, -90, -66, -45, 2, 24, 75, 170]);
    }

    #[test]
    fn test_radix_sort_msd() {
        let mut arr = [170, 45, 75, 90, 2, 802, 24, 66];
        radix_sort_msd(&mut arr);
        assert_eq!(arr, [2, 24, 45, 66, 75, 90, 170, 802]);
    }

    #[test]
    fn test_radix_sort_msd_with_negatives() {
        let mut arr = [170, -45, 75, -90, 2, -802, 24, -66];
        radix_sort_msd(&mut arr);
        assert_eq!(arr, [-802, -90, -66, -45, 2, 24, 75, 170]);
    }

    #[test]
    fn test_bucket_sort() {
        let mut arr = [42, 32, 33, 52, 37, 47, 51];
        bucket_sort(&mut arr);
        assert_eq!(arr, [32, 33, 37, 42, 47, 51, 52]);
    }

    #[test]
    fn test_flash_sort() {
        let mut arr = [42, 32, 33, 52, 37, 47, 51];
        flash_sort(&mut arr);
        assert_eq!(arr, [32, 33, 37, 42, 47, 51, 52]);
    }

    #[test]
    fn test_integer_sorts_with_large_array() {
        let mut arr: Vec<i32> = (0..1000).rev().collect();
        radix_sort_lsd(&mut arr);
        assert!(arr.windows(2).all(|w| w[0] <= w[1]));

        let mut arr: Vec<i32> = (0..1000).rev().collect();
        radix_sort_msd(&mut arr);
        assert!(arr.windows(2).all(|w| w[0] <= w[1]));
    }
}
