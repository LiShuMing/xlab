#include "../include/fwd.h"

class Solution {
public:
    bool isPalindrome(int x) {
        if (x < 0 || (x % 10 == 0 && x != 0)) {
            return false;
        }

        // reverse the second half of the number
        int reversed = 0;
        while (x > reversed) {
            reversed = reversed * 10 + x % 10;
            x /= 10;
        }
        return x == reversed || x == reversed / 10;
    }
};

int main() {
    Solution solution;
    cout << solution.isPalindrome(121) << endl;
    cout << solution.isPalindrome(123) << endl;
    cout << solution.isPalindrome(12321) << endl;
    cout << solution.isPalindrome(123321) << endl;
    cout << solution.isPalindrome(1234321) << endl;
    cout << solution.isPalindrome(123454321) << endl;
    cout << solution.isPalindrome(12345654321) << endl;
    cout << solution.isPalindrome(1234567654321) << endl;
    return 0;
}