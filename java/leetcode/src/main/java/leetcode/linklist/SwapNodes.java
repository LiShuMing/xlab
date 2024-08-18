package leetcode.linklist;

/**
 * @author : lishuming
 */

// TODO:
public class SwapNodes {
    public static LinkedNode solution(LinkedNode root) {
        if (root == null || root.next == null) {
            return root;
        }

        LinkedNode node = root.next;
        root.next = solution(root.next);
        node.next = root;

        return node;
    }

    public static LinkedNode solution2(LinkedNode root) {
        LinkedNode nextHead = root.next;
        while (root != null && root.next != null) {
            LinkedNode tmpNode = root.next.next;

            root.next.next = root;
            root.next = tmpNode;

            root = tmpNode;
        }
        return nextHead;
    }
}
