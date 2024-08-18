package leetcode.string;

/**
 * @author : lishuming
 */
public class ValidPaindrome {
    public boolean solution(String s) {
        char[] stack = new char[s.length() + 1];
        int top = 1;

        for (char c : s.toCharArray()) {
            if (c == '[' || c == '{' || c == '(') {
                stack[top++] = c;
            } else if (c == ']' && stack[--top] != '[') {
                return false;
            } else if (c == '}' && stack[--top] != '{') {
                return false;
            } else if (c == ')' && stack[--top] != '(') {
                return false;
            }
        }
        return true;
    }
}
