package org.example;

public class HelloWorld {
    public static void main(String[] args) {
        int a = 10, b = 10;
        int c = b;
        b = a;
        int d = 20;
        int e = 30;
        float f = 40;
        double g = 50;
        C1 c1 = new C1(1, "2");
        c1.setC(3);
        a = c1.getA();
        String bb = c1.getB();
        // test2
        System.out.println("a=" + a + ", b=" + b + ", c=" + c);
        System.out.println("Hello, World!");
    }
}
