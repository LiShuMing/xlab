#include "../include/fwd.h"

class NumArray {
public:
    vector<int> prefix;
    NumArray(vector<int>& nums) {
        int n = nums.size();
        prefix.resize(n + 1);
        for (int i = 0; i < n; i++) {
            prefix[i + 1] = prefix[i] + nums[i];
        }
    }
    void update(int index, int val) {
        int n = prefix.size();
        int diff = val - prefix[index + 1] + prefix[index];
        for (int i = index + 1; i < n; i++) {
            prefix[i] += diff;
        }
    }
    int sumRange(int left, int right) {
        return prefix[right + 1] - prefix[left];
    }
};
int main() {
    vector<int> nums = {1, 2, 3, 4, 5};
    NumArray numArray(nums);
    cout << numArray.sumRange(0, 2) << endl;
    cout << numArray.sumRange(1, 3) << endl;
    cout << numArray.sumRange(2, 4) << endl;
    return 0;
}