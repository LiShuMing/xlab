package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/03
 */
public class _009 {
    public boolean isPalindrome(int x) {
        if (x < 0) return false;
        int res = 0, mod = 0, old = x;
        while (x != 0) {
            mod = x % 10;
            x = x / 10;
            res = res * 10 + mod;
        }
        return res == old;
    }

    public static void main(String[] args) {
        boolean r = new _009().isPalindrome(121);
        System.out.println(r);
    }
}
