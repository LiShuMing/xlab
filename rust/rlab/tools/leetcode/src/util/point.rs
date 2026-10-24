/// A point on an integer 2-D grid.
#[derive(Debug, PartialEq, Eq)]
pub struct Point {
    /// Horizontal coordinate.
    pub x: i32,
    /// Vertical coordinate.
    pub y: i32,
}

impl Point {
    /// Create a point at `(x, y)`.
    #[inline]
    pub fn new(x: i32, y: i32) -> Self {
        Point { x, y }
    }
}

/// Build a `Point` literal, e.g. `point!(1, 2)`.
#[macro_export]
macro_rules! point {
    ($($e:expr),*) => {
        {
            let vec = vec![$($e.to_owned()), *];
            Point::new(vec[0], vec[1])
        }
    };
    ($($e:expr,)*) => (point![$($x),*])
}
