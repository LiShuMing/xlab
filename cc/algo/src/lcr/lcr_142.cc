#include "../include/fwd.h"
/**
 * Definition for singly-linked list.
 * struct ListNode {
 *     int val;
 *     ListNode *next;
 *     ListNode() : val(0), next(nullptr) {}
 *     ListNode(int x) : val(x), next(nullptr) {}
 *     ListNode(int x, ListNode *next) : val(x), next(next) {}
 * };
 */
 class Solution {
    public:
        ListNode* trainningPlan(ListNode* l1, ListNode* l2) {
            ListNode* dummy = new ListNode(0);
            ListNode* current = dummy;
            while (l1 && l2) {
                if (l1->val < l2->val) {
                    current->next = l1;
                    l1 = l1->next;
                } else {
                    current->next = l2;
                    l2 = l2->next;
                }
                current = current->next;
            }
            current->next = l1 ? l1 : l2;
            return dummy->next;
        }
};

int main() {
    Solution solution;
    ListNode* l1 = new ListNode(1, new ListNode(2, new ListNode(4)));
    ListNode* l2 = new ListNode(1, new ListNode(3, new ListNode(4)));
    ListNode* result = solution.trainningPlan(l1, l2);
    while (result) {
        cout << result->val << " ";
        result = result->next;
    }
    cout << endl;
    return 0;
}