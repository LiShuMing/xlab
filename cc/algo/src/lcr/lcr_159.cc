#include "../include/fwd.h"
class Solution {
    public:
        vector<int> inventoryManagement(vector<int>& stock, int cnt) {
           priority_queue<int, vector<int>, less<int>> pq;
           for (int num : stock) {
                pq.push(num);
                if (pq.size() > cnt) {
                    // remove the greatest element
                    pq.pop();
                }
           }
           vector<int> ans;
           while (!pq.empty()) {
            ans.push_back(pq.top());
            pq.pop();
           }
           return ans;
        }
};

int main() {
    Solution solution;
    vector<int> stock = {1, 2, 3, 4, 5};
    int cnt = 3;
    vector<int> ans = solution.inventoryManagement(stock, cnt);
    cout << "ans: ";
    printVector(ans);
    return 0;
}