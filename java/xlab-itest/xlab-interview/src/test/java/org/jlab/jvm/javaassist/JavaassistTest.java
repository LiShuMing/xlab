package org.jlab.jvm.javaassist;

import org.junit.Test;

import javassist.*;

public class JavaassistTest {
    @Test
    public void testBasic() throws Exception {
        // 创建类池
        ClassPool pool = ClassPool.getDefault();
        // 创建一个新类
        CtClass newClass = pool.makeClass("com.example.HelloWorld");
        // 添加一个字段
        CtField field = CtField.make("public String message = \"Hello, JavaAssist!\";", newClass);
        newClass.addField(field);
        // 添加一个方法
        CtMethod method = CtMethod.make(
                "public void printMessage() { System.out.println(message); }",
                newClass
        );
        newClass.addMethod(method);
        // 将类写入文件
        newClass.writeFile("./output"); // 输出路径
        // 加载并调用类
        Class<?> clazz = newClass.toClass();
        Object obj = clazz.getDeclaredConstructor().newInstance();
        clazz.getMethod("printMessage").invoke(obj);
    }
}
