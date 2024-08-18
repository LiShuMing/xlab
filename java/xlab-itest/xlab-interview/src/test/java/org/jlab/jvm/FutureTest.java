package org.jlab.jvm;

import org.junit.Test;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class FutureTest {
    private static enum TaskRunState {
        PENDING,
        RUNNING,
        SUCCESS,
        FAILED
    }
    private static class TaskRun {
        private final CompletableFuture<TaskRunState> future;
        public TaskRun() {
            this.future = new CompletableFuture<>();
        }
        public CompletableFuture<TaskRunState> getFuture() {
            return future;
        }
    }

    @Test
    public void testComplete() {
        TaskRun run = new TaskRun();
        ExecutorService executor = Executors.newFixedThreadPool(5);
        CompletableFuture<TaskRunState> future = CompletableFuture.supplyAsync(
                        () -> {
                            if (true) {
                                throw new RuntimeException("Failed");
                            }
                            return TaskRunState.SUCCESS;
                        }, executor);
        future.whenComplete((r, e) -> {
            if (e == null) {
                run.future.complete(TaskRunState.SUCCESS);

                System.out.println("Success: " + r);
            } else {
                run.future.completeExceptionally(e);
                System.out.println("Failed: " + e);
            }
        });
        try {
            TaskRunState state = run.future.get();
            System.out.println("State: " + state);
        } catch (ExecutionException e) {
            System.out.println("1");
            throw new RuntimeException(e);
        } catch (InterruptedException e) {
            System.out.println("2");
            throw new RuntimeException(e);
        }
    }
}
