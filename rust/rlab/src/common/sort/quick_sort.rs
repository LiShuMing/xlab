use std::fmt::Debug;
use std::fmt::Display;

pub struct TestStruct {
    a: usize,
}

pub fn quick_sort<T: Ord + Display>(arr: &mut [T]) {
    let len = arr.len();
    println!("len:{:?}", len);
    _quick_sort(arr, 0, (len - 1) as isize)
}

fn _quick_sort<T: Ord + Display>(arr: &mut [T], low: isize, high: isize) {
    if low < high && low >= 0 && high >= 0 {
        let p = partition(arr, low, high);
        partition(arr, low, p - 1);
        partition(arr, p + 1, high);
    }
}

fn partition<T: Ord + Display>(arr: &mut [T], low: isize, high: isize) -> isize {
    let pivot = high;
    let mut l = low - 1;
    let mut r = high;
    println!("0, l:{:?}, r:{:?}", l, r);

    loop {
        // println!("l:{:?}, r:{:?}", l, r);
        // for val in arr.iter() {
        //     print!("{},", val)
        // }
        l += 1;
        while arr[l as usize] < arr[pivot as usize] {
            l += 1;
        }
        r -= 1;
        while 0 <= r && arr[r as usize] > arr[pivot as usize] {
            r -= 1;
        }
        if l >= r {
            break;
        }
        arr.swap(l as usize, r as usize);
    }
    arr.swap(l as usize, pivot as usize);
    return l;
}

#[cfg(test)]
pub mod tests {
    #[test]
    fn test_quick_sort_basic() {
        println!("Sort numbers ascending");
        let mut numbers = [4, 65, 2, -31, 0, 99, 2, 83, 782, 1];
        println!("Before: {:?}", numbers);
        crate::common::sort::quick_sort::quick_sort(&mut numbers);
        println!("After:  {:?}\n", numbers);
    }
}
