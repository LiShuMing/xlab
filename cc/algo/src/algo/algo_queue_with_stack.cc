#include "../include/fwd.h"

class ConcurrentQueueWithStack {
private:
    // input stack
    stack<int> st1;
    // output stack
    stack<int> st2;
    // mutex for thread safety
    std::mutex mtx;
    std::condition_variable cv;
public:
    ConcurrentQueueWithStack() {}
    ~ConcurrentQueueWithStack() {}

    void transfer_no_lock() {
        if (st2.empty()) {
            while (!st1.empty()) {
                st2.push(st1.top());
                st1.pop();
            }
        }
    }

    void push(int value) {
        std::unique_lock<std::mutex> lock(mtx);
        st1.push(value);
        cv.notify_all();
    }
    int pop() {
        std::unique_lock<std::mutex> lock(mtx);
        transfer_no_lock();
        cv.wait(lock, [this]() { return !st2.empty(); });
        int value = st2.top();
        st2.pop();
        return value;
    }
    int top() {
        std::unique_lock<std::mutex> lock(mtx);
        transfer_no_lock();
        cv.wait(lock, [this]() { return !st2.empty(); });
        return st2.top();
    }
    bool empty() {
        std::unique_lock<std::mutex> lock(mtx);
        return st1.empty() && st2.empty();
    }
    size_t size() {
        std::unique_lock<std::mutex> lock(mtx);
        return st1.size() + st2.size();
    }
};

int main() {
    ConcurrentQueueWithStack queue;
    for (int i = 0; i < 10; i++) {
        queue.push(rand() % 100);
    }
    while (!queue.empty()) {
        cout << queue.pop() << endl;
    }
    return 0;
}