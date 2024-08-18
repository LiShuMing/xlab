package leetcode;

import java.util.HashMap;
import java.util.Map;

/**
 * @author : lishuming
 */
public class IsHappy202 {
    public Map<Integer, Boolean> map = new HashMap<Integer, Boolean>();

    public boolean isHappy(int n) {
        if (n == 1) {
            return true;
        }

        int ret = 0;
        while (n / 10 != 0) {
            int t = n % 10;
            ret += t * t;

            n = n / 10;
        }
        ret += n * n;

        if (map.containsKey(ret)) {
            return false;
        }
        map.put(ret, true);

        return isHappy(ret);
    }

    public static void main(String[] args) {
        boolean ret = new IsHappy202().isHappy(9);
        System.out.println(ret);
    }
}
