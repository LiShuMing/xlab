#include "../include/fwd.h"

class Solution {
public:
    vector<int> asteroidCollision(vector<int>& asteroids) {
        stack<int> s;
        for (int asteroid : asteroids) {
            if (s.empty() || asteroid > 0) {
                s.push(asteroid);
            } else {
                // if the current asteroid is negative 
                // and the top of the stack is positive
                // and the top of the stack is smaller than the current asteroid
                while (!s.empty() && s.top() > 0 && s.top() < -asteroid) {
                    s.pop();
                }
                // if the top of the stack is equal to the current asteroid
                if (!s.empty() && s.top() == -asteroid) {
                    s.pop();
                } else if (s.empty() || s.top() < 0) {
                    // if the stack is empty or the top of the stack is negative
                    // push the current asteroid onto the stack
                    s.push(asteroid);
                }
            }
        }
        vector<int> result;
        while (!s.empty()) {
            result.push_back(s.top());
            s.pop();
        }   
        reverse(result.begin(), result.end());
        return result;
    }
};
int main() {
    Solution solution;
    vector<int> asteroids = {5, 10, -5};
    cout << "asteroids: " << strJoin(asteroids, " ") << endl;
    cout << "asteroidCollision: " << strJoin(solution.asteroidCollision(asteroids), " ") << endl;
    return 0;
}