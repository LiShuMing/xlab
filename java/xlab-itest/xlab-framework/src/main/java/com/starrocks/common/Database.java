package com.starrocks.common;

import java.util.concurrent.locks.ReentrantReadWriteLock;

public class Database {
    public final String dbName;
    public final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();
    public int val;
    public Database(String dbName) {
        this.dbName = dbName;
    }

    public void rLock() {
        lock.readLock().lock();
    }

    public void rUnLock() {
        lock.readLock().unlock();
    }

    public void wLock() {
        lock.writeLock().lock();
    }

    public void wUnLock() {
        lock.writeLock().unlock();
    }

    public int getVal() {
        return val;
    }

    public void setVal(int val) {
       this.val = val;
    }
}
