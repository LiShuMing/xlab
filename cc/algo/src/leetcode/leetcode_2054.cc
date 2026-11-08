#include "../include/fwd.h"

class Solution {
private:
    class Event {
    public:
        int startTime;
        int endTime;
        int value;
        Event(int startTime, int endTime, int value) : startTime(startTime), endTime(endTime), value(value) {}
    };

public:
    int maxTwoEvents(vector<vector<int>>& events) {
        int n = events.size();
        vector<Event> sortedEvents;
        for (int i = 0; i < n; ++i) {
            sortedEvents.emplace_back(events[i][0], events[i][1], events[i][2]);
        }

        sort(sortedEvents.begin(), sortedEvents.end(), [](const Event& a, const Event& b) {
            return a.endTime < b.endTime;
        });

        vector<int> ends(n);
        vector<int> best(n + 1, 0);
        for (int i = 0; i < n; ++i) {
            ends[i] = sortedEvents[i].endTime;
            best[i + 1] = max(best[i], sortedEvents[i].value);
        }
        int ans = 0;
        for (int i = 0; i < n; ++i) {
            auto it = lower_bound(ends.begin(), ends.end(), sortedEvents[i].startTime);
            ans = max(ans, sortedEvents[i].value + best[it - ends.begin()]);
        }
        return ans;
    }
};
