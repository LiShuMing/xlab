#include "../include/fwd.h"
class Solution {
public:
    ListNode* partition(ListNode* head, int x) {
        if (!head) return nullptr;
        ListNode* less_dummy = new ListNode(0);
        ListNode* greater_dummy = new ListNode(0);
        ListNode* less = less_dummy;
        ListNode* greater = greater_dummy;
        ListNode* cur = head;
        while (cur) {
            if (cur->val < x) {
                less->next = cur;
                less = less->next;
            } else {
                greater->next = cur;
                greater = greater->next;
            }
            cur = cur->next;
        }
        less->next = greater_dummy->next;
        greater->next = nullptr;
        return less_dummy->next;
    }
};

int main() {
    Solution solution;
    ListNode* head = new ListNode(
            1, new ListNode(4, new ListNode(3, new ListNode(2, new ListNode(5, new ListNode(2))))));
    ListNode* result = solution.partition(head, 3);
    while (result) {
        cout << result->val << " ";
        result = result->next;
    }
}