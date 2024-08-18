package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/03
 */
public class _125 {
    public boolean isPalindrome(String s) {
        if (s == null || s.isEmpty()) return true;
        int len = s.length(), p = 0, q = len - 1;
        while (p < q) {
            while (!isCharOrDigital(s.charAt(p)) && p < q) p++;
            while (!isCharOrDigital(s.charAt(q)) && p < q) q--;
            if (p >= q) {
                return true;
            }
            if (!isSameChar(s.charAt(p++), s.charAt(q--))) {
                return false;
            }
        }
        return true;
    }
    private boolean isCharOrDigital(char a) {
       if (isChar(a) || isDigital(a)) {
           return true;
       }
       return false;
    }
    private boolean isChar(char a) {
        if ((a >= 'a' && a <= 'z') || (a >= 'A' && a <= 'Z')) {
            return true;
        }
        return false;
    }
    private boolean isDigital(char a) {
        if (a >= '0' && a <= '9') {
            return true;
        }
        return false;
    }
    private boolean isSameChar(char a, char b) {
        int t = Math.abs(a - b);
        if (isChar(a) && isChar(b) && (t == 0 || t == ('a' - 'A'))) {
            return true;
        }
        if (isDigital(a) && isDigital(b) && t == 0)  {
           return true;
        }
        return false;
    }
    public static void main(String[] args) {
        boolean r = new _125().isPalindrome( "A man, a plan, a canal: Panama");
//        boolean r = new _125().isPalindrome( ".,");
        System.out.println(r);
    }
}
