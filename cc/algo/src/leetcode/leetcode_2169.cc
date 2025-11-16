#include "../include/fwd.h"

class Solution {
public:
    int countOperations(int num1, int num2) {
        int ans = 0;
        while (num1 > 0 && num2 > 0) {
            if (num1 > num2) {
                num1 -= num2;
            } else {
                num2 -= num1;
            }
            ans++;
        }
        return ans;
    }
};

int main() {
    Solution solution;
    int num1 = 2, num2 = 3;
    cout << "num1: " << num1 << ", num2: " << num2 << ", ans: " << solution.countOperations(num1, num2) << endl;
    num1 = 10, num2 = 10;
    cout << "num1: " << num1 << ", num2: " << num2 << ", ans: " << solution.countOperations(num1, num2) << endl;
    return 0;
}