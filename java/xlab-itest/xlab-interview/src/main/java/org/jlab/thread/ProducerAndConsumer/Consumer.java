package org.jlab.thread.ProducerAndConsumer;

/**
 * Created by MOBIN on 2016/8/18.
 */
public class Consumer implements Runnable {
	private EventStorage storage;

	public Consumer(EventStorage storage) {
		this.storage = storage;
	}

	@Override
	public void run() {
		for (int i = 0; i < 100; i++) {
			storage.get();
		}
	}
}
