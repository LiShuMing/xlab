package leetcode;

/**
 * @author : lishuming
 */
public class IsPalindrome234 {
    public boolean isPalindrome(ListNode head) {
        if (head == null) {
            return true;
        }

        int len = 0;
        ListNode lNode = head;
        while (lNode != null) {
            len += 1;
            lNode = lNode.next;
        }

        int mid = len / 2, j = mid;
        int i = len % 2 == 0 ? mid : mid + 1;
        ListNode p1 = head, p2 = head, pre = null;

        while (i-- > 0) {
            p2 = p2.next;
        }

        while (j-- > 0) {
            if (j == 0) {
                p1.next = pre;
                break;
            }
            ListNode t = p1.next;
            p1.next = pre;
            pre = p1;
            p1 = t;
        }

        while (p1 != null && p2 != null) {
            if (p1.val != p2.val) {
                return false;
            }
            p1 = p1.next;
            p2 = p2.next;
        }

        return true;
    }

    public static void main(String[] args) {
        ListNode node1 = new ListNode(1);
        node1.next = new ListNode(0);
        //node1.next.next = new ListNode(1);
        //node1.next.next.next = new ListNode(1);

        boolean ret = new IsPalindrome234().isPalindrome(node1);
        System.out.println(ret);
    }
}
