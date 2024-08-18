package leetcode.string;

/**
 * @author : lishuming
 */
public class StringMatch {
    public static boolean solution(String s, String p) {
        if (s.isEmpty()) {
            return p.isEmpty();
        }

        if (p.length() == 1) {
            return s.length() == 1 && (p.charAt(0) == s.charAt(0) || p.charAt(0) == '.');
        }

        if (p.charAt(1) != '*') {
            if (s.isEmpty()) {
                return false;
            }

            return (p.charAt(0) == '.' || s.charAt(0) == p.charAt(0)) && solution(s.substring(1), p.substring(1));
        }
        return false;
    }
}
