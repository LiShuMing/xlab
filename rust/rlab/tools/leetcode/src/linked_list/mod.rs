//! Linked List Problems
//!
//! Problems involving singly and doubly linked lists.

/// Definition for singly-linked list node
#[derive(PartialEq, Eq, Clone, Debug)]
pub struct ListNode {
    pub val: i32,
    pub next: Option<Box<ListNode>>,
}

impl ListNode {
    /// Create a new node
    #[inline]
    pub fn new(val: i32) -> Self {
        ListNode { val, next: None }
    }

    /// Create a linked list from a vector (helper for testing)
    pub fn from_vec(vals: Vec<i32>) -> Option<Box<ListNode>> {
        let mut dummy = Box::new(ListNode::new(0));
        let mut curr = &mut dummy;
        
        for val in vals {
            curr.next = Some(Box::new(ListNode::new(val)));
            curr = curr.next.as_mut().unwrap();
        }
        
        dummy.next
    }

    /// Convert linked list to vector (helper for testing)
    pub fn to_vec(head: Option<Box<ListNode>>) -> Vec<i32> {
        let mut result = vec![];
        let mut curr = head;
        
        while let Some(node) = curr {
            result.push(node.val);
            curr = node.next;
        }
        
        result
    }
}

/// LeetCode 206: Reverse Linked List
///
/// Reverse a singly linked list.
pub fn reverse_list(head: Option<Box<ListNode>>) -> Option<Box<ListNode>> {
    let mut prev = None;
    let mut curr = head;
    
    while let Some(mut node) = curr {
        curr = node.next.take();
        node.next = prev;
        prev = Some(node);
    }
    
    prev
}

/// LeetCode 21: Merge Two Sorted Lists
///
/// Merge two sorted linked lists into one sorted list.
pub fn merge_two_lists(
    list1: Option<Box<ListNode>>,
    list2: Option<Box<ListNode>>,
) -> Option<Box<ListNode>> {
    match (list1, list2) {
        (None, None) => None,
        (Some(l), None) => Some(l),
        (None, Some(r)) => Some(r),
        (Some(mut l), Some(mut r)) => {
            if l.val <= r.val {
                l.next = merge_two_lists(l.next, Some(r));
                Some(l)
            } else {
                r.next = merge_two_lists(Some(l), r.next);
                Some(r)
            }
        }
    }
}

/// LeetCode 141: Linked List Cycle
///
/// Determine if a linked list has a cycle using Floyd's algorithm.
pub fn has_cycle(head: Option<Box<ListNode>>) -> bool {
    let mut slow = &head;
    let mut fast = &head;
    
    while let (Some(s), Some(f)) = (slow, fast) {
        fast = &f.next;
        if let Some(f) = fast {
            fast = &f.next;
        } else {
            return false;
        }
        slow = &s.next;
        
        if std::ptr::eq(slow.as_ref().unwrap().as_ref(), fast.as_ref().unwrap().as_ref()) {
            return true;
        }
    }
    
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_reverse_list() {
        let head = ListNode::from_vec(vec![1, 2, 3, 4, 5]);
        let reversed = reverse_list(head);
        assert_eq!(ListNode::to_vec(reversed), vec![5, 4, 3, 2, 1]);
    }

    #[test]
    fn test_merge_two_lists() {
        let l1 = ListNode::from_vec(vec![1, 2, 4]);
        let l2 = ListNode::from_vec(vec![1, 3, 4]);
        let merged = merge_two_lists(l1, l2);
        assert_eq!(ListNode::to_vec(merged), vec![1, 1, 2, 3, 4, 4]);
    }
}
