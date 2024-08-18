package leetcode;

import java.util.Stack;

/**
 * @author shuming.lsm
 * @version 2019/12/14
 */
public class _844 {
    public boolean backspaceCompare(String S, String T) {
        if (S == null && T == null) return true;
        if (S == null || T == null) return false;

        int l1 = S.length(), l2 = T.length();

        while (l1 > 0 && l2 > 0) {
            while (S.charAt(l1 - 1) == '#' && l1 > 0) l1 -= 2;
            while (T.charAt(l2 - 1) == '#' && l2 > 0) l2 -= 2;
            if (S.charAt(l1--) != T.charAt(l2--)) {
                return false;
            }
        }
        if (l1 >0 || l2 > 0) {
            return false;
        }
        return true;
    }
    public boolean backspaceCompareV2(String S, String T) {
        if (S == null && T == null) return true;
        if (S == null || T == null) return false;

        Stack<Character> s1 = new Stack<>(), s2 = new Stack<>();
        for (char c: S.toCharArray()) {
            if (c == '#') {
                if (!s1.isEmpty()) {
                    s1.pop();
                }
            } else {
                s1.push(c);
            }
        }
        for (char c: T.toCharArray()) {
            if (c == '#') {
                if (!s2.isEmpty()) {
                    s2.pop();
                }
            } else {
                s2.push(c);
            }
        }
        while (!s1.isEmpty() && !s2.isEmpty()) {
            if (s1.pop() != s2.pop()) {
                return false;
            }
        }
        if (s1.isEmpty() && s2.isEmpty()) {
            return true;
        }
        return false;
    }

    public static void main(String[] args) {
        boolean r = new _844().backspaceCompareV2("y#fo##f", "y#f#o##f");
        System.out.println(r);
    }
}
