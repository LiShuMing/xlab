package com.starrocks.common;

import com.google.common.collect.Lists;
import com.google.common.collect.Sets;

import java.util.Iterator;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;

public class TaskRunCompareTest {
    private final static int N = 10;
    public static void test1() {
        List<TaskRun> taskRuns = Lists.newArrayList();
        for (int i = 0; i < N; i++) {
            taskRuns.add(new TaskRun(i, 0));
        }
        taskRuns.sort(TaskRun::compareTo);
        for (int i = 0; i < N; i++) {
            System.out.println(taskRuns.get(i));
        }
    }
    public static void test2() {
        Set<TaskRun> taskRuns = Sets.newTreeSet();
        for (int i = 0; i < N; i++) {
            taskRuns.add(new TaskRun(i, 0));
        }
        Iterator<TaskRun> iter = taskRuns.iterator();
        while (iter.hasNext()) {
            TaskRun taskRun = iter.next();
            System.out.println(taskRun);
        }
    }

    public static void main(String[] args) {
        test2();
    }
}
