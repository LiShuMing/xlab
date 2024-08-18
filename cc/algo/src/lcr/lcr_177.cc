#include "../include/fwd.h"

class Solution {
public:
    vector<int> sockCollocation(vector<int>& sockets) {
        int n = sockets.size();
        int x = 0;
        for (int i = 0; i < n; i++) {
            x ^= sockets[i];
        }
        int mask = 1;
        while ((x & mask) == 0) {
            mask <<= 1;
        }
        int a = 0, b = 0;
        for (int i = 0; i < n; i++) {
            if (sockets[i] & mask) {
                a ^= sockets[i];
            } else {
                b ^= sockets[i];
            }
        }
        return {a, b};
    }
};

int main() {
    Solution solution;
    vector<int> sockets = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
    vector<int> result = solution.sockCollocation(sockets);
    cout << result[0] << " " << result[1] << endl;
    return 0;
}