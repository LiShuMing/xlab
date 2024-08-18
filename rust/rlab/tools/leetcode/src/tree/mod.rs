//! Tree and Graph Problems
//!
//! Problems involving binary trees, BSTs, and graphs.

use std::cell::RefCell;
use std::rc::Rc;

/// Definition for a binary tree node
#[derive(Debug, PartialEq, Eq)]
pub struct TreeNode {
    pub val: i32,
    pub left: Option<Rc<RefCell<TreeNode>>>,
    pub right: Option<Rc<RefCell<TreeNode>>>,
}

impl TreeNode {
    /// Create a new tree node
    #[inline]
    pub fn new(val: i32) -> Self {
        TreeNode {
            val,
            left: None,
            right: None,
        }
    }
}

/// LeetCode 104: Maximum Depth of Binary Tree
///
/// Find the maximum depth of a binary tree.
pub fn max_depth(root: Option<Rc<RefCell<TreeNode>>>) -> i32 {
    match root {
        None => 0,
        Some(node) => {
            let node = node.borrow();
            let left_depth = max_depth(node.left.clone());
            let right_depth = max_depth(node.right.clone());
            1 + left_depth.max(right_depth)
        }
    }
}

/// LeetCode 226: Invert Binary Tree
///
/// Invert a binary tree (mirror).
pub fn invert_tree(root: Option<Rc<RefCell<TreeNode>>>) -> Option<Rc<RefCell<TreeNode>>> {
    if let Some(node) = root {
        let mut n = node.borrow_mut();
        let left = n.left.take();
        let right = n.right.take();
        n.left = invert_tree(right);
        n.right = invert_tree(left);
        drop(n);
        Some(node)
    } else {
        None
    }
}

/// LeetCode 98: Validate Binary Search Tree
///
/// Determine if a binary tree is a valid BST.
pub fn is_valid_bst(root: Option<Rc<RefCell<TreeNode>>>) -> bool {
    fn helper(
        node: Option<Rc<RefCell<TreeNode>>>,
        min: Option<i64>,
        max: Option<i64>,
    ) -> bool {
        match node {
            None => true,
            Some(n) => {
                let n = n.borrow();
                let val = n.val as i64;
                
                if let Some(min) = min {
                    if val <= min {
                        return false;
                    }
                }
                if let Some(max) = max {
                    if val >= max {
                        return false;
                    }
                }
                
                helper(n.left.clone(), min, Some(val)) && helper(n.right.clone(), Some(val), max)
            }
        }
    }
    
    helper(root, None, None)
}

/// LeetCode 102: Binary Tree Level Order Traversal
///
/// Return the level order traversal of a binary tree's nodes' values.
pub fn level_order(root: Option<Rc<RefCell<TreeNode>>>) -> Vec<Vec<i32>> {
    use std::collections::VecDeque;
    
    let mut result = vec![];
    if root.is_none() {
        return result;
    }
    
    let mut queue = VecDeque::new();
    queue.push_back(root.unwrap());
    
    while !queue.is_empty() {
        let level_size = queue.len();
        let mut current_level = vec![];
        
        for _ in 0..level_size {
            let node = queue.pop_front().unwrap();
            let n = node.borrow();
            current_level.push(n.val);
            
            if let Some(left) = n.left.clone() {
                queue.push_back(left);
            }
            if let Some(right) = n.right.clone() {
                queue.push_back(right);
            }
        }
        
        result.push(current_level);
    }
    
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_max_depth() {
        // Simple tree:    3
        //                / \
        //               9  20
        //                 /  \
        //                15   7
        let root = Some(Rc::new(RefCell::new(TreeNode {
            val: 3,
            left: Some(Rc::new(RefCell::new(TreeNode::new(9)))),
            right: Some(Rc::new(RefCell::new(TreeNode {
                val: 20,
                left: Some(Rc::new(RefCell::new(TreeNode::new(15)))),
                right: Some(Rc::new(RefCell::new(TreeNode::new(7)))),
            }))),
        })));
        
        assert_eq!(max_depth(root), 3);
    }

    #[test]
    fn test_level_order() {
        // Tree:     3
        //          / \
        //         9  20
        //           /  \
        //          15   7
        let root = Some(Rc::new(RefCell::new(TreeNode {
            val: 3,
            left: Some(Rc::new(RefCell::new(TreeNode::new(9)))),
            right: Some(Rc::new(RefCell::new(TreeNode {
                val: 20,
                left: Some(Rc::new(RefCell::new(TreeNode::new(15)))),
                right: Some(Rc::new(RefCell::new(TreeNode::new(7)))),
            }))),
        })));
        
        assert_eq!(level_order(root), vec![vec![3], vec![9, 20], vec![15, 7]]);
    }
}
