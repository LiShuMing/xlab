#include "../include/fwd.h"
class Solution {
public:
    ListNode* deleteNode(ListNode* head, int val) {
        if (!head) return nullptr;
        ListNode* dummy = new ListNode(0, head);
        ListNode* current = dummy;
        while (current && current->next) {
            if (current->next->val == val) {
                current->next = current->next->next;
            }
            current = current->next;
        }
        return dummy->next;
    }
};
int main() {
    Solution solution;
    ListNode* head =
            new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4, new ListNode(5)))));
    auto ans = solution.deleteNode(head, 3);
    printList(ans);
    return 0;
}