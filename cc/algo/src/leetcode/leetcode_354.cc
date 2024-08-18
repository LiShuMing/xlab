#include "../include/fwd.h"

class Solution {
public:
    /**
     * Russian Doll Envelopes
     * 
     * Strategy:
     * 1. Sort envelopes by width (ascending), and by height (descending) when widths are equal
     *    This ensures that after sorting, we only need to find LIS on heights
     * 2. Use binary search to optimize LIS from O(n^2) to O(n log n)
     * 
     * Why the sorting works:
     * - After sorting, if envelopes[j][1] < envelopes[i][1], then envelopes[j][0] < envelopes[i][0]
     *   (because same-width envelopes are sorted by height descending)
     * - So we only need to find the longest increasing subsequence on heights
     */
    int maxEnvelopes(vector<vector<int>>& envelopes) {
        if (envelopes.empty()) {
            return 0;
        }
        
        int n = envelopes.size();
        
        // Sort by width ascending, and by height descending when widths are equal
        // This ensures that for same width, larger heights come first
        // So when we check heights later, if h1 < h2, we know w1 < w2
        sort(envelopes.begin(), envelopes.end(), [](const auto& e1, const auto& e2) {
            return e1[0] < e2[0] || (e1[0] == e2[0] && e1[1] > e2[1]);
        });
        
        // Optimized LIS using binary search: O(n log n) instead of O(n^2)
        // tails[i] = smallest height that ends an increasing subsequence of length i+1
        vector<int> tails;
        
        for (int i = 0; i < n; ++i) {
            int height = envelopes[i][1];
            
            // Binary search for the position to insert/replace
            auto it = lower_bound(tails.begin(), tails.end(), height);
            
            if (it == tails.end()) {
                // height is larger than all elements, extend the sequence
                tails.push_back(height);
            } else {
                // Replace the first element >= height with height
                // This maintains the property that tails[i] is the smallest ending element
                *it = height;
            }
        }
        
        return tails.size();
    }
    
    /**
     * Original O(n^2) DP solution (for reference, may timeout on large inputs)
     */
    int maxEnvelopesDP(vector<vector<int>>& envelopes) {
        if (envelopes.empty()) {
            return 0;
        }
        
        int n = envelopes.size();
        sort(envelopes.begin(), envelopes.end(), [](const auto& e1, const auto& e2) {
            return e1[0] < e2[0] || (e1[0] == e2[0] && e1[1] > e2[1]);
        });
        
        vector<int> dp(n, 1);
        for (int i = 1; i < n; ++i) {
            for (int j = 0; j < i; ++j) {
                // After sorting, if heights[j] < heights[i], then widths[j] < widths[i]
                // (because same-width envelopes are sorted by height descending)
                if (envelopes[j][1] < envelopes[i][1]) {
                    dp[i] = max(dp[i], dp[j] + 1);
                }
            }
        }
        return *max_element(dp.begin(), dp.end());
    }
};

int main() {
    Solution solution;
    
    // Test cases
    vector<vector<int>> test1 = {{5,4},{6,4},{6,7},{2,3}};
    cout << "Test 1: " << solution.maxEnvelopes(test1) << " (expected: 3)" << endl;
    
    vector<vector<int>> test2 = {{1,1},{1,1},{1,1}};
    cout << "Test 2: " << solution.maxEnvelopes(test2) << " (expected: 1)" << endl;
    
    vector<vector<int>> test3 = {{1,3},{3,5},{6,7},{6,8},{8,4},{9,5}};
    cout << "Test 3: " << solution.maxEnvelopes(test3) << " (expected: 3)" << endl;
    
    return 0;
}