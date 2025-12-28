#include "../include/fwd.h"

class Solution {
public:
    class MonotonicQueue {
    public:
        void push(int num) {
            while (!dq.empty() && dq.back() < num) {
                dq.pop_back();
            }
            dq.push_back(num);
        }
        
    private:
        deque<int> dq;
    };
    vector<int> maxSlidingWindow(vector<int>& nums, int k) {
        int n = nums.size();
        vector<int> ans;
        deque<int> dq;
        for (int i = 0; i < n; i++) {
            if (!dq.empty() && dq.front() == i - k) {
                dq.pop_front();
            }
            while (!dq.empty() && nums[dq.back()] < nums[i]) {
                dq.pop_back();
    }
};

int main() {
    Solution solution;
    return 0;
}