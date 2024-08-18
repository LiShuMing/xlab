package leetcode;

/**
 * @author : lishuming
 */
public class IsPalindrome9 {
    public boolean isPalindrome(int x) {
        if (x < 0) {
            return false;
        }

        int y = x;
        int ret = 0;
        while (y != 0) {
            ret = 10 * ret + y % 10;
            y = y / 10;
        }

        return ret == x;
    }

    public static void main(String[] args) {
        boolean ret = new IsPalindrome9().isPalindrome(101);
        System.out.println(ret);
    }
}
