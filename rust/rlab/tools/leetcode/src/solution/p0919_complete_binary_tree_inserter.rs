/**
 * [919] Complete Binary Tree Inserter
 *
 * A complete binary tree is a binary tree in which every level, except possibly the last, is completely filled, and all nodes are as far left as possible.
 * Design an algorithm to insert a new node to a complete binary tree keeping it complete after the insertion.
 * Implement the CBTInserter class:
 *
 * 	CBTInserter(TreeNode root) Initializes the data structure with the root of the complete binary tree.
 * 	int insert(int v) Inserts a TreeNode into the tree with value Node.val == val so that the tree remains complete, and returns the value of the parent of the inserted TreeNode.
 * 	TreeNode get_root() Returns the root node of the tree.
 *
 *  
 * <strong class="example">Example 1:
 * <img alt="" src="https://assets.leetcode.com/uploads/2021/08/03/lc-treeinsert.jpg" style="width: 500px; height: 143px;" />
 * Input
 * ["CBTInserter", "insert", "insert", "get_root"]
 * [[[1, 2]], [3], [4], []]
 * Output
 * [null, 1, 2, [1, 2, 3, 4]]
 * Explanation
 * CBTInserter cBTInserter = new CBTInserter([1, 2]);
 * cBTInserter.insert(3);  // return 1
 * cBTInserter.insert(4);  // return 2
 * cBTInserter.get_root(); // return [1, 2, 3, 4]
 *
 *  
 * Constraints:
 *
 * 	The number of nodes in the tree will be in the range [1, 1000].
 * 	0 <= Node.val <= 5000
 * 	root is a complete binary tree.
 * 	0 <= val <= 5000
 * 	At most 10^4 calls will be made to insert and get_root.
 *
 */
use crate::util::tree::{to_tree, TreeNode};
use std::cell::RefCell;
use std::rc::Rc;

pub struct Solution {}

// problem: https://leetcode.com/problems/complete-binary-tree-inserter/
// discuss: https://leetcode.com/problems/complete-binary-tree-inserter/discuss/?currentPage=1&orderBy=most_votes&query=

// submission codes start here

// Definition for a binary tree node.
// #[derive(Debug, PartialEq, Eq)]
// pub struct TreeNode {
//   pub val: i32,
//   pub left: Option<Rc<RefCell<TreeNode>>>,
//   pub right: Option<Rc<RefCell<TreeNode>>>,
// }
//
// impl TreeNode {
//   #[inline]
//   pub fn new(val: i32) -> Self {
//     TreeNode {
//       val,
//       left: None,
//       right: None
//     }
//   }
// }
struct CBTInserter {
    // fields
    root: Option<Rc<RefCell<TreeNode>>>,
    deque: Vec<Rc<RefCell<TreeNode>>>,
}

/**
 * `&self` means the method takes an immutable reference.
 * If you need a mutable reference, change it to `&mut self` instead.
 */
impl CBTInserter {
    fn new(root: Option<Rc<RefCell<TreeNode>>>) -> Self {
        // initialize fields
        let mut deque = Vec::new();
        if let Some(r) = root.clone() {
            // level order traversal to populate deque
            let mut q = vec![r];
            while !q.is_empty() {
                let node = q.remove(0);
                let left = node.borrow().left.clone();
                let right = node.borrow().right.clone();
                if let Some(ref l) = left {
                    q.push(l.clone());
                }
                if let Some(ref r) = right {
                    q.push(r.clone());
                }
                if left.is_none() || right.is_none() {
                    deque.push(node);
                }
            }
        }
        Self { root, deque }
    }

    fn insert(&mut self, val: i32) -> i32 {
        // insert val into the tree
        let new_node = Rc::new(RefCell::new(TreeNode::new(val)));
        let parent = self.deque[0].clone();
        let ans = parent.borrow().val;
        if parent.borrow().left.is_none() {
            parent.borrow_mut().left = Some(new_node.clone());
        } else {
            parent.borrow_mut().right = Some(new_node.clone());
            self.deque.remove(0);
        }
        self.deque.push(new_node);
        ans
    }

    fn get_root(&self) -> Option<Rc<RefCell<TreeNode>>> {
        // return the root of the tree
        self.root.clone()
    }
}

/**
 * Your CBTInserter object will be instantiated and called as such:
 * let obj = CBTInserter::new(root);
 * let ret_1: i32 = obj.insert(val);
 * let ret_2: Option<Rc<RefCell<TreeNode>>> = obj.get_root();
 */

// submission codes end

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_919() {
        let root = to_tree(vec![Some(1), Some(2), Some(3), Some(4), Some(5), Some(6)]);
        let mut obj = CBTInserter::new(root);
        let ret_1 = obj.insert(7);
        assert_eq!(ret_1, 3);
        let ret_2 = obj.get_root();
        let expected = to_tree(vec![
            Some(1),
            Some(2),
            Some(3),
            Some(4),
            Some(5),
            Some(6),
            Some(7),
        ]);
        assert_eq!(ret_2, expected);
    }
}
