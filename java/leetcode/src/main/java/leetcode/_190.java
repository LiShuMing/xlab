package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/03
 */
public class _190 {
    public int reverseBits2(int n) {
        int res = 0;
        for (int i = 0; i < 32; i++) {
            res = res << 1;
            res |= n &1;
            n = n >> 1;
        }
        return res;
    }

    public int reverseBits(int n) {
        int res = 0, cur = 0;
        for (int i = 0; i < 32; i++) {
            cur = n & 1;
            n >>= 1;
            if (cur != 0) {
                res += cur << (31 - i);
            }
        }
        return res;
    }
    public static void main(String[] args) {
        System.out.println(new _190().reverseBits(8));
        System.out.println(new _190().reverseBits2(8));
        System.out.println(Integer.toBinaryString(8));
        System.out.println(Integer.toBinaryString(-8));
    }
}
