package leetcode;

import java.util.ArrayList;
import java.util.List;
import java.util.Stack;

/**
 * @author shuming.lsm
 * @version 2019/12/21
 */
public class _046 {
    public List<List<Integer>> permute(int[] nums) {
        List<List<Integer>> result = new ArrayList<>();
        Stack<Integer> s = new Stack<>();
        backtrace(result, s, nums);
        return result;
    }

    private void backtrace(List<List<Integer>> result, Stack<Integer> cur, int[] nums) {
        if (cur != null && cur.size() == nums.length) {
            result.add(new ArrayList<>(cur));
            return;
        }
        for (int i = 0;i < nums.length; i++) {
            if (cur.contains(nums[i])) continue;
            cur.push(nums[i]);
            backtrace(result, cur, nums);
            if (!cur.isEmpty()) cur.pop();
        }
    }

    public static void main(String[] args) {
        int[] nums = {1, 2, 3};
        List<List<Integer>> result = new _046().permute(nums);
        for (List<Integer> r: result) {
            System.out.println("#########");
            for (Integer i: r) {
                System.out.println(i);
            }
        }
    }
}
