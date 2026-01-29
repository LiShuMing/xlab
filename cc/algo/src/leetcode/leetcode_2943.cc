#include "../include/fwd.h"

class Solution {
public:
    int maximizeSquareHoleArea(int n, int m, vector<int>& hBars, vector<int>& vBars) {
        sort(hBars.begin(), hBars.end());
        sort(vBars.begin(), vBars.end());
        int m_vbar = 1;
        int m_hbar = 1;
        int cur_vbar = 1;
        int cur_hbar = 1;
        for (int i = 1; i < hBars.size(); i++) {
            if (hBars[i] == hBars[i - 1] + 1) {
                cur_hbar++;
            } else {
                cur_hbar = 1;
            }
            m_hbar = max(m_hbar, cur_hbar);
        }
        for (int i = 1; i < vBars.size(); i++) {
            if (vBars[i] == vBars[i - 1] + 1) {
                cur_vbar++;
            } else {
                cur_vbar = 1;
            }
            m_vbar = max(m_vbar, cur_vbar);
        }
        m_vbar = max(m_vbar, m_hbar) + 1;
        return m_vbar * m_hbar;
    }
};