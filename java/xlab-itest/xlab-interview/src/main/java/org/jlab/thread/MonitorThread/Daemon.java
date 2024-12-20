package org.jlab.thread.MonitorThread;

import java.util.concurrent.ThreadFactory;

/**
 * Created by Mobin on 2017/2/18.
 */
public class Daemon extends Thread {
	Runnable runnable = null;

	{
		setDaemon(true); // 永远作为守护线程
	}

	public Daemon() {
		super();
	}

	public Daemon(Runnable runnable) {
		super(runnable);
		this.runnable = runnable;
	}

	public Runnable getTunnable() {
		return runnable;
	}

	/*
	 为ExecutorService提供一个名为守护线程的工厂
	 创建一个可重用固定的守护线程池
	 Executors.newFixedThreadPool(threads,new Daemon.DaemonFactory());
	*/
	public static class DaemonFactory extends Daemon implements ThreadFactory {

		@Override
		public Thread newThread(Runnable r) {
			return new Daemon(r);
		}
	}
}
