#include "../include/fwd.h"
#include <climits>
#include <algorithm>
#include <iostream>

using namespace std;

class Solution {
public:
    long long minimumCost(vector<int>& nums, int k, int dist) {
        int n = nums.size();
        const long long INF = LLONG_MAX / 4;

        // We need k subarrays with start positions: s1=0, s2, s3, ..., sk
        // Constraint: sk - s2 <= dist
        // Cost: nums[0] + nums[s2] + nums[s3] + ... + nums[sk]

        long long ans = INF;

        // Iterate over all valid (s2, sk) pairs
        for (int s2 = 1; s2 < n; s2++) {
            for (int sk = s2; sk < n && sk - s2 <= dist; sk++) {
                // We need to pick (k-1) positions from [s2, sk] (inclusive)
                // The positions are: s2, s3, ..., sk (k-1 positions)
                // This means picking (k-3) intermediate positions from (s2, sk)

                int available = sk - s2 + 1;  // positions in [s2, sk]
                int need = k - 1;             // total positions needed

                if (available < need) continue;  // not enough positions

                if (k == 2) {
                    // Only s2 (which is also sk)
                    ans = min(ans, static_cast<long long>(nums[0]) + nums[s2]);
                } else {
                    // Need to pick (k-3) intermediate positions from (s2, sk)
                    int m = k - 3;
                    if (m < 0) m = 0;

                    // DP: min cost to pick t positions from range [s2, x]
                    vector<vector<long long>> dp(m + 1, vector<long long>(sk - s2 + 1, INF));

                    // dp[t][i] = min cost to pick t positions from [s2, s2+i]
                    for (int i = 0; i <= sk - s2; i++) {
                        dp[0][i] = 0;
                    }

                    for (int t = 1; t <= m; t++) {
                        for (int i = t; i <= sk - s2; i++) {
                            // Don't pick position s2+i
                            dp[t][i] = min(dp[t][i], dp[t][i - 1]);
                            // Pick position s2+i
                            dp[t][i] = min(dp[t][i], dp[t - 1][i - 1] + nums[s2 + i]);
                        }
                    }

                    // Get minimum cost for picking m positions from [s2, sk-1]
                    long long minMid = dp[m][sk - s2 - 1];
                    if (minMid != INF) {
                        ans = min(ans, static_cast<long long>(nums[0]) + nums[s2] + minMid + nums[sk]);
                    }
                }
            }
        }

        return ans == INF ? -1 : ans;
    }
};

// Test function
void testMinimumCost() {
    Solution s;

    // Test case 1: k=2, constraint is always satisfied
    // Cost = nums[0] + nums[s2], minimize over s2
    vector<int> nums1 = {1, 2, 3, 4, 5};
    int k1 = 2;
    int dist1 = 3;
    cout << "Test 1: nums=[1,2,3,4,5], k=2, dist=3" << endl;
    cout << "Cost = nums[0] + nums[s2], minimize over s2" << endl;
    cout << "Expected: 1+2=3 (s2=1)" << endl;
    cout << "Result: " << s.minimumCost(nums1, k1, dist1) << endl;
    cout << endl;

    // Test case 2: k=3, need to pick s2 and s3 with s3 - s2 <= dist
    // Cost = nums[0] + nums[s2] + nums[s3]
    vector<int> nums2 = {5, 4, 3, 2, 1};
    int k2 = 3;
    int dist2 = 2;
    cout << "Test 2: nums=[5,4,3,2,1], k=3, dist=2" << endl;
    cout << "Cost = 5 + nums[s2] + nums[s3] with s3 - s2 <= 2" << endl;
    cout << "Best: s2=3, s3=4 -> 5+2+1=8" << endl;
    cout << "Result: " << s.minimumCost(nums2, k2, dist2) << endl;
    cout << endl;

    // Test case 3: mixed positive/negative
    vector<int> nums3 = {1, 3, -1, -3, 5, 3, 6, 7};
    int k3 = 4;
    int dist3 = 3;
    cout << "Test 3: nums=[1,3,-1,-3,5,3,6,7], k=4, dist=3" << endl;
    cout << "Result: " << s.minimumCost(nums3, k3, dist3) << endl;
}

int main() {
    testMinimumCost();
    return 0;
}
