#include "../include/fwd.h"
class Solution {
public:
    char dismantlingAction(string arr) {
        map<char, int> freq;
        for (char c : arr) {
            freq[c]++;
        }
        for (char c : arr) {
            if (freq[c] == 1) {
                return c;
            }
        }
        return ' ';
    }
};
int main() {
    Solution solution;
    cout << solution.dismantlingAction("abbccdeff") << endl;
    cout << solution.dismantlingAction("zzzxxxccc") << endl;
    cout << solution.dismantlingAction("zzzxxxccc") << endl;
    return 0;
}