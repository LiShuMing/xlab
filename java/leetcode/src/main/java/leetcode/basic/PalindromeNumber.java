package leetcode.basic;

/**
 * @author : lishuming
 */
public class PalindromeNumber {
    public boolean solution(int a) {
        if (a < 0) {
            return false;
        }
        int reverseA = 0, aa = a;

        for (; aa != 0; aa = aa / 10) {
            reverseA = reverseA * 10 + aa % 10;
        }
        return reverseA == a;
    }
}
