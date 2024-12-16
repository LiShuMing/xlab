package org.jlab.jvm.oom;

public class FinalizeExample {
    private static FinalizeExample instance;

    @Override
    protected void finalize() throws Throwable {
        System.out.println("finalize() called");
        instance = this; // 对象“自救”
        System.out.println(instance != null ? "Resurrected" : "Collected");
    }

    public static void main(String[] args) {
        instance = new FinalizeExample();
        instance = null; // 不可达
//        System.out.println(instance != null ? "Resurrected" : "Collected");
        System.gc();     // 第一次 GC，调用 finalize()
        System.out.println(instance != null ? "Resurrected" : "Collected");

        // System.out.println(instance != null ? "Resurrected" : "Collected");
        instance = null; // 再次不可达
        System.gc();     // 第二次 GC，无法再自救
        System.out.println(instance != null ? "Resurrected" : "Collected");
    }
}