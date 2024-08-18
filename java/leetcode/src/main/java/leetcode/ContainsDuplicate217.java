package leetcode;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * @author : lishuming
 */
public class ContainsDuplicate217 {
    public static boolean solution(int[] nums) {
        Map<Integer, Boolean> map = new HashMap<Integer, Boolean>();
        for (int i : nums) {
            if (map.containsKey(i)) {
                return true;
            } else {
                map.put(i, true);
            }
        }
        return false;
    }

    /**
     * bad!!!
     *
     * @param nums
     * @return
     */
    public static boolean solutionV1(int[] nums) {
        List<Integer> list = new ArrayList<Integer>();
        for (int i : nums) {
            if (list.contains(i)) {
                return true;
            } else {
                list.add(i);
            }
        }
        return false;
    }
}
