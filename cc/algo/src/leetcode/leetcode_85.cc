#include "../include/fwd.h"

/**
 * Given a binary matrix (characters '0' and '1'), find the largest rectangle
 * containing only 1's and return its area.
 *
 * Approach:
 * - Treat each row as the base of a histogram
 * - For each row, compute the heights of continuous 1's above (including current row)
 * - Apply Largest Rectangle in Histogram (leetcode_84) on each row's histogram
 * - Track the maximum area across all rows
 */
class Solution {
public:
    int maximalRectangle(vector<vector<char>>& matrix) {
        if (matrix.empty() || matrix[0].empty()) return 0;
        
        int n = matrix.size();
        int m = matrix[0].size();
        vector<int> heights(m, 0);
        int maxArea = 0;
        
        for (int i = 0; i < n; i++) {
            // Update heights for current row
            for (int j = 0; j < m; j++) {
                if (matrix[i][j] == '1') {
                    heights[j] += 1;
                } else {
                    heights[j] = 0;
                }
            }
            // Calculate max rectangle for this histogram
            maxArea = max(maxArea, largestRectangleArea(heights));
        }
        
        return maxArea;
    }
    
private:
    // Largest Rectangle in Histogram (leetcode_84 solution)
    int largestRectangleArea(const vector<int>& h) {
        int n = h.size();
        if (n == 0) return 0;
        
        vector<int> heights = h;  // Copy to add sentinels
        heights.insert(heights.begin(), 0);
        heights.push_back(0);
        
        stack<int> st;
        int ans = 0;
        
        for (int i = 0; i < heights.size(); i++) {
            while (!st.empty() && heights[i] < heights[st.top()]) {
                int height = heights[st.top()];
                st.pop();
                int width = i - st.top() - 1;
                ans = max(ans, height * width);
            }
            st.push(i);
        }
        
        return ans;
    }
};
