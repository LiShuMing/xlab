package leetcode.string;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * @author : lishuming
 */
public class LetterCombine {
    private static String[] map = new String[] {"abc", "def", "ghi", "jkl", "mno", "pqrs", "tuv", "wxyz"};

    public List<String> solution(String letter) {
        if (letter.length() == 0) { return Collections.emptyList(); }
        List<String> result = new ArrayList<>();
        helper(result, letter, "");
        return result;
    }

    public void helper(List<String> result, String letter, String ans) {
        if (ans.length() == letter.length()) {
            result.add(ans);
            return;
        }
        for (char c : map[letter.charAt(ans.length()) - '0'].toCharArray()) {
            helper(result, letter, ans + c);
        }
    }
}
