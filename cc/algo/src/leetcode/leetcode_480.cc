#include "../include/fwd.h"
#include <iomanip>
#include <set>

class MedianFinder {
private:
    // lq: multiset for lower half (ordered descending)
    // rq: multiset for upper half (ordered ascending)
    std::multiset<int, std::greater<int>> lq;
    std::multiset<int> rq;
    int k;

    // Rebalance to maintain:
    // 1. lq.size() == rq.size() or lq.size() == rq.size() + 1
    // 2. All elements in lq <= all elements in rq
    void rebalance() {
        // Balance sizes
        if (lq.size() > rq.size() + 1) {
            // Move largest from lq to rq
            auto it = lq.begin();
            rq.insert(*it);
            lq.erase(it);
        } else if (rq.size() > lq.size()) {
            // Move smallest from rq to lq
            auto it = rq.begin();
            lq.insert(*it);
            rq.erase(it);
        }
    }

public:
    MedianFinder(int windowSize = 0) : k(windowSize) {}

    void addNum(int num) {
        if (lq.empty() || num <= *lq.begin()) {
            lq.insert(num);
        } else {
            rq.insert(num);
        }
        rebalance();
    }

    void removeNum(int num) {
        // Try to remove from lq first
        auto itLq = lq.find(num);
        if (itLq != lq.end()) {
            lq.erase(itLq);
        } else {
            // Remove from rq
            auto itRq = rq.find(num);
            if (itRq != rq.end()) {
                rq.erase(itRq);
            }
        }
        rebalance();
    }

    double findMedian() {
        if (lq.size() == rq.size()) {
            return (*lq.begin() + *rq.begin()) / 2.0;
        } else {
            return *lq.begin();
        }
    }
};

/**
中位数是有序序列最中间的那个数。如果序列的长度是偶数，则没有最中间的数；此时中位数是最中间的两个数的平均数。

例如：

[2,3,4]，中位数是 3
[2,3]，中位数是 (2 + 3) / 2 = 2.5
给你一个数组 nums，有一个长度为 k 的窗口从最左端滑动到最右端。窗口中有 k 个数，每次窗口向右移动 1 位。你的任务是找出每次窗口移动后得到的新窗口中元素的中位数，并输出由它们组成的数组。


 */
class Solution {
public:
    vector<double> medianSlidingWindow(vector<int>& nums, int k) {
        vector<double> result;
        MedianFinder finder(k);

        // Add first k elements
        for (int i = 0; i < k; i++) {
            finder.addNum(nums[i]);
        }
        result.push_back(finder.findMedian());

        // Slide the window
        for (int i = k; i < nums.size(); i++) {
            // Add new element
            finder.addNum(nums[i]);
            // Remove element that's leaving the window
            finder.removeNum(nums[i - k]);
            // Get median
            result.push_back(finder.findMedian());
        }

        return result;
    }
};

// Test case for sliding window median
void testSlidingWindowMedian() {
    vector<int> nums = {1, 3, -1, -3, 5, 3, 6, 7};
    int k = 3;

    cout << "Input: nums = [1, 3, -1, -3, 5, 3, 6, 7], k = 3" << endl;

    // Expected: [1, -1, -1, 3, 5, 6]
    // Window 0: [1, 3, -1] -> sorted: [-1, 1, 3], median: 1
    // Window 1: [3, -1, -3] -> sorted: [-3, -1, 3], median: -1
    // Window 2: [-1, -3, 5] -> sorted: [-3, -1, 5], median: -1
    // Window 3: [-3, 5, 3] -> sorted: [-3, 3, 5], median: 3
    // Window 4: [5, 3, 6] -> sorted: [3, 5, 6], median: 5
    // Window 5: [3, 6, 7] -> sorted: [3, 6, 7], median: 6

    Solution s;
    vector<double> result = s.medianSlidingWindow(nums, k);

    cout << "Output: [";
    for (int i = 0; i < result.size(); i++) {
        cout << fixed << setprecision(5) << result[i];
        if (i < result.size() - 1) cout << ",";
    }
    cout << "]" << endl;
    cout << "Expected: [1.00000,-1.00000,-1.00000,3.00000,5.00000,6.00000]" << endl;
}

int main() {
    testSlidingWindowMedian();
    return 0;
}