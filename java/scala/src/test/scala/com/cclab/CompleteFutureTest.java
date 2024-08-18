package scala.com.cclab;

import java.util.concurrent.CompletableFuture;

import org.junit.Test;

/**
 * @author shuming.lsm
 * @version 2019/04/17
 */
public class CompleteFutureTest {

  @Test
  public void thenApply() {
    String result = CompletableFuture
        .supplyAsync(() -> "hello")
        .thenApply(s -> s + " world")
        .join();
    System.out.println(result);
  }

  @Test
  public void thenAccept(){
    CompletableFuture.supplyAsync(() -> "hello").thenAccept(s -> System.out.println(s+" world"));
  }

  @Test
  public void thenRun(){
    CompletableFuture.supplyAsync(() -> {
      try {
        Thread.sleep(2000);
      } catch (InterruptedException e) {
        e.printStackTrace();
      }
      return "hello";
    }).thenRun(() -> System.out.println("hello world"));

    try {
      Thread.sleep(3000);
    } catch (InterruptedException e) {
      e.printStackTrace();
    }
  }

  @Test
  public void thenCombine() {
    String result = CompletableFuture.supplyAsync(() -> {
      try {
        Thread.sleep(2000);
      } catch (InterruptedException e) {
        e.printStackTrace();
      }
      return "hello";
    }).thenCombine(CompletableFuture.supplyAsync(() -> {
      try {
        Thread.sleep(3000);
      } catch (InterruptedException e) {
        e.printStackTrace();
      }
      return "world";
    }), (s1, s2) -> s1 + " " + s2).join();
    System.out.println(result);
  }

  @Test
  public void thenAcceptBoth() {
    CompletableFuture.supplyAsync(() -> {
      try {
        Thread.sleep(2000);
      } catch (InterruptedException e) {
        e.printStackTrace();
      }
      return "hello";
    }).thenAcceptBoth(CompletableFuture.supplyAsync(() -> {
      try {
        Thread.sleep(3000);
      } catch (InterruptedException e) {
        e.printStackTrace();
      }
      return "world";
    }), (s1, s2) -> System.out.println(s1 + " " + s2));
    while (true){}
  }


  @Test
  public void runAfterBoth(){
    CompletableFuture.supplyAsync(() -> {
      try {
        Thread.sleep(2000);
      } catch (InterruptedException e) {
        e.printStackTrace();
      }
      System.out.println("s1");
      return "s1";
    }).runAfterBothAsync(CompletableFuture.supplyAsync(() -> {
      try {
        Thread.sleep(3000);
      } catch (InterruptedException e) {
        e.printStackTrace();
      }
      System.out.println("s2");
      return "s2";
    }), () -> System.out.println("hello world"));
    try {
      Thread.sleep(6000);
    } catch (InterruptedException e) {
      e.printStackTrace();
    }
  }

  @Test
  public void applyToEither() {
    String result = CompletableFuture.supplyAsync(() -> {
      try {
        Thread.sleep(1000);
      } catch (InterruptedException e) {
        e.printStackTrace();
      }
      return "s1";
    }).applyToEither(CompletableFuture.supplyAsync(() -> {
      try {
        Thread.sleep(2000);
      } catch (InterruptedException e) {
        e.printStackTrace();
      }
      return "hello world";
    }), s -> s).join();
    System.out.println(result);
  }

  @Test
  public void acceptEither() {
    CompletableFuture.supplyAsync(() -> {
      try {
        Thread.sleep(3000);
      } catch (InterruptedException e) {
        e.printStackTrace();
      }
      return "s1";
    }).acceptEither(CompletableFuture.supplyAsync(() -> {
      try {
        Thread.sleep(2000);
      } catch (InterruptedException e) {
        e.printStackTrace();
      }
      return "hello world";
    }), System.out::println);
    while (true){}
  }

  @Test
  public void runAfterEither() {
    CompletableFuture.supplyAsync(() -> {
      try {
        Thread.sleep(3000);
      } catch (InterruptedException e) {
        e.printStackTrace();
      }
      return "s1";
    }).runAfterEither(CompletableFuture.supplyAsync(() -> {
      try {
        Thread.sleep(2000);
      } catch (InterruptedException e) {
        e.printStackTrace();
      }
      return "s2";
    }), () -> System.out.println("hello world"));
    while (true) {
    }
  }

  @Test
  public void exceptionally() {
    String result = CompletableFuture.supplyAsync(() -> {
      try {
        Thread.sleep(3000);
      } catch (InterruptedException e) {
        e.printStackTrace();
      }
      if (1 == 1) {
        throw new RuntimeException("测试一下异常情况");
      }
      return "s1";
    }).exceptionally(e -> {
      System.out.println(e.getMessage());
      return "hello world";
    }).join();
    System.out.println(result);
  }

  @Test
  public void whenComplete() {
    String result = CompletableFuture.supplyAsync(() -> {
      try {
        Thread.sleep(3000);
      } catch (InterruptedException e) {
        e.printStackTrace();
      }
      if (1 == 1) {
        throw new RuntimeException("测试一下异常情况");
      }
      return "s1";
    }).whenComplete((s, t) -> {
      System.out.println(s);
      System.out.println(t.getMessage());
    }).exceptionally(e -> {
      System.out.println(e.getMessage());
      return "hello world";
    }).join();
    System.out.println(result);
  }

  @Test
  public void handle() {
    String result = CompletableFuture.supplyAsync(() -> {
      try {
        Thread.sleep(3000);
      } catch (InterruptedException e) {
        e.printStackTrace();
      }
      //出现异常
      if (1 == 1) {
        throw new RuntimeException("测试一下异常情况");
      }
      return "s1";
    }).handle((s, t) -> {
      if (t != null) {
        return "hello world";
      }
      return s;
    }).join();
    System.out.println(result);
  }
}
