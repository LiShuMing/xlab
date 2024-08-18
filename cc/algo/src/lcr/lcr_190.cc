#include "../include/fwd.h"

class Solution {
public:
    int encryptionCalculate(int dataA, int dataB) {
        while (dataB != 0) {
            int c = (unsigned int)(dataA & dataB) << 1;
            dataA = dataA ^ dataB;
            dataB = c;
        }
        return dataA;
    }
};
int main() {
    Solution solution;
    cout << solution.encryptionCalculate(1, 2) << endl;
    return 0;
}