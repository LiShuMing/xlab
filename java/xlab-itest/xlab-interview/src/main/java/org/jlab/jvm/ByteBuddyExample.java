package org.jlab.jvm;
import net.bytebuddy.ByteBuddy;
import net.bytebuddy.dynamic.loading.ClassLoadingStrategy;
import net.bytebuddy.implementation.FixedValue;

import static net.bytebuddy.matcher.ElementMatchers.named;

public class ByteBuddyExample {
    public static void main(String[] args) throws Exception {
        Class<?> dynamicType = new ByteBuddy()
                .subclass(Object.class)
                .method(named("toString"))
                .intercept(FixedValue.value("Hello World"))
                .make()
                .load(ByteBuddyExample.class.getClassLoader(), ClassLoadingStrategy.Default.WRAPPER)
                .getLoaded();

        System.out.println(dynamicType.newInstance().toString()); // 输出: Hello World
    }
}