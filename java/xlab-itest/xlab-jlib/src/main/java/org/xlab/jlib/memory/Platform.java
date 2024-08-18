package org.xlab.jlib.memory;

import sun.misc.Unsafe;

import java.lang.reflect.Field;

/**
 * @author shuming.lsm
 * @version 2018/08/16
 */
public class Platform {
  public static Unsafe getUnsafe() throws Exception {
    Field theUnsafe = Unsafe.class.getDeclaredField("theUnsafe");
    theUnsafe.setAccessible(true);
    Unsafe unsafe = (Unsafe)theUnsafe.get(null);
    return unsafe;
  }
}
