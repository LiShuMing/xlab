#include "../include/fwd.h"

/**
 * https://oi-wiki.org/ds/queue/
 */
void test_stack() {
    stack<int> st;
    st.push(1);
    st.push(2);
    st.push(3);
    while (!st.empty()) {
        cout << st.top() << " ";
        st.pop();
    }
    cout << endl;
}

void test_queue() {
    queue<int> q;
    q.push(1);
    q.push(2);
    q.push(3);
    cout << "queue front: " << q.front() << endl;
    cout << "queue back: " << q.back() << endl;
    cout << "queue size: " << q.size() << endl;
    while (!q.empty()) {
        cout << q.front() << " ";
        q.pop();
    }
    cout << endl;
}

void test_deque() {
    deque<int> dq;
    dq.push_front(1);
    dq.push_back(2);
    dq.push_front(3);
    dq.push_back(4);
    cout << "deque front: " << dq.front() << endl;
    cout << "deque back: " << dq.back() << endl;
    cout << "deque size: " << dq.size() << endl;

    // insert
    dq.insert(dq.begin() + 1, 5);
    cout << "deque after insert: ";
    for (int i = 0; i < dq.size(); i++) {
        cout << dq[i] << " ";
    }
    cout << endl;

    // erase
    dq.erase(dq.begin() + 1);

    // clear
    while (!dq.empty()) {
        cout << dq.front() << " ";
        dq.pop_front();
    }
    cout << endl;
}
void test_priority_queue() {
    priority_queue<int> pq;
    pq.push(1);
    pq.push(2);
    pq.push(3);
    while (!pq.empty()) {
        cout << pq.top() << " ";
        pq.pop();
    }
    cout << endl;
}

int main() {
    test_stack();
    test_queue();
    test_deque();
    return 0;
}