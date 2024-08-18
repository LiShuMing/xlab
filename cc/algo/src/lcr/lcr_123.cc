#include "../include/fwd.h"
class Solution {
public:
    vector<int> reverseBookList(ListNode* head) {
        // ListNode* prev = nullptr;
        // ListNode* current = head;
        // while (current) {
        //     ListNode* next = current->next;
        //     current->next = prev;
        //     prev = current;
        //     current = next;
        // }
        // return prev;
        vector<int> ans;
        while (head) {
            ans.push_back(head->val);
            head = head->next;
        }
        reverse(ans.begin(), ans.end());
        return ans;
    }
};
int main() {
    Solution solution;
    ListNode* head = new ListNode(1, new ListNode(2, new ListNode(3)));
    vector<int> ans = solution.reverseBookList(head);
    for (int i = 0; i < ans.size(); i++) {
        cout << ans[i] << " ";
    }
    cout << endl;
    return 0;
}