package leetcode;

/**
 * @author : lishuming
 */
public class AddTwoNumbers2 {
    public ListNode addTwoNumbers(ListNode l1, ListNode l2) {
        ListNode root = null;
        ListNode head = null;
        int v1, v2, t = 0, isAdd = 0;
        while (l1 != null || l2 != null) {
            if (l1 == null) {
                v1 = 0;
            } else {
                v1 = l1.val;
                l1 = l1.next;
            }
            if (l2 == null) {
                v2 = 0;
            } else {
                v2 = l2.val;
                l2 = l2.next;
            }

            t = v1 + v2 + isAdd;
            if (t >= 10) {
                isAdd = 1;
            } else {
                isAdd = 0;
            }

            ListNode node = new ListNode(t % 10);

            if (head == null) {
                root = node;
                head = node;
            } else {
                root.next = node;
                root = root.next;
            }
        }
        if (isAdd == 1) {
            root.next = new ListNode(1);
        }

        return head;
    }

    public static void main(String[] args) {
        ListNode node = new ListNode(2);
        node.next = new ListNode(4);
        node.next.next = new ListNode(3);

        ListNode node2 = new ListNode(5);
        node2.next = new ListNode(6);
        node2.next.next = new ListNode(4);

        ListNode l = new AddTwoNumbers2().addTwoNumbers(node, node2);
        while (l != null) {
            System.out.println(l.val);
            l = l.next;
        }
    }
}
