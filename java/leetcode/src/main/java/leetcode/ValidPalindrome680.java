package leetcode;

/**
 * @author : lishuming
 */
public class ValidPalindrome680 {
    public boolean validPalindrome(String s) {
        if (s == null || s.isEmpty()) {
            return false;
        }

        int len = s.length();
        int i = 0, j = len - 1;
        boolean hasDeleted = false;
        while (i < j) {
            System.out.println("left:" + s.charAt(i) + ", right:" + s.charAt(j));

            if (s.charAt(i) == s.charAt(j)) {
                i++;
                j--;
                continue;
            }
            if (hasDeleted) {
                return false;
            }

            boolean ret1 = s.charAt(i + 1) == s.charAt(j);
            boolean ret2 = s.charAt(i) == s.charAt(j - 1);

            if (ret1 && !ret2) {
                hasDeleted = true;
                i = i + 1;
            } else if (!ret1 & ret2) {
                hasDeleted = true;
                j = j - 1;
            } else if (ret1 && ret2) {
                if (i + 1 == j) {
                    return true;
                }
                return validPalindrome(s.substring(i + 1, j)) || validPalindrome(s.substring(i, j - 1));
            } else {
                return false;
            }

            i++;
            j--;
        }
        return true;
    }

    public static void main(String[] args) {
        boolean ret = new ValidPalindrome680().validPalindrome(
            "aguokepatgbnvfqmgmlcupuufxoohdfpgjdmysgvhmvffcnqxjjxqncffvmhvgsymdjgpfdhooxfuupuculmgmqfvnbgtapekouga");
        System.out.println(ret);
    }
}
