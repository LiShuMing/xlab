#include "../include/fwd.h"

// class Solution {
// public:
//     std::vector<int> maxSlidingWindow(const std::vector<int>& nums, int k) {
//         // sliding window
//         int n = nums.size();
//         if (n == 0 || k == 0) {
//             return {};
//         }
//         if (k >= n) {
//             return { *std::max_element(nums.begin(), nums.end()) };
//         }
//         std::vector<int> res;
//         // max is the index of the maximum element in the window
//         int max = std::distance(nums.begin(), std::max_element(nums.begin(), nums.begin() + k));
//         res.push_back(nums[max]);

//         int l = 0, r = k;
//         for (int i = k; i < n; ++i) {
//             ++l;
//             ++r;
//             // if max is out of the window, update it
//             if (max <= l) {
//                 max = std::distance(nums.begin(), std::max_element(nums.begin() + l, nums.begin() + r));
//             } else {
//                 //
//                 // max is in the window, compare nums[i] with nums[max]
//                 if (nums[i] > nums[max]) {
//                     max = i;
//                 }
//             }
//             res.push_back(nums[max]);
//         }
//         return res;
//     }
// };


class Solution {
public:
    std::vector<int> maxSlidingWindow(const std::vector<int>& nums, int k) {
        // sliding window
        int n = nums.size();
        if (n == 0 || k == 0) {
            return {};
        }
        if (k >= n) {
            return { *std::max_element(nums.begin(), nums.end()) };
        }
        std::vector<int> res;
        // queue: store the indices of the elements in the window
        // 单调队列： 单调递减
        deque<int> q;
        for (int i = 0; i < n; ++i) {
            // shrink window: move all elements smaller than nums[i] to the left
            while (!q.empty() && q.front() <= i - k) {
                q.pop_front();
            }
            // maintain the queue: move all elements smaller than nums[i] to the left
            while (!q.empty() && nums[i] > nums[q.back()]) {
                q.pop_back();
            }
            q.push_back(i);
            if (i >= k - 1) {
                res.push_back(nums[q.front()]);
            }
        }
        return res;
    }
};
