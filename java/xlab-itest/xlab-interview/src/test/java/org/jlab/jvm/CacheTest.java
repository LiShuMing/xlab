package org.jlab.jvm;


import org.junit.Test;

import java.lang.ref.WeakReference;
import java.util.HashMap;
import java.util.Map;

public class CacheTest {
    static class CacheExample {
        private Map<String, WeakReference<MyHeavyObject>> cache = new HashMap<>();

        public MyHeavyObject get(String key) {
            WeakReference<MyHeavyObject> ref = cache.get(key);
            if (ref != null) {
                return ref.get();
            } else {
                MyHeavyObject obj = new MyHeavyObject();
                cache.put(key, new WeakReference<>(obj));
                return obj;
            }
        }
        public void put(String key, MyHeavyObject obj) {
            cache.put(key, new WeakReference<>(obj));
        }

        private static class MyHeavyObject {
            private byte[] largeData = new byte[1024 * 1024 * 10]; // 10MB data
        }
    }

    @Test
    public void testCache() {
        CacheExample cache = new CacheExample();
        CacheExample.MyHeavyObject obj1 = cache.get("key1");
        cache.put("key2", new CacheExample.MyHeavyObject());
        CacheExample.MyHeavyObject obj2 = cache.get("key2");
        CacheExample.MyHeavyObject obj3 = cache.get("key3");
        CacheExample.MyHeavyObject obj4 = cache.get("key4");
        CacheExample.MyHeavyObject obj5 = cache.get("key5");
    }
}
