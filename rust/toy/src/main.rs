
mod sort;
mod libs;

fn main() {
    println!("Sort numbers ascending");
    let mut numbers = [4, 65, 2, -31, 0, 99, 2, 83, 782, 1];
    println!("Before: {:?}", numbers);
    sort::quick_sort::quick_sort(&mut numbers);
    println!("After:  {:?}\n", numbers);
}
