package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/02
 */
public class _002 {
    public ListNode addTwoNumbers(ListNode l1, ListNode l2) {
        ListNode r = new ListNode(0);
        ListNode head = r, n = null;
        int v = 0, m = 0, s = 0;
        while (l1 != null || l2 != null) {
            // reinit value;
            s = 0;
            if (l1 != null) {
                s += l1.val;
                l1 = l1.next;
            }
            if (l2 != null) {
                s += l2.val;
                l2 = l2.next;
            }
            s += m;
            v = s % 10;
            m = s / 10;
            n = new ListNode(v);
            r.next = n;
            r = r.next;
        }
        if (m != 0) {
            n = new ListNode(m);
            r.next = n;
        }
        return head.next;
    }
}
