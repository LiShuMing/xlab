#include "../include/fwd.h"
class Solution {
public:
    long long power(long long base, int exp, int MOD) {
        long long result = 1;
        while (exp > 0) {
            if (exp % 2 == 1) {
                result = (result * base) % MOD;
            }
            base = (base * base) % MOD;
            exp /= 2;
        }
        return result;
    }
    
    int cuttingBamboo(int bamboo_len) {
        if (bamboo_len <= 3) return bamboo_len - 1;
        int MOD = 1e9 + 7;
        int remainder = bamboo_len % 3;
        int quotient = bamboo_len / 3;
        
        if (remainder == 0) {
            return power(3, quotient, MOD);
        } else if (remainder == 1) {
            return (power(3, quotient - 1, MOD) * 4) % MOD;
        } else {
            return (power(3, quotient, MOD) * 2) % MOD;
            }
    }
};
int main() {
    Solution solution;
    cout << solution.cuttingBamboo(5) << endl;
    return 0;
}