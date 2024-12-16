package org.jlab.jvm;

import org.junit.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Random;

public class JDKCollectionTest {
    @Test
    public void testCollections1() {
        {
            List<Integer> l = new ArrayList<>();
            Collections.sort(l);
            Collections.shuffle(l, new Random());

        }
        {

            List<Integer> l1 = new ArrayList<>();
            List<Integer> l2 = new ArrayList<>();
            if (Collections.disjoint(l1, l2)) {
                System.out.println("disjoint");
            }
        }
    }

    @Test
    public void testArrays() {
        {
            String[] s1 = new String[] { "a", "b", "c" };
            String[] s2 = Arrays.copyOf(s1, 2);
            System.out.println(Arrays.toString(s2));
        }
        {
            long[] ls = new long[10];
            Arrays.fill(ls, 10);
            System.out.println(Arrays.toString(ls));
            Arrays.setAll(ls, i -> i * 2);
            Arrays.sort(ls);
            System.out.println(Arrays.toString(ls));
            Arrays.parallelPrefix(ls, (left, right) -> left + right);
            System.out.println(Arrays.toString(ls));
        }
    }
}
