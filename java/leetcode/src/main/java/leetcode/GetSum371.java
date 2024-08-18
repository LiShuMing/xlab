package leetcode;

/**
 * @author : lishuming
 */
public class GetSum371 {
    public int getSum(int a, int b) {
        if (b <= 0) {
            return a;
        }
        int sum = a ^ b;
        int carry = (a & b) << 1;

        return getSum(sum, carry);
    }

    public static void main(String[] args) {
        System.out.println(Integer.toBinaryString(12));
        System.out.println(Integer.toBinaryString(24));

        int v = new GetSum371().getSum(12, 24);
        System.out.println(v);
    }
}
