package leetcode;

import java.util.*;

/**
 * @author shuming.lsm
 * @version 2019/12/21
 */
public class _047 {
//    public List<List<Integer>> permuteUnique(int[] nums) {
//        List<List<Integer>> result = new ArrayList<>();
//        Stack<Integer> s = new Stack<>();
//        Map<List<Integer>, Boolean> m = new HashMap<>();
//        backtrace(result, s, m, 0, nums);
//        return result;
//    }
//
//    private void backtrace(List<List<Integer>> result, Stack<Integer> cur, Map<List<Integer>, Boolean> m, int i, int[] nums) {
//        if (cur.size() == nums.length) {
//            if (!m.containsKey(cur)) {
//                List<Integer> r = new ArrayList<>(cur);
//                m.put(r, true);
//                result.add(r);
//            }
//            return;
//        }
//        for (int j = 0; j < nums.length; j++) {
//            if (i == j) continue;
//            cur.push(nums[j]);
//            backtrace(result, cur, m, j, nums);
//            cur.pop();
//        }
//    }

    public List<List<Integer>> permuteUniqueV2(int[] nums) {
        boolean[] flags = new boolean[nums.length];
        List<List<Integer>> result = new ArrayList<>();
        List<Integer> current = new ArrayList<>();
        Arrays.sort(nums);
        dfs(result, flags, current, nums);
        return result;
    }

    public void dfs(List<List<Integer>> result, boolean[] flags, List<Integer> current, int[] nums) {
        if (current.size() == nums.length) {
            result.add(new ArrayList<>(current));
            return;
        }
        for (int i = 0;i < nums.length; i++) {
            if (flags[i]) continue;
            if (i > 0 && nums[i] == nums[i - 1] && flags[i - 1] == false) continue;

            current.add(nums[i]);
            flags[i] = true;
            dfs(result, flags, current, nums);
            flags[i] = false;
            current.remove(current.size() - 1);
        }
    }

    public static void main(String[] args) {
        int[] nums = {1, 1, 3};
        List<List<Integer>> result = new _047().permuteUniqueV2(nums);
        for (List<Integer> r: result) {
            System.out.println("#########");
            for (Integer i: r) {
                System.out.println(i);
            }
        }
    }
}
