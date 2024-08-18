package leetcode.string;

/**
 * @author : lishuming
 */
public class StrStr {
    public static int solution(String str, String needle) {
        int l1 = str.length(), l2 = needle.length();

        if (l1 < l2) {
            return -1;
        }

        for (int i = 0; i < l1; i++) {
            if (i + l2 > l1) { return -1; }

            for (int j = 0; ; j++) {
                if (j == l2) { return i; }
                if (str.charAt(i++) != needle.charAt(j++)) {
                    break;
                }
            }
        }

        return -1;
    }
}
