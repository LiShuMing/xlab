use rlab::add;

#[test]
fn it_adds_two() {
    let result = add(2, 2);
    assert_eq!(result, 4);
}

#[test]
fn test_ownership() {
    let mut s = String::from("hello");
    let s2 = s.clone(); // Clone the string so we can use both

    {
        s.push_str(" world"); // This will fail because s is borrowed as immutable
        assert_eq!(s, "hello world");
        assert_eq!(s2, "hello");
    }

    {
        let s3 = &mut s;
        s3.push_str(" world, jojo");

        // s3 is borrowed as mutable, so we can't borrow s again
        //assert_eq!(s, "hello world world, jojo");
        // let s4 = &mut s;
        // s4.push_str(" world, jojo");

        assert_eq!(s2, "hello");
        assert_eq!(s3, "hello world world, jojo");

        // s3 is out of scope, so we can borrow s again
        //s.push_str(" world, jojo");
    }
}

#[test]
fn test_string() {
    let mut s = String::from("hello");
    let s2 = &mut s;
    println!("{}", s2);

    let s3 = String::from("hello");
    let s4 = s3.clone();
    println!("{}", s3);
    println!("{}", s4);
}

fn compute(a: &u32, output: &mut u32) {
    if (*a > 10) {
        *output = *a + 1;
    } else {
        *output = *a - 1;
    }
}

fn nothing<'a, 'b>(x: &'a i32, y: &'b i32) {
    'a: {
        let x: i32 = 1;
        'b: {
            let z: &'b i32;
            // let y: &'b i32 = &'b x;
            println!("{}", y);
        }
    }
    {
        let mut data = vec![1, 2, 3];
        let x = data[0]; // Clone the value instead of borrowing
        data.push(4);
        println!("{:?}", x);
    }
}

#[test]
fn test_compute() {
    let a = 11;
    let mut output = 0;
    compute(&a, &mut output);
    assert_eq!(output, 12);
}

#[derive(Debug)]
struct X<'a>(&'a i32);

#[derive(Debug)]
struct Y<'a>(&'a i32);

impl Drop for X<'_> {
    fn drop(&mut self) {
        println!("Dropping X");
    }
}

impl Drop for Y<'_> {
    fn drop(&mut self) {
        println!("Dropping Y");
    }
}

#[test]
fn test_x() {
    {
        let x = X(&1);
        let y = Y(&1);
    }

    let mut data = vec![1, 2, 3];
    {
        let x = X(&data[0]);
        let y = Y(&data[1]);
        println!("{:?}", x);
        println!("{:?}", y);
    }
    data.push(4);
    println!("{:?}", data);
}

#[derive(Debug)]
struct Foo;

impl Foo {
    fn mut_and_share<'a>(&'a mut self) -> &'a mut Self {
        &mut *self
    }
    fn share<'a>(&'a self) -> &'a Self {
        self
    }
}

#[test]
fn test_foo() {
    let mut foo = Foo;
    let mut_foo = foo.mut_and_share();
    println!("{:?}", mut_foo);
    foo.share();
}
