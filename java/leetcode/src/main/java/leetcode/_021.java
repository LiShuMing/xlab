package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/02
 */
public class _021 {
    public ListNode mergeTwoLists(ListNode l1, ListNode l2) {
        int l, r, target;
        ListNode node = new ListNode(0);
        ListNode head = node;
        while (l1 != null || l2 != null) {

            if (l1 != null && l2 != null) {
                l = l1.val;
                r = l2.val;
                if (l < r) {
                    target = l;
                    l1 = l1.next;
                } else {
                    target = r;
                    l2 = l2.next;
                }
            } else {
                if (l1 != null) {
                    target = l1.val;
                    l1 = l1.next;
                } else {
                    target = l2.val;
                    l2 = l2.next;
                }
            }
            ListNode n = new ListNode(target);
            node.next = n;
            node = node.next;
        }
        return  head.next;
    }
}
