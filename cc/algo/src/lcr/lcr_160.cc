#include "../include/fwd.h"

class MedianFinder {
private:
    // bigger half, max heap
    priority_queue<int, vector<int>, less<int>> bq;
    // smaller half, min heap
    priority_queue<int, vector<int>, greater<int>> sq;

public:
    /** initialize your data structure here. */
    MedianFinder() {}

    void addNum(int num) {
        if (bq.empty() || num <= bq.top()) {
            bq.push(num);
        } else {
            sq.push(num);
        }
        while (bq.size() > sq.size() + 1) {
            sq.push(bq.top());
            bq.pop();
        }
        while (sq.size() > bq.size() + 1) {
            bq.push(sq.top());
            sq.pop();
        }
    }

    double findMedian() {
        if (bq.size() == sq.size()) {
            return (bq.top() + sq.top()) / 2.0;
        } else if (bq.size() > sq.size()) {
            return bq.top();
        } else {
            return sq.top();
        }
    }
};

int main() {
    MedianFinder medianFinder;
    medianFinder.addNum(1);
    cout << medianFinder.findMedian() << endl;
    medianFinder.addNum(2);
    cout << medianFinder.findMedian() << endl;
    medianFinder.addNum(3);
    cout << medianFinder.findMedian() << endl;
    medianFinder.addNum(4);
    cout << medianFinder.findMedian() << endl;
    medianFinder.addNum(5);
    cout << medianFinder.findMedian() << endl;
    medianFinder.addNum(6);
    cout << medianFinder.findMedian() << endl;
    medianFinder.addNum(7);
    cout << medianFinder.findMedian() << endl;
    medianFinder.addNum(8);
    cout << medianFinder.findMedian() << endl;
    return 0;
}