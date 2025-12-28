#include "../include/fwd.h"
class CQueue {
private:
    queue<int> q1;

public:
    CQueue() {}

    void appendTail(int value) { q1.push(value); }

    int deleteHead() {
        if (q1.empty()) return -1;
        int value = q1.front();
        q1.pop();
        return value;
    }
};
int main() {
    CQueue cqueue;
    cqueue.appendTail(1);
    cqueue.appendTail(2);
    cqueue.appendTail(3);
    cout << cqueue.deleteHead() << endl;
    cout << cqueue.deleteHead() << endl;
}