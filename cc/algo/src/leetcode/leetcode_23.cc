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
     ListNode* mergeKLists(vector<ListNode*>& lists) {
        struct Point {
            ListNode* node;
            int index;
            Point(ListNode* node, int index) : node(node), index(index) {}
            bool operator>(const Point& other) const {
                return node->val > other.node->val;
            }
        };
        priority_queue<Point, vector<Point>, greater<Point>> pq;
        for (int i = 0; i < lists.size(); i++) {
            if (lists[i]) {
                pq.push(Point(lists[i], i));
            }
        }
        ListNode* dummy = new ListNode(0);
        ListNode* current = dummy;
        while (!pq.empty()) {
            Point p = pq.top();
            pq.pop();
            current->next = p.node;
            current = current->next;
            if (p.node->next) {
                pq.push(Point(p.node->next, p.index));
            }
        }
        return dummy->next;
    }
};

int main() {
    Solution solution;
    vector<ListNode*> lists = {new ListNode(1, new ListNode(4, new ListNode(5))), new ListNode(1, new ListNode(3, new ListNode(4))), new ListNode(2, new ListNode(6))};
    ListNode* result = solution.mergeKLists(lists);
    while (result) {
        cout << result->val << " ";
        result = result->next;
    }
    cout << endl;
    return 0;
}