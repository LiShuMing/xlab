package leetcode;

import java.util.HashMap;
import java.util.Map;

/**
 * @author : lishuming
 */
public class Multiply43 {
    public String multiply(String num1, String num2) {
        if (num1 == null || num2 == null) {
            return null;
        }

        int len1 = num1.length();
        int len2 = num2.length();
        int l1 = len1, l2 = len2, l, r, t, up = 0;

        boolean firstTime = true;

        Map<Integer, Integer> ret = new HashMap<>();
        for (int i = len1; i > 0; i--) {
            l = (num1.charAt(i - 1) - '0');

            for (int j = len2; j > 0; j--) {
                r = (num2.charAt(j - 1) - '0');

                //System.out.println("i * j:" + i * j);

                int order = (len1 - i + 1) * (len2 - j + 1);
                System.out.println("order:" + order);
                if (ret.containsKey(order)) {
                    ret.put(order, ret.get(order) + l * r);
                } else {
                    ret.put(order, l * r);
                }
            }
        }

        StringBuilder sb = new StringBuilder();
        for (int i = 1; i <= len1 * len2; i++) {
            System.out.println("i:" + i);
            t = ret.get(i) + up;
            sb.append(t % 10);
            up = t / 10;
        }
        while (up != 0) {
            sb.append(up % 10);
            up = up / 10;
        }
        return sb.reverse().toString();
    }

    public static void main(String[] args) {
        String r = new Multiply43().multiply("111", "10");
        System.out.println(r);
    }
}
