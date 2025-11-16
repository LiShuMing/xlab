#include "../include/fwd.h"

class Solution {
    private:
    // Optimized structure: map from count to set of values with that count
    // Use set (not unordered_set) to maintain descending order when count is same
    struct XSumHeap {
        std::map<int, std::set<int, std::greater<int>>, std::greater<int>> countToValues;
        std::unordered_map<int, int> valueToCount;
        int x;
        int k;
        long long total;
        long long xSum;
        XSumHeap(int x, int k) : x(x), k(k), total(0) {}
        void init(vector<int>& nums) {
            for (int i = 0; i < k; i++) {
                add(nums[i]);
            }
        }
        void remove(int val) {
            auto it = valueToCount.find(val);
            if (it != valueToCount.end() && it->second > 0) {
                int oldCount = it->second;
                countToValues[oldCount].erase(val);
                if (countToValues[oldCount].empty()) {
                    countToValues.erase(oldCount);
                }
                
                it->second--;
                total -= val;
                
                if (it->second > 0) {
                    countToValues[it->second].insert(val);
                } else {
                    valueToCount.erase(it);
                }
            }
        }
        void add(int val) {
            auto it = valueToCount.find(val);
            if (it != valueToCount.end() && it->second > 0) {
                int oldCount = it->second;
                countToValues[oldCount].erase(val);
                if (countToValues[oldCount].empty()) {
                    countToValues.erase(oldCount);
                    xSum -= (long long)oldCount * oldCount;
                }
                it->second++;
            } else {
                valueToCount[val] = 1;
            }
            
            total += val;
            countToValues[valueToCount[val]].insert(val);
            xSum += (long long)valueToCount[val] * valueToCount[val];
        }
        long long getXSum() {
            int distinctCount = valueToCount.size();
            if (distinctCount < x) {
                return total;
            }
            return xSum;
        }
    };
    public: 
        vector<long long> findXSum(vector<int>& nums, int k, int x) {
            int n = nums.size();
            vector<long long> ans;
            ans.reserve(n - k + 1);
            XSumHeap xsumHeap(x, k);
            xsumHeap.init(nums);
            ans.push_back(xsumHeap.getXSum());
            for (int i = k; i < n; i++) {
                xsumHeap.remove(nums[i - k]);
                xsumHeap.add(nums[i]);
                ans.push_back(xsumHeap.getXSum());
            }
            return ans;
        }
};

int main() {
    Solution solution;
    // case 1
    vector<int> nums = {1,1,2,2,3,4,2,3};
    int k = 6;
    int x = 2;

    // case 2
    // vector<int> nums = {1000000000,1000000000,1000000000,1000000000,1000000000,1000000000};
    // int k = 6;
    // int x = 1;

    vector<long long> ans = solution.findXSum(nums, k, x);
    printVector(ans);
    return 0;
}