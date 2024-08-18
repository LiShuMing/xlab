package com.lemon.thread;

import com.google.common.base.Joiner;
import com.google.common.collect.Sets;

import java.util.Set;

public class MultiThreadTest {
	public static void main(String[] args) {
		final Sharedata sharedata = new Sharedata();
		for (int i = 0; i < 5; i++) {
			new Thread(new Runnable() {
				public void run() {
					sharedata.inc();
				}
			}).start();

//			new Thread(new Runnable() {
//				public void run() {
//					sharedata.dec();
//				}
//			}).start();
		}
	}

	static class Sharedata {
		private int count = 10;
		private boolean flag = true;
		private Set<Long> threadIds = Sets.newConcurrentHashSet();

		private void printStack(Set<Long> threadIds) {
			System.out.println("Thread Corrupt: " + threadIds);
			for (Thread thread : Thread.getAllStackTraces().keySet()) {
				if (threadIds.contains(thread.getId())) {
					System.out.println("Print Thread Stack({}) :\n {}" + thread.getId() + "\n" +
							Joiner.on("\n").join(thread.getStackTrace()));
				}
			}
		}
		public void inc() {
			threadIds.add(Thread.currentThread().getId());
			if (threadIds.size() > 1) {
				printStack(threadIds);
			}
            /*while(!flag) {
                try {
                    this.wait();
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }*/
			count++;
			System.out.println("Add: " + count);
			threadIds.remove(Thread.currentThread().getId());
          /*  flag = false;
            this.notify();*/
		}

		public void dec() {
          /*  while (flag){
                try {
                    this.wait();
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }*/
			count--;
			System.out.println("线程进行了减操作" + count);
           /* flag = true;
            this.notify();*/
		}
	}
}
