#include "../include/fwd.h"

class Checkout {
    private:
        queue<int> q;
        deque<int> max_q;  // Use deque to support removal from both ends
public:
    Checkout() {}

    int get_max() {
        if (max_q.empty()) {
            return -1;
        }
        return max_q.front();
    }

    void add(int value) {
        q.push(value);
        // Remove elements from back that are smaller than current value
        while (!max_q.empty() && max_q.back() < value) {
            max_q.pop_back();
        }
        max_q.push_back(value);
    }

    int remove() {
        if (q.empty()) {
            return -1;
        }
        int value = q.front();
        q.pop();
        // Remove from front if the removed value is the current max
        if (!max_q.empty() && value == max_q.front()) {
            max_q.pop_front();
        }
        return value;
    }
};

int main() {
    Checkout checkout;
    checkout.add(1);
    checkout.add(2);
    checkout.add(3);
    cout << checkout.get_max() << endl;
    cout << checkout.remove() << endl;
    cout << checkout.get_max() << endl;
    return 0;
}