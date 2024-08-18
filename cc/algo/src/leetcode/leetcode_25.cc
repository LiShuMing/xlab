#include "../include/fwd.h"

class Solution {
public:
    ListNode* reverseKGroup(ListNode* head, int k) {
        if (!head) return nullptr;
        ListNode* dummy = new ListNode(0, head);
        ListNode* prev = dummy;
        ListNode* curr = head;
        int l = 0;
        while (curr) {
            l++;
            curr = curr->next;
        }
        curr = head;
        for (int i = 0; i < l / k; i++) {
            ListNode* next = curr->next;
            for (int j = 0; j < k - 1; j++) {
                curr->next = next->next;
                next->next = prev->next;
                prev->next = next;
                next = curr->next;
            }
            prev = curr;
            curr = next;
        }
        return dummy->next;
    }
};

int main() {
    Solution solution;
    return 0;
}