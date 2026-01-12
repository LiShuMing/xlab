#include "../include/fwd.h"

/**
 * LeetCode 82: Remove Duplicates from Sorted List II
 * 
 * Given the head of a sorted linked list, delete all nodes that have
 * duplicate numbers, leaving only distinct numbers.
 * 
 * Approach: Two-pointer (slow/fast) with dummy node
 * - slow: tracks the last confirmed unique node
 * - fast: scans ahead to find duplicates
 */
class Solution {
public:
    ListNode* deleteDuplicates(ListNode* head) {
        auto* dummy = new ListNode(0, head);
        ListNode* slow = dummy;
        ListNode* fast = head;
        
        while (fast) {
            // Skip all duplicates of the current value
            while (fast->next && fast->val == fast->next->val) {
                fast = fast->next;
            }
            
            // If slow->next != fast, it means there were duplicates
            // Skip them by linking slow to fast->next
            if (slow->next != fast) {
                slow->next = fast->next;
            } else {
                // No duplicates, move slow forward
                slow = slow->next;
            }
            
            // Move fast to the next distinct value
            fast = fast->next;
        }
        
        return dummy->next;
    }
};

int main() {
    Solution solution;
    // Test case: 1 -> 2 -> 3 -> 3 -> 4 -> 4 -> 5
    // Expected: 1 -> 2 -> 5
    auto* head = new ListNode(1, 
        new ListNode(2, 
            new ListNode(3, 
                new ListNode(3, 
                    new ListNode(4, 
                        new ListNode(4, 
                            new ListNode(5)))))));
    ListNode* result = solution.deleteDuplicates(head);
    
    cout << "Result: ";
    while (result) {
        cout << result->val << " ";
        result = result->next;
    }
    cout << endl;
    
    return 0;
}
