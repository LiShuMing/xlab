package leetcode.string;

/**
 * @author : lishuming
 */
public class MultiString {
    public static String solution(String a, String b) {
        int la = a.length(), lb = b.length(), l = la + lb;

        int[] res = new int[l];
        char[] ca = a.toCharArray();
        char[] cb = b.toCharArray();

        for (int i = la - 1; i >= 0; i--) {
            int c = ca[i] - '0';
            for (int j = lb - 1; j >= 0; j--) {
                res[i + j + 1] += c * (cb[j] - '0');
            }
        }

        for (int i = l - 1; i > 0; i--) {
            if (res[i] > 9) {
                int mod = res[i] / 10;
                res[i] = res[i] % 10;
                res[i - 1] += mod;
            }
        }

        int k = 0;
        while (res[k] == 0) {
            k++;
        }

        StringBuilder sb = new StringBuilder();
        for (int i = k; i < l; i++) {
            sb.append(res[i]);
        }

        return sb.toString();
    }
}
