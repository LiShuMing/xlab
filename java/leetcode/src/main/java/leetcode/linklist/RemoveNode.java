package leetcode.linklist;

/**
 * @author : lishuming
 */
public class RemoveNode {
    public LinkedNode solution(LinkedNode head, int n) {
        if (n <= 0 || head == null) {
            return head;
        }

        LinkedNode r = head, l = null;

        while (r.next != null) {
            System.out.println(r.getVal());
            r = r.next;

            if (n-- == 0) {
                l = head;
            }
            if (l != null) {
                l = l.next;
            }
        }

        // delete l.next
        l.next = l.next.next;

        return head;
    }
}
