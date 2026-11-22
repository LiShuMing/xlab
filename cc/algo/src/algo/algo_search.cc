#include "../include/fwd.h"


namespace {

void binary_search(const vector<int>& nums, int target) {
    int l = 0;
    int r = nums.size() - 1;
    
    while (l <= r) {
        int mid = l + (r - l) / 2;
        if (nums[mid] == target) {
            return mid;
        } else if (nums[mid] < target) {
            l = mid + 1;
        } else {
            r = mid - 1;
        }
    }
    return -1;
}

};

void main() {
    
    vector<int> nums = {1, 2, 3, 4, 5};
    int target = 3;
    binary_search(nums, target);
}
