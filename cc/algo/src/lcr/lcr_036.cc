#include "../include/fwd.h"

class Solution {
    public:
        int evalRPN(vector<string>& tokens) {
            stack<int> st;
            for (const auto& token : tokens) {
                int op = getOperator(token);
                if (op == 0) {
                    st.push(stoi(token));
                } else {
                    int b = st.top();
                    st.pop();
                    int a = st.top();
                    st.pop();
                    switch (op) {
                        case 1:
                            st.push(a + b);
                            break;
                        case 2:
                            st.push(a - b);
                            break;
                        case 3:
                            st.push(a * b);
                            break;
                        case 4:
                            st.push(a / b);
                            break;
                        default:
                            break;
                    }
                }
            }
            return st.top();
        }
        int getOperator(const string& token) {
            if (token == "+") return 1;
            if (token == "-") return 2;
            if (token == "*") return 3;
            if (token == "/") return 4;
            return 0;
        }
};

int main() {
    Solution solution;
    vector<string> tokens = {"2", "1", "+", "3", "*"};
    cout << "tokens: ";
    printVector(tokens);
    cout << "evalRPN: ";
    cout << solution.evalRPN(tokens) << endl;
    return 0;
}