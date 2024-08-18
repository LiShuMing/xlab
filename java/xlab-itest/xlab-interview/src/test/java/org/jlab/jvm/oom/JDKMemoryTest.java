package org.jlab.jvm.oom;

import net.sf.cglib.proxy.Enhancer;
import net.sf.cglib.proxy.MethodInterceptor;
import org.junit.Test;

public class JDKMemoryTest {
    @Test
    public void testMetaMemory() {
        while (true) {
            Enhancer enhancer = new Enhancer();
            enhancer.setSuperclass(MetaMemoryOOM.class);
            enhancer.setUseCache(false);
            enhancer.setCallback((MethodInterceptor) (obj, method, args1, proxy) -> proxy.invokeSuper(obj, args1));
            enhancer.create(); // 动态生成类，导致元空间膨胀
        }
    }

    @Test
    public void testRecycleGC() {
        class Node {
            Node next;
        }
        Node a = new Node();
        Node b = new Node();
        a.next = b;
        b.next = a;
        // recycle GC
    }

    @Test
    public void testGCRoot() {
        class C {}
        class B {
            C c;
        }
        class A {
            B b;
        }
        A a = new A();
        a.b = new B();
        a.b.c = new C();
    }
}
