#include "../include/fwd.h"
class Solution {
public:
    ListNode* rotateRight(ListNode* head, int k) {
        if (!head) return nullptr;
        ListNode* cur = head;
        int length = 0;
        while (cur) {
            length++;
            cur = cur->next;
        }
        k = k % length;
        for (int i = 0; i < k; i++) {
            head = rotateRightOne(head);
        }
        return head;
    }

    ListNode* rotateRightOne(ListNode* head) {
        ListNode* slow = head;
        ListNode* fast = head->next;
        while (fast && fast->next) {
            slow = slow->next;
            fast = fast->next;
        }
        fast->next = head;
        slow->next = nullptr;
        return fast;
    }
};