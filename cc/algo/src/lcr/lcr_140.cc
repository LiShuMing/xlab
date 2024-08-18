#include "../include/fwd.h"

class Solution {
public:
    ListNode* trainingPlan(ListNode* head, int cnt) {
        ListNode* prev = head;
        ListNode* next = head;
        int i = 0;
        while (i < cnt && next) {
            next = next->next;
            i++;
        }
        if (!next) {
            return head;
        }
        while (next->next) {
            prev = prev->next;
            next = next->next;
        }
        return prev->next;
    }
};

int main() {
    Solution solution;
    ListNode* head =
            new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4, new ListNode(5)))));
    ListNode* result = solution.trainingPlan(head, 2);
    while (result) {
        cout << result->val << " ";
        result = result->next;
    }
    cout << endl;
    return 0;
}