package com.cclab;

import com.google.common.collect.Lists;
import org.junit.Test;

import java.security.InvalidParameterException;
import java.util.List;

public class StreamTest {
    @Test
    public void testEmptyList() {
        List<String> empty = Lists.newArrayList();
        {
            boolean ret = empty.stream().noneMatch(x -> x.equals("x"));
            System.out.println(ret);
        }
        {
            boolean ret = empty.stream().anyMatch(x -> x.equals("x"));
            System.out.println(ret);
        }
        {
            boolean ret = empty.stream().allMatch(x -> x.equals("x"));
            System.out.println(ret);
        }
    }

    class Timer implements AutoCloseable {
        public Timer() {}
        @Override
        public void close() {
        }
    }
    private Timer funcThrowException() {
        if (true) {
            throw new InvalidParameterException("invalid param");
        } else {
            return new Timer();
        }
    }
    @Test
    public void testException() throws Exception {
        try (Timer v = funcThrowException()) {
            System.out.println(v);
        }
    }
}
