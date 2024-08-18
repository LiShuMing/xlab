package leetcode;

import java.util.HashSet;
import java.util.Set;

/**
 * @author shuming.lsm
 * @version 2019/12/03
 */
public class _003 {
    public int lengthOfLongestSubstring(String s) {
        if (s == null || s.isEmpty()) return 0;

        Set<Character> chars = new HashSet<>();
        int i = 0, j = 0, n = s.length(), ans = 0;
        while (i < n && j < n) {
            if (!chars.contains(s.charAt(j))) {
                chars.add(s.charAt(j++));
                ans = Math.max(j - i, ans);
            } else {
                chars.remove(s.charAt(i++));
            }
        }
        return ans;
    }
    static public void main(String[] args) {
        int r = new _003().lengthOfLongestSubstring("abcabcbb");
        System.out.println(r);
    }
}
