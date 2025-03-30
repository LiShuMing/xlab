// use jemallocator::jemalloc_sys;
// use jemallocator::jemalloc_sys::MALLOCX_ALIGN;
// use jemallocator::Jemalloc;
// use std::alloc::Layout;
// use libc::c_int;
use std::thread;
// use threadpool::ThreadPool;
// use std::sync::mpsc::channel;

// fn layout_to_flags(layout: &Layout) -> c_int {
//     if layout.align() <= MIN_ALIGN && layout.align() <= layout.size() {
//         0
//     } else {
//         MALLOCX_ALIGN(layout.align())
//     }
// }

#[test]
fn testDemo1() {
    // use jemalloc_sys as jemalloc;
    // let flags = layout_to_flags(&Layout::from_size_align(10, 8).unwrap());
    // let ptr = Jemalloc::Alloc(10, Jemalloc::MALLOCX_ZERO);
    // Jemalloc::sdallocx(ptr, 10, 16);

    let v = vec![1];
    let handle = thread::spawn(move || {
        print!("aaa\n");
    });
    let ret = handle.join();

    // loop {
    //     // do nothing.
    // }
    println!("Hello, world!");
}
