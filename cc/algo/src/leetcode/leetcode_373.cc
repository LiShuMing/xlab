#include "../include/fwd.h"

class Solution {
public:
    vector<vector<int>> kSmallestPairs(vector<int>& nums1, vector<int>& nums2, int k) {
        if (nums1.empty() || nums2.empty()) return {};
        // priority_queue<pair<int, pair<int, int>>, vector<pair<int, pair<int, int>>>, less<pair<int, pair<int, int>>>> pq;
        // for (int i = 0; i < nums1.size(); i++) {
        //     for (int j = 0; j < nums2.size(); j++) {
        //         pq.push({nums1[i] + nums2[j], {i, j}});
        //         if (pq.size() > k) {
        //             pq.pop();
        //         }
        //     }
        // }
        // vector<vector<int>> ans;
        // while (!pq.empty()) {
        //     auto [_, pair] = pq.top();
        //     int i = pair.first;
        //     int j = pair.second;
        //     ans.push_back({nums1[i], nums2[j]});
        //     pq.pop();
        // }
        // return ans;

        // use a min heap to store the pairs
        int m = nums1.size();
        int n = nums2.size();
        vector<vector<int>> ans;
        auto cmp = [&](const pair<int, int>& a, const pair<int, int>& b) {
            return nums1[a.first] + nums2[a.second] > nums1[b.first] + nums2[b.second];
        };
        priority_queue<pair<int, int>, vector<pair<int, int>>, decltype(cmp)> pq(cmp);
        for (int i = 0; i < min(k, m); i++) {
            pq.push({i, 0});
        }
        while (!pq.empty() && k > 0) {
            auto [x, y] = pq.top();
            ans.push_back({nums1[x], nums2[y]});
            pq.pop();
            if (y < n - 1) {
                pq.push({x, y + 1});
            }
            k--;
        }
        return ans;
    }
};

int main() {
    Solution solution;
    vector<int> nums1 = {1, 7, 11};
    vector<int> nums2 = {2, 4, 6};
    int k = 3;
    vector<vector<int>> ans = solution.kSmallestPairs(nums1, nums2, k);
    for (auto& a : ans) {
        cout << a[0] << " " << a[1] << endl;
    }
    return 0;
}