package com.starrocks.common;

import com.google.common.collect.Lists;
import com.google.common.util.concurrent.Uninterruptibles;

import java.util.List;

public class ReentranceRWLockTest {

    private static List<Database> mockDbs(int n) {
        List<Database> dbs = Lists.newArrayList();
        for (int i = 0; i < n; i++) {
            Database db = new Database("db" + i);
            dbs.add(db);
        }
        return dbs;
    }

    public static void doDML(List<Database> dbs) {
        try {
            Locker.lockDatabases(dbs);
            System.out.println(Thread.currentThread().getName() + ": lock all databases: time 1");
            Uninterruptibles.sleepUninterruptibly(10, java.util.concurrent.TimeUnit.SECONDS);
            try {
                Locker.lockDatabases(dbs);
                System.out.println(Thread.currentThread().getName() + ": lock all databases: time 2");
            } catch (Exception e) {
                e.printStackTrace();
            } finally {
                System.out.println(Thread.currentThread().getName() + ": unlock all databases: time 2");
                Locker.unlockDatabases(dbs);
            }
        } finally {
            Locker.unlockDatabases(dbs);
            System.out.println(Thread.currentThread().getName() + ": unlock all databases: time 1");
        }
    }

    public static void main(String[] args) {
        List<Database> dbs = mockDbs(10);
        List<Thread> threads = Lists.newArrayList();
        for (int i = 0; i < 10; i++) {
            Thread t1 = new Thread(() -> {
                doDML(dbs);
            });
            threads.add(t1);
        }

        for (Thread t : threads) {
            t.start();
        }
        for (Thread t : threads) {
            try {
                t.join();
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
    }
}
