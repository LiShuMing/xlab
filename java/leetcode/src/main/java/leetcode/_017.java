package leetcode;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * @author shuming.lsm
 * @version 2019/12/14
 */
public class _017 {
    private final Map<Character, String> mapping = new HashMap<>();
    public List<String> letterCombinations(String digits) {
        List<String> ret = new ArrayList<>();
        if (digits == null || digits.length() == 0) return ret;
        mapping.put('2', "abc");
        mapping.put('3', "def");
        mapping.put('4', "ghi");
        mapping.put('5', "jkl");
        mapping.put('6', "mno");
        mapping.put('7', "pqrs");
        mapping.put('8', "tuv");
        mapping.put('9', "wxyz");

        List<Character> chars = new ArrayList<>();
        for (char c: digits.toCharArray()) {
            chars.add(c);
        }
        backtrace(ret, "", chars);
        return ret;
    }

    private void backtrace(List<String> r, String cur, List<Character> rest) {
        if (rest == null || rest.size() == 0) {
            r.add(cur);
            return;
        }

        Character curChar = rest.get(0);
        List<Character> restV2 = null;
        if (rest.size() > 1) {
            restV2 = rest.subList(1, rest.size());
        }
        for (Character c: mapping.get(curChar).toCharArray()) {
            cur = cur + c;
            backtrace(r, cur, restV2);
            cur = cur.substring(0, cur.length() - 1);
        }
    }

    public static void main(String[] args) {
        List<String> ret = new _017().letterCombinations("");
        for (String r: ret) {
            System.out.println(r);
        }
    }
}
