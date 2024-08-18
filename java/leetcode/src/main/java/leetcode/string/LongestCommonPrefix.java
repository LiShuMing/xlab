package leetcode.string;

/**
 * @author : lishuming
 */
public class LongestCommonPrefix {
    public String solution(String[] strs) {
        if (strs == null || strs.length == 0) {
            return "";
        }
        int minLenth = Integer.MAX_VALUE;
        for (int i = 0; i < strs.length; i++) {
            minLenth = Math.min(strs[i].length(), minLenth);
        }
        if (minLenth == 0) {
            return "";
        }

        int result = 0;
        for (; result < minLenth; result++) {
            for (int j = 1; j < strs.length; j++) {
                if (strs[j].charAt(result) != strs[0].charAt(result)) {
                    return strs[0].substring(0, result);
                }
            }
        }
        return strs[0].substring(0, result);
    }
}
