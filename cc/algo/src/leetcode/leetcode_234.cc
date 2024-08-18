#include "../include/fwd.h"

class Solution {
public:
    bool isPalindrome(ListNode* head) {
        ListNode* slow = head;
        ListNode* fast = head;
        while (fast != nullptr && fast->next != nullptr) {
            slow = slow->next;
            fast = fast->next->next;
        }
        ListNode* prev = nullptr;
        while (slow != nullptr) {
            ListNode* next = slow->next;
            slow->next = prev;
            prev = slow;
            slow = next;
        }
        while (head != nullptr && prev != nullptr) {
            if (head->val != prev->val) {
                return false;
            }
            head = head->next;
            prev = prev->next;
        }
        return true;
    }
};