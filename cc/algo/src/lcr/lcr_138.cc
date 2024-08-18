#include "../include/fwd.h"

/*
  Implement valid number check (finite state machine with transition table).
  A valid number (simplified) includes: integer, decimal, scientific notation (e/E).
*/
class Solution {
public:
    bool validNumber(string s) {
        int n = s.size();
        int i = 0;
        
        // Skip leading spaces
        while (i < n && s[i] == ' ') i++;
        
        // Optional sign
        if (i < n && (s[i] == '+' || s[i] == '-')) i++;
        
        bool is_numeric = false;
        bool has_dot = false, has_exp = false;
        
        while (i < n) {
            if (isdigit(s[i])) {
                is_numeric = true;
                i++;
            } else if (s[i] == '.') {
                if (has_dot || has_exp) return false; // No more than one dot or after exp
                has_dot = true;
                i++;
            } else if (s[i] == 'e' || s[i] == 'E') {
                if (has_exp || !is_numeric) return false; // Only one e and must follow a number
                has_exp = true;
                is_numeric = false; // Need at least one digit after exp
                i++;
                // exponent sign
                if (i < n && (s[i] == '+' || s[i] == '-')) i++;
            } else if (s[i] == ' ') {
                // Skip trailing spaces, but nothing else may follow
                while (i < n && s[i] == ' ') i++;
                break;
            } else {
                return false;
            }
        }
        
        return is_numeric && i == n;
    }

    bool validNumberByFSM(string s) {
        // Define FSM states
        enum State {
            STATE_START,
            STATE_INT_SIGN,
            STATE_INTEGER,
            STATE_POINT,
            STATE_POINT_WITHOUT_INT,
            STATE_FRACTION,
            STATE_EXP,
            STATE_EXP_SIGN,
            STATE_EXP_NUMBER,
            STATE_END_SPACE,
            STATE_INVALID
        };
        // Define types of input characters
        enum CharType {
            CHAR_SPACE,
            CHAR_SIGN,
            CHAR_DIGIT,
            CHAR_POINT,
            CHAR_EXP,
            CHAR_ILLEGAL
        };

        // Map a character to its character type
        auto toCharType = [](char ch) -> CharType {
            if (ch == ' ') return CHAR_SPACE;
            else if (ch == '+' || ch == '-') return CHAR_SIGN;
            else if (ch >= '0' && ch <= '9') return CHAR_DIGIT;
            else if (ch == '.') return CHAR_POINT;
            else if (ch == 'e' || ch == 'E') return CHAR_EXP;
            else return CHAR_ILLEGAL;
        };

        // State transition table: current state x input type --> next state
        map<State, map<CharType, State>> transfer {
            {STATE_START, {
                {CHAR_SPACE, STATE_START},
                {CHAR_SIGN, STATE_INT_SIGN},
                {CHAR_DIGIT, STATE_INTEGER},
                {CHAR_POINT, STATE_POINT_WITHOUT_INT}
            }},
            {STATE_INT_SIGN, {
                {CHAR_DIGIT, STATE_INTEGER},
                {CHAR_POINT, STATE_POINT_WITHOUT_INT}
            }},
            {STATE_INTEGER, {
                {CHAR_DIGIT, STATE_INTEGER},
                {CHAR_POINT, STATE_POINT},
                {CHAR_EXP, STATE_EXP},
                {CHAR_SPACE, STATE_END_SPACE}
            }},
            {STATE_POINT, {
                {CHAR_DIGIT, STATE_FRACTION},
                {CHAR_EXP, STATE_EXP},
                {CHAR_SPACE, STATE_END_SPACE}
            }},
            {STATE_POINT_WITHOUT_INT, {
                {CHAR_DIGIT, STATE_FRACTION}
            }},
            {STATE_FRACTION, {
                {CHAR_DIGIT, STATE_FRACTION},
                {CHAR_EXP, STATE_EXP},
                {CHAR_SPACE, STATE_END_SPACE}
            }},
            {STATE_EXP, {
                {CHAR_SIGN, STATE_EXP_SIGN},
                {CHAR_DIGIT, STATE_EXP_NUMBER}
            }},
            {STATE_EXP_SIGN, {
                {CHAR_DIGIT, STATE_EXP_NUMBER}
            }},
            {STATE_EXP_NUMBER, {
                {CHAR_DIGIT, STATE_EXP_NUMBER},
                {CHAR_SPACE, STATE_END_SPACE}
            }},
            {STATE_END_SPACE, {
                {CHAR_SPACE, STATE_END_SPACE}
            }}
        };

        State state = STATE_START;
        for (int i = 0; i < s.size(); ++i) {
            CharType type = toCharType(s[i]);
            if (transfer[state].count(type)) {
                state = transfer[state][type];
            } else {
                return false;
            }
        }

        // Check if the final state is one of the valid ending states
        return state == STATE_INTEGER ||
               state == STATE_POINT ||
               state == STATE_FRACTION ||
               state == STATE_EXP_NUMBER ||
               state == STATE_END_SPACE;
    }
};

int main() {
    Solution solution;
    vector<string> tests{
        "0", " 0.1 ", "abc", "1 a", "2e10", " -90e3   ", " 1e", "e3", "6e-1",
        "99e2.5", "53.5e93", "--6", "-+3", "95a54e53", "3.", ".1", ".", ".e1",
        "e3", "1 "
    };
    for (const auto& s : tests) {
        cout << "\"" << s << "\": " << solution.validNumber(s) << endl;
    }
    return 0;
}