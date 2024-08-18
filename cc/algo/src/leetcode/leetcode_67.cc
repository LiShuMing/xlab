#include "../include/fwd.h"
class Solution {
public:
    string addBinary(string a, string b) {
        int n = a.size();
        int m = b.size();
        int i = n - 1;
        int j = m - 1;
        int carry = 0;
        string result = "";
        while (i >= 0 || j >= 0 || carry > 0) {
            int sum = carry;
            if (i >= 0) {
                sum += a[i] - '0';
                i--;
            }
            if (j >= 0) {
                sum += b[j] - '0';
                j--;
            }
            result = to_string(sum % 2) + result;
            carry = sum / 2;
        }
        return result;
    }
};