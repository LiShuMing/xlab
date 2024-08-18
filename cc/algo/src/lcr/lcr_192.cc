#include "../include/fwd.h"

class Solution {
public:
    int myAtoi(string str) {
        int n = str.size();
        if (n == 0) return 0;
        int i = 0;
        while (i < n && str[i] == ' ') i++;
        if (i == n) return 0;
        int sign = 1;
        if (str[i] == '-') {
            sign = -1;
            i++;
        } else if (str[i] == '+') {
            i++;
        }
        long num = 0;
        while (i < n && str[i] >= '0' && str[i] <= '9') {
            num = num * 10 + (str[i] - '0');
            if (num > INT_MAX) {
                return sign == 1 ? INT_MAX : INT_MIN;
            }
            i++;
        }
        return sign * num;
    }
};

int main() {
    Solution solution;
    cout << solution.myAtoi("42") << endl;
    return 0;
}