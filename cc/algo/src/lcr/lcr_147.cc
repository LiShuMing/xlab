#include "../include/fwd.h"

class MinStack {
private:
    stack<int> _st;
    stack<int> _min_st;

public:
    /** initialize your data structure here. */
    MinStack() {}

    void push(int x) {
        _st.push(x);
        if (_min_st.empty() || x <= _min_st.top()) {
            _min_st.push(x);
        }
    }

    void pop() {
        if (_st.top() == _min_st.top()) {
            _min_st.pop();
        }
        _st.pop();
    }

    int top() { return _st.top(); }

    int getMin() { return _min_st.top(); }
};

/**
     * Your MinStack object will be instantiated and called as such:
     * MinStack* obj = new MinStack();
     * obj->push(x);
     * obj->pop();
     * int param_3 = obj->top();
     * int param_4 = obj->getMin();
     */

int main() {
    MinStack minStack;
    minStack.push(2);
    minStack.push(0);
    minStack.push(3);
    minStack.push(0);
    cout << minStack.getMin() << endl;
    minStack.pop();
    cout << minStack.getMin() << endl;
    return 0;
}