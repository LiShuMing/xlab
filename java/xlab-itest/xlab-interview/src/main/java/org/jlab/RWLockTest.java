package org.jlab;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.concurrent.locks.ReadWriteLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;

public class RWLockTest {
    public static final Logger LOGGER = LoggerFactory.getLogger(RWLockTest.class);

    public static void main(String[] args) {
        SomeClass someClass = new SomeClass();

        Reader readerRunnable = new Reader(someClass);
        Writer writerRunnable = new Writer(someClass);
        //group 1 readers
        for (int i = 0; i < 10; i++) {
            new Thread(readerRunnable).start();
        }

        // 2 writers
        new Thread(writerRunnable).start();
        LOGGER.info("!!!!!!!!!!!!!!!WRITER_1 WAS STARTED!!!!!!!!!!!!!!!");
        new Thread(writerRunnable).start();
        LOGGER.info("!!!!!!!!!!!!!!!WRITER_2 WAS STARTED!!!!!!!!!!!!!!!");

        //group 2 readers
        for (int i = 0; i < 10; i++) {
            Thread thread = new Thread(readerRunnable);
            LOGGER.info(String.format("%s was submitted", thread.getId()));
            thread.start();
        }
    }

    public static class SomeClass {
        public ReadWriteLock readWriteLock = new ReentrantReadWriteLock();

        public void read() {
            LOGGER.info(String.format("Read by %s submitted", Thread.currentThread().getId()));
            readWriteLock.readLock().lock();
            try {
                LOGGER.info(String.format("Read by %s started", Thread.currentThread().getId()));
                Thread.sleep(5000);
                LOGGER.info(String.format("Read by %s finished", Thread.currentThread().getId()));
            } catch (InterruptedException e) {
                e.printStackTrace();
            } finally {
                readWriteLock.readLock().unlock();
            }
        }

        public void write() {
            LOGGER.info(String.format("Write by %s submitted", Thread.currentThread().getId()));
            readWriteLock.writeLock().lock();
            try {
                LOGGER.info(String.format("!!!!!!!!!!Write by %s started!!!!!!!!!!!!", Thread.currentThread().getId()));
                Thread.sleep(3000);
                LOGGER.info(String.format("!!!!!!!!!!Write by %s finished!!!!!!!!", Thread.currentThread().getId()));
            } catch (InterruptedException e) {
                e.printStackTrace();
            } finally {
                readWriteLock.writeLock().unlock();
            }
        }
    }

    public static class Reader implements Runnable {
        SomeClass someClass;
        public Reader(SomeClass someClass) {
            this.someClass = someClass;
        }

        @Override
        public void run() {
            someClass.read();
        }
    }

    public static class Writer implements Runnable {
        SomeClass someClass;

        public Writer(SomeClass someClass) {
            this.someClass = someClass;
        }

        @Override
        public void run() {
            someClass.write();
        }
    }
}