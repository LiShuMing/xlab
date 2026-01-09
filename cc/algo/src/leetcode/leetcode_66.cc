#include "../include/fwd.h"
class Solution {
public:
    vector<int> plusOne(vector<int>& digits) {
        int n = digits.size();
        bool carry = true;
        for (int i = n - 1; i >= 0; i--) {
            int sum = digits[i] + (carry ? 1 : 0);
            if (sum == 10) {
                digits[i] = 0;
                carry = true;
            } else {
                digits[i] = sum;
                carry = false;
            }
        }
        if (carry) {
            digits.insert(digits.begin(), 1);
        }
        return digits;
    }
};
int main() {
    Solution solution;
    vector<int> digits = {9, 9, 9};
    vector<int> result = solution.plusOne(digits);
    printVector(result);
    return 0;
}