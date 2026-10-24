/// A singly-linked list node, as used by the LeetCode problem definitions.
#[derive(PartialEq, Eq, Debug)]
pub struct ListNode {
    /// Value stored in this node.
    pub val: i32,
    /// Rest of the list, if any.
    pub next: Option<Box<ListNode>>,
}

impl ListNode {
    /// Create a single node with no successor.
    #[inline]
    pub fn new(val: i32) -> Self {
        ListNode { next: None, val }
    }
}

/// Build a linked list from `vec`, preserving order. Used to write test inputs.
pub fn to_list(vec: Vec<i32>) -> Option<Box<ListNode>> {
    let mut current = None;
    for &v in vec.iter().rev() {
        let mut node = ListNode::new(v);
        node.next = current;
        current = Some(Box::new(node));
    }
    current
}

/// Build a linked list from a list of values, e.g. `linked!(1, 2, 3)`.
#[macro_export]
macro_rules! linked {
    ($($e:expr),*) => {to_list(vec![$($e.to_owned()), *])};
    ($($e:expr,)*) => {to_list(vec![$($e.to_owned()), *])};
}
