package com.lemon.thread.Executor;

import java.util.concurrent.Callable;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

/**
 * Created by Mobin on 2016/3/20.
 * 执行完线程后返回结果
 */
public class CallableAndFuture {
	public static void main(String[] args) throws ExecutionException, InterruptedException {
		ExecutorService executor = Executors.newSingleThreadExecutor();

		Future<String> future = executor.submit(new Callable<String>() {
			public String call() throws Exception {
				return "MOBIN";
			}
		});

		System.out.println("任务的执行结果：" + future.get());
	}
}
