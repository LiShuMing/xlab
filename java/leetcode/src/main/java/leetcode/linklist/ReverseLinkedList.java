package leetcode.linklist;

/**
 * @author : lishuming
 */
public class ReverseLinkedList {
    public LinkedNode reverse(LinkedNode node) {
        if (node == null) {
            return node;
        }

        LinkedNode next = node.next;
        while (next != null) {
            next = node.next.next;
            LinkedNode tmp = next.next;
            tmp.next = node;
        }
        return next;
    }

    public static void main(String[] args) {

    }
}
