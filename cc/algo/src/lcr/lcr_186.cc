#include "../include/fwd.h"
class Solution {
public:
    bool checkDynasty(vector<int>& places) {
        int n = places.size();
        sort(places.begin(), places.end()); // sort the places
        int zero_count = 0;
        for (int i = 0; i < n - 1; i++) {
            if (places[i] == 0) {
                zero_count++;
            } else if (places[i] == places[i + 1]) {
                return false;
            }
        }
        return places[4] - places[zero_count] <= 4;
    }
};
int main() {
    Solution solution;
    vector<int> places = {1, 2, 3, 4, 5};
    bool result = solution.checkDynasty(places);
    cout << (result ? "true" : "false") << endl;
    return 0;
}