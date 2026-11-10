#include "../include/fwd.h"
class Solution {
public:
    int compress(vector<char>& chars) {
        int n = chars.size();
        int l = 0;
        int r = 0;
        while (r < n) {
            int i = r;
            while (r < n && chars[r] == chars[i]) {
                r++;
            }
            chars[l++] = chars[i];
            if (r - i > 1) {
                for (char c : to_string(r - i)) {
                    chars[l++] = c;
                }
            }
        }
        return l;
    }
};
