package leetcode;

import leetcode.linklist.LinkedNode;
import leetcode.string.MultiString;

/**
 * @author : lishuming
 */
public class Solution {
    public static void main(String[] args) {
        //System.out.println(new RevertInt().revert(123));
        //System.out.println(new Atoi().solution("-123"));
        //System.out.println(new PalindromeNumber().solution(12321));

        int[] height = new int[] {1, 2, 3, 4};
        //System.out.println(new ContainerWithWater().soluction(height));

        //System.out.println(new Int2Roman().solution(87));
        //System.out.println(new Roman2Int().solution("LXXXVII"));
        //System.out.println(new LongestCommonPrefix().solution(new String[]{"abcxyz", "abcxb", "abcx123"}));
        //System.out.println(new Sum3Closest().solution(new int[]{-1, 2, 1, -4}, 1));
        //System.out.println(new LetterCombine().solution("23"));

        LinkedNode node1 = new LinkedNode(1);
        LinkedNode node2 = new LinkedNode(2);
        LinkedNode node3 = new LinkedNode(3);
        LinkedNode node4 = new LinkedNode(4);
        node1.next = node2;
        node2.next = node3;
        node3.next = node4;
        //System.out.println(node1);
        //System.out.println(new RemoveNode().solution(node1, 2));
        //System.out.println(new RemoveNode().solution(node1, 1));

        //System.out.println(new ValidPaindrome().solution("{}{}[()]"));
        //System.out.println(new GenParentness().solution(2));

        //LinkedNode node = SwapNodes.solution(node1);
        LinkedNode tnode = node1;
        /**
         while (node1 != null) {
         System.out.println(node1.getVal() + " ");
         node1 = node1.next;
         }

         LinkedNode node = SwapNodes.solution2(tnode);
         while (node != null) {
         System.out.println(node.getVal() + " ");
         node = node.next;
         }*/

        int[] t = {2, 3, 3, 5};
        //System.out.println(RemoveDuplicate.solution(t));
        //System.out.println(RemoveElement.solution(t, 3));
        //printArray(t);

        //System.out.println(StrStr.solution("abcdb", "cd"));

        //System.out.println(DivideTwoNumber.solution(22, 3));
        //System.out.println(SearchInsert.solution(t, 4));
        System.out.println(MultiString.solution("123", "123"));
    }

    private static void printArray(int[] t) {
        for (int i = 0; i < t.length; i++) {
            System.out.println(t[i]);
        }
    }
}
