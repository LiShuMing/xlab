package org.jlab.jvm;

import org.junit.Test;

public class TestMyClassLoader {
    @Test
    public void testClassLoader() throws Exception {
        MyClassLoader myClassLoader = new MyClassLoader("/path/to/classes/");
        Class<?> clazz = myClassLoader.loadClass("com.example.MyClass");
        Object obj = clazz.getDeclaredConstructor().newInstance();
        System.out.println(obj.getClass().getClassLoader());
    }
}
