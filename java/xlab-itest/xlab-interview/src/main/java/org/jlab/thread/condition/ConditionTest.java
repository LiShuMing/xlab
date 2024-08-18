package org.jlab.thread.condition;

import com.google.common.collect.Lists;

import java.util.List;
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;

/**
 * Created by Mobin on 2016/3/28.
 * conndition的使用
 */
public class ConditionTest {
	public static void main(String[] args) {
		final Commons common = new Commons();

		// sub thread and main thread will run concurrently
		// and print sub and main sequentially
		Thread subThread = new Thread(() -> {
			for (int i = 1; i <= 50; i++) {
				common.sub(i);
			}
		});
		subThread.start();
		for (int i = 1; i <= 50; i++) {
			common.main(i);
		}
		try {
			subThread.join();
		} catch (Exception e) {
			e.printStackTrace();
			System.exit(-1);
		}
		List<Boolean> result = common.getResult();
		System.out.println(result);
		for (int i = 0; i < result.size(); i++) {
			if (i % 2 == 0) {
				assert result.get(i);
			} else {
				assert !result.get(i);
			}
		}
	}
}

class Commons {
	Lock lock = new ReentrantLock();
	Condition condition = lock.newCondition();
	// need to be volatile to ensure visibility
	private volatile boolean sub = true;
	private List<Boolean> result = Lists.newArrayList();

	public void sub(int i) {
		lock.lock();
		try {
			// wait until sub is false
			while (!sub) {   //用while而不用if可以避免虚假唤醒
				try {
					condition.await();
				} catch (InterruptedException e) {
					e.printStackTrace();
				}
			}
			// sub is true now
			result.add(sub);
			for (int j = 1; j <= 10; j++) {
				System.out.println("sub  " + j + " loop of " + i);
			}
			// sub is false now
			sub = false;
			condition.signal();
		} finally {
			lock.unlock();
		}
	}

	public void main(int i) {
		lock.lock();
		try {
			while (sub) {
				try {
					condition.await();
				} catch (InterruptedException e) {
					e.printStackTrace();
				}
			}
			// sub is false now
			result.add(sub);
			for (int j = 1; j <= 10; j++) {
				System.out.println("main " + j + " loop of  " + i);
			}
			// sub is true now
			sub = true;
			condition.signal();
		} finally {
			lock.unlock();
		}
	}

	public List<Boolean> getResult() {
		return result;
	}
}
