package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/23
 */
public class _014 {
    public String longestCommonPrefix(String[] strs) {
        int min = Integer.MAX_VALUE;
        for (String s: strs) {
            if (s == null) return null;
            min = Math.min(min, s.length());
        }
        if (min == 0) return "";
        if (strs == null || strs.length == 0) return null;

        int i = 0;
        for (int j = 1; j < strs.length; i++) {
            if (strs[j].charAt(i) != strs[0].charAt(i)) {
                break;
            }
        }
        return strs[0].substring(0, i);
    }
}
