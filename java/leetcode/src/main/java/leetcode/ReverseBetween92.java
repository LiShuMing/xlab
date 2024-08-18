package leetcode;

/**
 * @author : lishuming
 */
public class ReverseBetween92 {
    public ListNode reverseBetween(ListNode head, int m, int n) {
        if (head == null) {
            return null;
        }

        ListNode p = head, q = head;

        while (m - 1 > 0 && p != null) {
            p = p.next;
            m--;
        }

        if (m > 0 && p == null) {
            return head;
        }
        return null;
    }

    public static void main(String[] args) {

    }
}
