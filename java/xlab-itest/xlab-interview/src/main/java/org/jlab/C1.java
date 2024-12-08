package org.jlab;

public class C1 {
    private final int a;
    private final String b;
    private int c = 0;
    public C1(int a, String b) {
        this.a = a;
        this.b = b;
    }

    public int getA() {
        return a;
    }

    public String getB() {
        return b;
    }

    public int getC() {
        return c;
    }

    public void setC(int c) {
        this.c = c;
    }
}
