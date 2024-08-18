package leetcode;

/**
 * @author : lishuming
 */
public class CountPrimes204 {
    public int countPrimes(int n) {
        int ret = 0;

        for (int i = 1; i < n; i++) {
            if (isPrime(i)) {
                ret++;
            }
        }

        return ret;
    }

    public int countPrimesV2(int n) {
        if (n <= 0) {
            return 0;
        }

        int[] m = new int[n - 1];
        int k;

        for (int i = 2; i < n; i++) {
            for (int j = 2; (k = i * j) < n; j++) {
                m[k - 1] = 1;
            }
        }

        int ret = 0;
        for (int i = 1; i < n - 1; i++) {
            if (m[i] == 0) {
                ret++;
            }
        }

        return ret;
    }

    public boolean isPrime(int a) {
        if (a <= 1) {
            return false;
        }
        if (a <= 2) {
            return true;
        }

        int tmp = (int)Math.sqrt(a);
        for (int i = 2; i <= tmp; i++) {
            if (a % i == 0) {
                return false;
            }
        }

        return true;
    }

    public static void main(String[] args) {
        System.out.println(new CountPrimes204().countPrimesV2(10));
    }
}
