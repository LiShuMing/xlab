package leetcode.string;

import java.util.ArrayList;
import java.util.List;

/**
 * @author : lishuming
 */
public class GenParentness {
    public List<String> solution(int n) {
        List<String> list = new ArrayList<>();
        helper(list, "", 0, n);
        return list;
    }

    public void helper(List<String> list, String s, int leftRest, int rightNeed) {
        if (leftRest == 0 && rightNeed == 0) {
            list.add(s);
            return;
        }
        if (leftRest > 0) { helper(list, s + "(", leftRest - 1, rightNeed + 1); }
        if (rightNeed > 0) { helper(list, s + ")", leftRest, rightNeed - 1); }
    }
}
