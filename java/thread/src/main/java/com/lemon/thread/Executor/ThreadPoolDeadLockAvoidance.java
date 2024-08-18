package com.lemon.thread.Executor;

import java.util.concurrent.ExecutionException;
import java.util.concurrent.Future;
import java.util.concurrent.SynchronousQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;

/**
 * Created by Mobin on 2017/8/7.
 */
public class ThreadPoolDeadLockAvoidance {
	private final ThreadPoolExecutor threadPoolExecutor = new ThreadPoolExecutor(
			1,
			1,
			60L, TimeUnit.SECONDS,
			new SynchronousQueue<Runnable>(),
			new ThreadPoolExecutor.CallerRunsPolicy()
	);

	public static void main(String[] args) {
		ThreadPoolDeadLockAvoidance poolDeadLockAvoidance = new ThreadPoolDeadLockAvoidance();
		poolDeadLockAvoidance.test("MOBIN");
	}

	public void test(final String mes) {
		Runnable taskA = new Runnable() {
			@Override
			public void run() {
				System.out.println("Executing taskA");
				Runnable tabkB = new Runnable() {
					@Override
					public void run() {
						System.out.println("TaskB processes " + mes);
					}
				};
				Future<?> rs = threadPoolExecutor.submit(tabkB);
				try {
					rs.get();   //等待taskB执行
				} catch (InterruptedException e) {
					e.printStackTrace();
				} catch (ExecutionException e) {
					e.printStackTrace();
				}
				System.out.println("TaskA Done");
			}
		};
		threadPoolExecutor.submit(taskA);
	}
}
