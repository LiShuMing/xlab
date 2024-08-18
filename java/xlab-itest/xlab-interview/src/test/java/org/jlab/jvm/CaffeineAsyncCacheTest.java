package org.jlab.jvm;

import com.github.benmanes.caffeine.cache.AsyncCacheLoader;
import com.github.benmanes.caffeine.cache.AsyncLoadingCache;
import com.github.benmanes.caffeine.cache.Caffeine;
import com.google.common.util.concurrent.Uninterruptibles;
import org.junit.Test;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Executor;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

public class CaffeineAsyncCacheTest {
    // **定义异步缓存**
    private final AsyncLoadingCache<String, String> cache = Caffeine.newBuilder()
            .maximumSize(100) // 限制最大缓存条目
            .expireAfterWrite(10, TimeUnit.SECONDS) // 10秒后过期
            .buildAsync(new AsyncCacheLoader<>() {
                @Override
                public CompletableFuture<String> asyncLoad(String key, Executor executor) {
                    return CompletableFuture.supplyAsync(() -> {
                        try {
                            Thread.sleep(500); // 模拟异步延迟
                        } catch (InterruptedException e) {
                            throw new RuntimeException(e);
                        }
                        return "Value for " + key;
                    }, executor);
                }
            });

    @Test
    public void testAsyncCacheLoader() throws ExecutionException, InterruptedException {
        // **从缓存异步获取值**
        CompletableFuture<String> future = cache.get("testKey");

        // **等待任务完成**
        String value = future.get(); // 阻塞直到任务完成

        // **验证缓存返回的值**
        assertEquals("Value for testKey", value);

        // **缓存中已经有这个值，检查同步读取**
        assertTrue(cache.synchronous().getIfPresent("testKey") != null);
    }

    @Test
    public void testAsyncCacheExpiration() throws ExecutionException, InterruptedException {
        // **写入缓存**
        cache.get("expireKey").get(); // 触发异步加载

        // **等待缓存过期**
        Thread.sleep(11000); // 11 秒 > 10 秒缓存过期时间

        // **缓存应该过期，getIfPresent 应该返回 null**
        assertNull(cache.synchronous().getIfPresent("expireKey"));
    }

    @Test
    public void testAsyncCachePreloading() throws ExecutionException, InterruptedException {
        // **预加载缓存**
        cache.put("preKey", CompletableFuture.completedFuture("Preloaded Value"));

        // **立即获取值，不应该触发异步加载**
        assertEquals("Preloaded Value", cache.get("preKey").get());
    }

    @Test
    public void testAsyncCacheParallelRequests() throws ExecutionException, InterruptedException {
        // **并行请求多个 key**
        CompletableFuture<String> future1 = cache.get("key1");
        CompletableFuture<String> future2 = cache.get("key2");

        // **等待完成**
        assertEquals("Value for key1", future1.get());
        assertEquals("Value for key2", future2.get());

        // **检查缓存是否已经存储**
        assertNotNull(cache.synchronous().getIfPresent("key1"));
        assertNotNull(cache.synchronous().getIfPresent("key2"));
    }

    @Test
    public void testAsyncCacheWithCustomExecutorSync() {
        // **使用自定义线程池**
        ExecutorService customExecutor = Executors.newFixedThreadPool(5);

        AsyncLoadingCache<String, String> customCache = Caffeine.newBuilder()
                .maximumSize(50)
                .buildAsync(new AsyncCacheLoader<>() {
                    @Override
                    public CompletableFuture<String> asyncLoad(String key, Executor executor) {
                        System.out.println("2: start to load " + key + " on " + Thread.currentThread().getName() + ": " + System.currentTimeMillis());
                        Uninterruptibles.sleepUninterruptibly(5000, TimeUnit.MILLISECONDS); // 模拟异步延迟
                        System.out.println("3: Loading " + key + " on " + Thread.currentThread().getName() + ": " + System.currentTimeMillis());
                        return CompletableFuture.supplyAsync(() -> "Custom " + key, customExecutor);
                    }
                });
        System.out.println("1: start to get:" + System.currentTimeMillis());
        CompletableFuture<String> future = customCache.get("customKey");
        System.out.println("4: start to wait:" + System.currentTimeMillis());
        Uninterruptibles.sleepUninterruptibly(10000, TimeUnit.MILLISECONDS); // 模拟异步延迟
        System.out.println("5: end to wait:" + System.currentTimeMillis());
        customExecutor.shutdown();
    }

    @Test
    public void testAsyncCacheWithCustomExecutor1() {
        ExecutorService customExecutor = Executors.newFixedThreadPool(5);
        AsyncLoadingCache<String, String> customCache = Caffeine.newBuilder()
                .maximumSize(50)
                .buildAsync(new AsyncCacheLoader<>() {
                    @Override
                    public CompletableFuture<String> asyncLoad(String key, Executor executor) {
                        return CompletableFuture.supplyAsync(() -> {
                            System.out.println("3: Start loading " + key + " on " + Thread.currentThread().getName() + ": " + System.currentTimeMillis());
                            Uninterruptibles.sleepUninterruptibly(5000, TimeUnit.MILLISECONDS);
                            System.out.println("4: Loaded " + key + " on " + Thread.currentThread().getName() + ": " + System.currentTimeMillis());
                            return "Custom " + key;
                        }, executor);
                    }
                });
        System.out.println("1: start to get:" + System.currentTimeMillis());
        CompletableFuture<String> future = customCache.get("customKey");
        System.out.println("2: start to wait:" + System.currentTimeMillis());
        //assertEquals("Custom customKey1:", future.get());
        Uninterruptibles.sleepUninterruptibly(10000, TimeUnit.MILLISECONDS);
        System.out.println("5: end to wait:" + System.currentTimeMillis());
        customExecutor.shutdown();
    }
}
