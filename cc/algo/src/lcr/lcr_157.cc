#include "../include/fwd.h"
#include <unordered_set>

class Solution {
public:
    vector<string> goodsOrder(string goods) {
        vector<string> result;
        backtrack(goods, 0, result);
        return result;
    }

    void backtrack(string& goods, int start, vector<string>& result) {
        if (start == goods.size()) {
            result.push_back(goods);
            return;
        }
        unordered_set<char> used;
        for (int i = start; i < goods.size(); i++) {
            if (used.count(goods[i])) continue;  // avoid repeated chars
            used.insert(goods[i]);
            swap(goods, start, i);
            backtrack(goods, start + 1, result);
            swap(goods, start, i);
        }
    }
    void swap(string& goods, int i, int j) {
        char temp = goods[i];
        goods[i] = goods[j];
        goods[j] = temp;
    }
};

int main() {
    Solution solution;
    string goods = "abc";
    vector<string> result = solution.goodsOrder(goods);
    for (const auto& order : result) {
        cout << order << endl;
    }
    return 0;
}