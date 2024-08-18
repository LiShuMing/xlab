package leetcode;

import java.util.HashMap;
import java.util.Map;

/**
 * @author : lishuming
 */
public class ContainsNearbyDuplicate219 {
    public static boolean solution(int[] nums, int k) {
        Map<Integer, Integer> map = new HashMap<Integer, Integer>();

        int j = 0;
        for (int i : nums) {
            if (map.containsKey(i)) {
                if (j - map.get(i) <= k) {
                    return true;
                } else {
                    map.put(i, j);
                }
            } else {
                map.put(i, j);
            }
            j++;
        }

        return false;
    }
}
