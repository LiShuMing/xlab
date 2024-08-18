#include "../include/fwd.h"

class Solution {
public:
    int maxProduct(vector<int>& nums) {
        int n = nums.size();
        int max_product = nums[0];
        int min_product = nums[0];
        int ans = nums[0];
        for (int i = 1; i < n; i++) {
            int temp = max_product;
            max_product = max(max(max_product * nums[i], min_product * nums[i]), nums[i]);
            min_product = min(min(temp * nums[i], min_product * nums[i]), nums[i]);
            ans = max(ans, max_product);
        }
        return ans;
    }

    int maxProduct2(vector<int>& nums) {
        int n = nums.size();

        vector<int> max_product(n, 0);
        vector<int> min_product(n, 0);
        max_product[0] = nums[0];
        min_product[0] = nums[0];
        for (int i = 1; i < n; i++) {
            max_product[i] = max(max(max_product[i - 1] * nums[i], min_product[i - 1] * nums[i]), nums[i]);
            min_product[i] = min(min(max_product[i - 1] * nums[i], min_product[i - 1] * nums[i]), nums[i]);
        }
        return *max_element(max_product.begin(), max_product.end());
    }
};