package leetcode;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Stack;

/**
 * @author shuming.lsm
 * @version 2019/12/04
 */
public class _039 {
    public List<List<Integer>> combinationSum(int[] candidates, int target) {
        if (candidates.length == 0) return null;
        List<List<Integer>> r = new ArrayList<>();
        Arrays.sort(candidates);
        helper(r, candidates, 0, target, new Stack<>());
        return r;
    }

    private void helper(List<List<Integer>> r, int[] candidates, int start, int left, Stack<Integer> cur) {
        if (left == 0) {
            r.add(new ArrayList<>(cur));
            return;
        }
        for (int i = start; i < candidates.length; i++) {
            if (left - candidates[i] < 0) {
                continue;
            }
            int v = candidates[i];
            cur.add(v);
            helper(r, candidates, i, left - v, cur);
            cur.pop();
        }
    }

    public static void main(String[] args) {
        int[] cands = {2, 3, 6, 7};
        List<List<Integer>> r = new _039().combinationSum(cands, 7);
        for (List<Integer> l: r) {
            for (Integer ll: l) {
                System.out.println(ll);
            }
            System.out.println("#########");
        }
    }
}
