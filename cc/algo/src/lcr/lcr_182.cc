#include "../include/fwd.h"
class Solution {
public:
    string dynamicPassword(string password, int target) {
        reverse(password, 0, target - 1);
        reverse(password, target, password.size() - 1);
        reverse(password, 0, password.size() - 1);
        return password;
    }

    void reverse(string& password, int start, int end) {
        while (start < end) {
            swap(password[start], password[end]);
            start++;
            end--;
        }
    }
};

int main() {
    Solution solution;
    cout << solution.dynamicPassword("1234567890", 3) << endl;
    cout << solution.dynamicPassword("1234567890", 5) << endl;
    cout << solution.dynamicPassword("1234567890", 7) << endl;
    cout << solution.dynamicPassword("1234567890", 9) << endl;
    cout << solution.dynamicPassword("1234567890", 11) << endl;
    cout << solution.dynamicPassword("1234567890", 13) << endl;
    cout << solution.dynamicPassword("1234567890", 15) << endl;
    cout << solution.dynamicPassword("1234567890", 17) << endl;
    cout << solution.dynamicPassword("1234567890", 19) << endl;
    return 0;
}