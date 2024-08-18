package com.cclab.util;

/**
 * @author shuming.lsm
 * @version 2018/07/04
 */
public class BitPack {

    public static void main(String[] args) {
        Integer i = 11;

        System.out.println(Integer.toBinaryString(i));
        System.out.println(Integer.toBinaryString(i<<1));
        System.out.print(b(1,3));
    }

    private static String b(int i, int size) {
        String binaryString = Integer.toBinaryString(i);
        while (binaryString.length() < size) {
            binaryString = "0" + binaryString;
        }
        return binaryString;
    }
}
