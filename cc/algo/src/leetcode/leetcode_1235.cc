#include "../include/fwd.h"

class Solution {
private:
    class Job {
    public:
        int startTime;
        int endTime;
        int profit;
        Job(int startTime, int endTime, int profit) : startTime(startTime), endTime(endTime), profit(profit) {}
    };

public:
    int jobScheduling(vector<int>& startTime, vector<int>& endTime, vector<int>& profit) {
        int n = startTime.size();
        if (n == 0) return 0;

        vector<Job> jobs;
        for (int i = 0; i < n; ++i) {
            jobs.emplace_back(startTime[i], endTime[i], profit[i]);
        }
        sort(jobs.begin(), jobs.end(), [](const Job& a, const Job& b) {
            return a.endTime < b.endTime;
        });

        vector<int> ends(n);
        for (int i = 0; i < n; ++i) {
            ends[i] = jobs[i].endTime;
        }

        vector<int> dp(n + 1, 0);

        for (int i = 1; i <= n; ++i) {
            auto it = upper_bound(ends.begin(), ends.begin() + i - 1, jobs[i-1].startTime);
            dp[i] = max(dp[i-1], jobs[i-1].profit + (it == ends.begin() ? 0 : dp[it - ends.begin()]));
        }
        return dp[n];
    }
};
