package com.starrocks.common;

import java.util.Comparator;
import java.util.List;

public class Locker {
    public static void lockDatabases(List<Database> dbs) {
        // dbs.sort(Comparator.comparing(a -> a.dbName));
        for (Database db : dbs) {
            db.rLock();
        }
    }

    public static void unlockDatabases(List<Database> dbs) {
        for (Database db : dbs) {
            db.rUnLock();
        }
    }
}
