package leetcode;

/**
 * @author : lishuming
 */
public class ReverseList206 {
    public ListNode reverseList(ListNode head) {
        ListNode pre = null;

        while (head != null) {
            ListNode tmp = head.next;
            head.next = pre;
            pre = head;
            head = tmp;
        }

        return pre;
    }

    public static void main(String[] args) {

    }
}
