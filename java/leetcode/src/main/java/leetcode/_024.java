package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/14
 */
public class _024 {
    public ListNode swapPairs(ListNode head) {
        if (head == null || head.next == null) return head;
        ListNode pre = new ListNode(0);
        pre.next = head;
        ListNode tmp = pre;
        while(tmp.next != null && tmp.next.next != null) {
            ListNode s = tmp.next;
            ListNode e = tmp.next.next;

            tmp.next = e;
            s.next = e.next;
            e.next = s;

            tmp = s;
        }
        return pre.next;
    }
}

