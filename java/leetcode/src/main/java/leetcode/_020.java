package leetcode;

import java.util.HashMap;
import java.util.Map;
import java.util.Stack;

/**
 * @author shuming.lsm
 * @version 2019/12/03
 */
public class _020 {
    public boolean isValid(String s) {
        Map<Character, Character> map = new HashMap<>();
        map.put('{', '}');
        map.put('[', ']');
        map.put('(', ')');
        Stack<Character> stack = new Stack<>();
        int i = 0, len = s.length();
        char c, t;
        while (i < len) {
            c = s.charAt(i);
//            System.out.println(c);
            if (map.containsKey(c)) {
                stack.push(c);
            } else {
                if (stack.isEmpty()) {
                    return false;
                }
                t = stack.pop();
                if (c != map.get(t)) {
                    return false;
                }
            }
            i++;
        }
        return true && stack.isEmpty();
    }

    public static void main(String[] args) {
        boolean r = new _020().isValid("()[]{}");
        System.out.println(r);
    }
}
