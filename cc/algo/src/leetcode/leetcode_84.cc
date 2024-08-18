#include "../include/fwd.h"

/**
 * Given n non-negative integers representing the heights of histogram bars.
 * Each bar has width 1. Find the maximum area of a rectangle that can be
 * outlined by the histogram.
 *
 * Monotonic Stack Approach:
 * - Use an increasing stack to store bar indices
 * - left[i]: index of the first bar to the left that is shorter than heights[i] (-1 if none)
 * - right[i]: index of the first bar to the right that is shorter than heights[i] (n if none)
 * - Rectangle width = right[i] - left[i] - 1
 */
class Solution {
public:
    int largestRectangleArea(vector<int>& heights) {
        int n = heights.size();
        if (n == 0) return 0;
        
        vector<int> left(n), right(n);
        stack<int> st;
        
        // Find the first smaller element to the left
        for (int i = 0; i < n; i++) {
            while (!st.empty() && heights[st.top()] >= heights[i]) {
                st.pop();
            }
            left[i] = st.empty() ? -1 : st.top();
            st.push(i);
        }
        
        // Create a new stack to find the first smaller element to the right
        stack<int> st2;
        for (int i = n - 1; i >= 0; i--) {
            while (!st2.empty() && heights[st2.top()] >= heights[i]) {
                st2.pop();
            }
            right[i] = st2.empty() ? n : st2.top();
            st2.push(i);
        }
        
        // Calculate the maximum area
        int ans = 0;
        for (int i = 0; i < n; i++) {
            int width = right[i] - left[i] - 1;
            ans = max(ans, heights[i] * width);
        }
        return ans;
    }
};

// Optimized version: single pass with sentinels (cleaner and more efficient)
class Solution2 {
public:
    int largestRectangleArea(vector<int>& heights) {
        int n = heights.size();
        if (n == 0) return 0;
        
        // Add sentinels at both ends to avoid boundary checks
        heights.insert(heights.begin(), 0);
        heights.push_back(0);
        
        stack<int> st;  // Store indices, monotonically increasing
        int ans = 0;
        
        for (int i = 0; i < heights.size(); i++) {
            // Current height is less than stack top, calculate rectangle area
            while (!st.empty() && heights[i] < heights[st.top()]) {
                int h = heights[st.top()];
                st.pop();
                int width = i - st.top() - 1;
                ans = max(ans, h * width);
            }
            st.push(i);
        }
        
        return ans;
    }
};
