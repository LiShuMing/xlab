package org.xlab.jlib.memory;//package com.cclab.memory;
//
//import sun.misc.Unsafe;
//
///**
// * @author shuming.lsm
// * @version 2018/08/16
// */
//public class DirectMemomery {
//
//  public static void offHeap(int maximum) throws Exception {
//    Unsafe unsafe = Platform.getUnsafe();
//
//    long size = maximum * 8;
//    long address = unsafe.allocateMemory(size); // 申请内存
//    System.out.println(address);
//
//    unsafe.setMemory(address, size, (byte) -1);// 设置内存
//    System.out.println(unsafe.getByte(address)); // 根据地址获取数据
//    for (int i = 0; i < size; i++) {
//      unsafe.putByte(address + i, (byte) i);
//    }
//    unsafe.freeMemory(address);
//  }
//
//  public static void onHeap(int maximum) {
//    byte[] array = new byte[maximum];
//    for (int i = 0; i < maximum; i++) {
//      array[i] = (byte)i;
//    }
//  }
//
//  public static void main(String[] args) throws Exception {
//    int maximum = 40 * 1024 * 1024;
//
//    int j = 0;
//    while (j < 10000000) {
//      System.out.println(j);
//      // onHeap(maximum);
//      offHeap(maximum);
//      j++;
//    }
//  }
//}
