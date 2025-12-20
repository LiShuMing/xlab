#include "../include/fwd.h"

class MedianFinder {
private:
    priority_queue<int, vector<int>, less<int>> lq;
    priority_queue<int, vector<int>, greater<int>> rq;
public:
    MedianFinder() {}

    void addNum(int num) {
        if (lq.empty() || num <= lq.top()) {
            lq.push(num);
        } else {
            rq.push(num);
        }
        if (lq.size() > rq.size() + 1) {
            rq.push(lq.top());
            lq.pop();
        }
        if (rq.size() > lq.size() + 1) {
            lq.push(rq.top());
            rq.pop();
        }
    }

    double findMedian() {
        if (lq.size() == rq.size()) {
            return (lq.top() + rq.top()) / 2.0;
        } else if (lq.size() > rq.size()) {
            return lq.top();
        } else {
            return rq.top();
        }
    }
};

class MedianFinder2 {
private:
// use a sorted list to store the numbers
    vector<int> nums;
    int n;
public:
    MedianFinder2() {}
    void addNum(int num) {
        // nums.push_back(num);
        // sort(nums.begin(), nums.end());
        int i = lower_bound(nums.begin(), nums.end(), num) - nums.begin();
        nums.insert(nums.begin() + i, num);
        n++;
    }
    double findMedian() {
        if (n % 2 == 0) {
            return (nums[n/2 - 1] + nums[n/2]) / 2.0;
        } else {
            return nums[n/2];
        }
    }
};
int main() {
    MedianFinder medianFinder;
    medianFinder.addNum(1);
    medianFinder.addNum(2);
    cout << medianFinder.findMedian() << endl;
    medianFinder.addNum(3);
    cout << medianFinder.findMedian() << endl;
    return 0;
}