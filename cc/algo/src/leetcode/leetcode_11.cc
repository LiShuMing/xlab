#include "../include/fwd.h"


class Solution {
public:
    int maxArea(vector<int>& height) {
        int n = height.size();
        int l = 0;
        int r = n - 1;
        int maxArea = 0;
        while (l < r) {
            int h = min(height[l], height[r]);
            int w = r - l;
            int area = h * w;
            maxArea = max(maxArea, area);

            // Move the pointer pointing to the shorter line inward
            if (height[l] < height[r]) {
                l++;
            } else {
                r--;
            }
        }
        return maxArea;
    }
};
