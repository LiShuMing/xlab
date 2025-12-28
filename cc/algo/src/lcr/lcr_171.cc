#include "../include/fwd.h"

class Solution {
public:
    ListNode* getIntersectionNode(ListNode* headA, ListNode* headB) {
        ListNode* p1 = headA;
        ListNode* p2 = headB;
        while (p1 != p2) {
            p1 = p1 != NULL ? p1->next : headB;
            p2 = p2 != NULL ? p2->next : headA;
        }
        return p1;
    }
};

int main() {
    Solution solution;
    ListNode* headA = new ListNode(1);
    ListNode* headB = new ListNode(2);
    headA->next = new ListNode(3);
    headB->next = new ListNode(4);
    headA->next->next = new ListNode(5);
    headB->next->next = new ListNode(6);
    headA->next->next->next = new ListNode(7);
    headB->next->next->next = new ListNode(8);
    cout << solution.getIntersectionNode(headA, headB)->val << endl;
    return 0;
}