#include <queue>
#include <set>

#include "../include/fwd.h"

// class Solution {
// private:
//     struct XSumHeap {
//         unordered_map<int, int> valueToCount;
//         int x;
//         int k;
//         long long xSum;

//         struct Comp {
//             bool operator()(const pair<int, int>& a, const pair<int, int>& b) const {
//                 if (a.first != b.first) return a.first > b.first;
//                 return a.second > b.second;
//             }
//         };

//         set<pair<int, int>, Comp> allOrdered;
//         set<pair<int, int>, Comp> topX;

//         XSumHeap(int x_, int k_) : x(x_), k(k_), xSum(0) {}

//         void rebuildTopX() {
//             topX.clear();
//             xSum = 0;
//             int cnt = 0;
//             for (auto it = allOrdered.begin(); it != allOrdered.end() && cnt < x; ++it, ++cnt) {
//                 topX.insert(*it);
//                 xSum += (long long)it->first * it->second;
//             }
//         }

//         void init(const vector<int>& nums) {
//             for (int i = 0; i < k; i++) {
//                 int val = nums[i];
//                 int oldCount = 0;
//                 auto it = valueToCount.find(val);
//                 if (it != valueToCount.end()) {
//                     oldCount = it->second;
//                     allOrdered.erase(make_pair(oldCount, val));
//                 }
//                 int newCount = oldCount + 1;
//                 valueToCount[val] = newCount;
//                 allOrdered.insert(make_pair(newCount, val));
//             }
//             rebuildTopX();
//         }

//         void remove(int val) {
//             auto it = valueToCount.find(val);
//             if (it == valueToCount.end()) return;

//             int oldCount = it->second;
//             allOrdered.erase(make_pair(oldCount, val));

//             int newCount = oldCount - 1;
//             if (newCount > 0) {
//                 valueToCount[val] = newCount;
//                 allOrdered.insert(make_pair(newCount, val));
//             } else {
//                 valueToCount.erase(it);
//             }

//             rebuildTopX();
//         }

//         void add(int val) {
//             int oldCount = 0;
//             auto it = valueToCount.find(val);
//             if (it != valueToCount.end()) {
//                 oldCount = it->second;
//                 allOrdered.erase(make_pair(oldCount, val));
//             }

//             int newCount = oldCount + 1;
//             valueToCount[val] = newCount;
//             allOrdered.insert(make_pair(newCount, val));

//             rebuildTopX();
//         }

//         long long getXSum() {
//             return xSum;
//         }
//     };

// public:
//     vector<long long> findXSum(vector<int>& nums, int k, int x) {
//         int n = nums.size();
//         vector<long long> ans;
//         ans.reserve(n - k + 1);

//         XSumHeap xsumHeap(x, k);
//         xsumHeap.init(nums);
//         ans.push_back(xsumHeap.getXSum());

//         for (int i = k; i < n; i++) {
//             xsumHeap.remove(nums[i - k]);
//             xsumHeap.add(nums[i]);
//             ans.push_back(xsumHeap.getXSum());
//         }
//         return ans;
//     }
// };

class Helper {
public:
    Helper(int x) {
        this->x = x;
        this->result = 0;
    }

    void insert(int num) {
        if (occ[num]) {
            internalRemove({occ[num], num});
        }
        ++occ[num];
        internalInsert({occ[num], num});
    }

    void remove(int num) {
        internalRemove({occ[num], num});
        --occ[num];
        if (occ[num]) {
            internalInsert({occ[num], num});
        }
    }

    long long get() { return result; }

private:
    void internalInsert(const pair<int, int>& p) {
        if (large.size() < x || p > *large.begin()) {
            result += static_cast<long long>(p.first) * p.second;
            large.insert(p);
            if (large.size() > x) {
                result -= static_cast<long long>(large.begin()->first) * large.begin()->second;
                auto transfer = *large.begin();
                large.erase(transfer);
                small.insert(transfer);
            }
        } else {
            small.insert(p);
        }
    }

    void internalRemove(const pair<int, int>& p) {
        if (p >= *large.begin()) {
            result -= static_cast<long long>(p.first) * p.second;
            large.erase(p);
            if (!small.empty()) {
                result += static_cast<long long>(small.rbegin()->first) * small.rbegin()->second;
                auto transfer = *small.rbegin();
                small.erase(transfer);
                large.insert(transfer);
            }
        } else {
            small.erase(p);
        }
    }

private:
    int x;
    long long result;
    set<pair<int, int>> large, small;
    unordered_map<int, int> occ;
};

class Solution {
public:
    vector<long long> findXSum(vector<int>& nums, int k, int x) {
        Helper helper(x);

        vector<long long> ans;
        for (int i = 0; i < nums.size(); ++i) {
            helper.insert(nums[i]);
            if (i >= k) {
                helper.remove(nums[i - k]);
            }
            if (i >= k - 1) {
                ans.push_back(helper.get());
            }
        }
        return ans;
    }
};

int main() {
    Solution solution;
    int arr[] = {1, 1, 2, 2, 3, 4, 2, 3};
    vector<int> nums(arr, arr + 8);
    int k = 6;
    int x = 2;

    vector<long long> ans = solution.findXSum(nums, k, x);
    printVector(ans);
    return 0;
}
