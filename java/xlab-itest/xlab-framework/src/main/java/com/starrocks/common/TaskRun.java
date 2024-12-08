package com.starrocks.common;

class TaskRun implements Comparable<TaskRun> {
    public long createTime;
    public long priority;
    public TaskRun(long createTime, long priority) {
        this.createTime = createTime;
        this.priority = priority;
    }

    @Override
    public int compareTo(TaskRun o) {
        if (this.priority != o.priority) {
            return Long.compare(o.priority, this.priority);
        } else {
            return Long.compare(this.createTime, o.createTime);
        }
    }

    public String toString() {
        return "TaskRun{" +
                "createTime=" + createTime +
                ", priority=" + priority +
                '}';
    }
}