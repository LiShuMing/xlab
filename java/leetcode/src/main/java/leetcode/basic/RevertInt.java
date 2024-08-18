package leetcode.basic;

/**
 * @author : lishuming
 */
public class RevertInt {
    public int revert(int x) {
        int result = 0;
        for (; x != 0; x = x / 10) {
            result = result * 10 + x % 10;
        }
        return (result > Integer.MAX_VALUE || result < Integer.MIN_VALUE) ? 0 : result;
    }
}
