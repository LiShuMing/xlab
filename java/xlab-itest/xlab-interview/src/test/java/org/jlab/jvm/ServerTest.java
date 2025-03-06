package org.jlab.jvm;

import org.junit.Test;

import java.util.concurrent.ExecutionException;
import java.util.concurrent.Executors;
import java.util.concurrent.StructuredTaskScope;
//import java.util.template.*;

public class ServerTest {
    @Test
    public void testServer() {
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            executor.submit(() -> System.out.println("Hello from virtual thread"));
        }
    }

    @Test
    public void test2() throws InterruptedException {
        try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
            scope.fork(() -> {
                System.out.println("Task 1");
                return null;
            });
            scope.fork(() -> {
                System.out.println("Task 2");
                return null;
            });
            scope.join();
            scope.throwIfFailed();
        } catch (ExecutionException e) {
            throw new RuntimeException(e);
        }
    }

    @Test
    public void testRecord() {
        record Point(int x, int y) {}
        var obj = new Point(1, 2);
        if (obj instanceof Point(int x, int y)) {
            System.out.println("x: " + x + ", y: " + y);
        }
    }
    @Test
    public void testStringTemplate() {
        String name = "Alice";
        int age = 30;
//        String result = STR."Name: \{name}, Age: \{age}";
    }
}
