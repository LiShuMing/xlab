#include "../include/fwd.h"

struct MeetingComparator {
    bool operator()(const vector<int>& a, const vector<int>& b) const {
        return a[0] < b[0];
    }
};

class Solution {
public:
    int mostBooked(int n, vector<vector<int> >& meetings) {
        sort(meetings.begin(), meetings.end(), MeetingComparator());

        // available rooms (min heap by room number)
        priority_queue<int, vector<int>, greater<int> > available_rooms;
        for (int i = 0; i < n; i++) {
            available_rooms.push(i);
        }
        
        vector<int> count(n, 0);
        long long current_time = 0;
        
        // used rooms: (end time, room number)
        priority_queue<pair<long long, int>, vector<pair<long long, int> >, greater<pair<long long, int> > > used_rooms;
        
        for (int i = 0; i < meetings.size(); i++) {
            vector<int>& meeting = meetings[i];
            current_time = max(current_time, static_cast<long long>(meeting[0]));

            // release the rooms that are available
            while (!used_rooms.empty() && used_rooms.top().first <= current_time) {
                available_rooms.push(used_rooms.top().second);
                used_rooms.pop();
            }

            // if no available rooms, wait for the earliest one
            if (available_rooms.empty()) {
                current_time = used_rooms.top().first;
                available_rooms.push(used_rooms.top().second);
                used_rooms.pop();
            }

            int room = available_rooms.top();
            available_rooms.pop();
            count[room]++;
            
            long long end_time = current_time + static_cast<long long>(meeting[1] - meeting[0]);
            used_rooms.push(make_pair(end_time, room));
        }
        
        int ans = 0;
        for (int i = 0; i < n; i++) {
            if (count[i] > count[ans]) {
                ans = i;
            }
        }
        return ans;
    }
};

int main() {
    Solution solution;
    
    // Test case 1: [[0,10],[1,5],[2,7],[3,4]]
    int arr1[][2] = {{0,10},{1,5},{2,7},{3,4}};
    vector<vector<int> > meetings1;
    for (int i = 0; i < 4; i++) {
        vector<int> meeting;
        meeting.push_back(arr1[i][0]);
        meeting.push_back(arr1[i][1]);
        meetings1.push_back(meeting);
    }
    cout << "Test 1 (n=2): " << solution.mostBooked(2, meetings1) << " (expected: 0)" << endl;
    
    // Test case 2: [[1,20],[2,10],[3,5],[4,9],[6,8]]
    int arr2[][2] = {{1,20},{2,10},{3,5},{4,9},{6,8}};
    vector<vector<int> > meetings2;
    for (int i = 0; i < 5; i++) {
        vector<int> meeting;
        meeting.push_back(arr2[i][0]);
        meeting.push_back(arr2[i][1]);
        meetings2.push_back(meeting);
    }
    cout << "Test 2 (n=3): " << solution.mostBooked(3, meetings2) << " (expected: 1)" << endl;
    
    return 0;
}