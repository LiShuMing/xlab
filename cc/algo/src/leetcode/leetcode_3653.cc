#include "../include/fwd.h"

class Solution {
    public:
        static const int MOD = 1e9 + 7;
        int xorAfterQueries(vector<int>& nums, vector<vector<int>>& queries) {
            // for (int i = 0; i < n; i++) {
            //     int idx = queries[i][0];
            //     auto& query = queries[idx];
            //     if (idx <= query[1]) {
            //         nums[idx] = (nums[idx] * query[3]) % MOD;
            //         idx += query[2];
            //     }
            // }
            int n = nums.size();
            long long A[n];
            for (int i = 0; i < n; i++) {
                A[i] = nums[i];
            }

            for (auto& query : queries) {
                for (int i = query[0]; i <= query[1]; i += query[2]) {
                    A[i] = A[i] * query[3] % MOD;
                }
            }
            int ans = 0;
            for (auto& num : A) {
                ans ^= num;
            }
            return ans;
        }
    };