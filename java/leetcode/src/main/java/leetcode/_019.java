package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/14
 */
public class _019 {
    public ListNode removeNthFromEnd(ListNode head, int n) {
        if (head == null) return null;
        ListNode p = head, q = head, r = head;
        int i = n;
        while (p != null && i > 0) {
            p = p.next;
            i--;
        }
        if (i != 0) {
            return null;
        }
        if (p == null) {
            return q.next;
        }
        p = p.next;
        while (p != null) {
            p = p.next;
            q = q.next;
        }
        q.next = q.next.next;

        return r;
    }
}
