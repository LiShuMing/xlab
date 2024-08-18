package leetcode;

/**
 * @author : lishuming
 */

public class GetMinimumDifference530 {
    private int min = Integer.MAX_VALUE;
    private TreeNode pre = null;

    public int getMinimumDifference(TreeNode root) {
        if (root.left != null) {
            getMinimumDifference(root.left);
        }

        if (pre != null) {
            min = Math.min(min, root.val - pre.val);
        }
        pre = root;

        if (root.right != null) {
            getMinimumDifference(root.right);
        }

        return min;
    }
}
