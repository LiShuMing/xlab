package org.jlab.jvm.oom;

public class GCRootExample {
    private static Object staticObj;  // 静态字段，属于 GC Roots
    private Object instanceObj;       // 非静态字段，不是 GC Roots

    public static void main(String[] args) {
        GCRootExample example = new GCRootExample();
        example.instanceObj = new Object(); // 可达
        staticObj = new Object();          // 可达
    }
}