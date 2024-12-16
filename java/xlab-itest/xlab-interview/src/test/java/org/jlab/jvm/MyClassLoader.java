package org.jlab.jvm;

import java.io.*;

public class MyClassLoader extends ClassLoader {
    private String classPath;

    public MyClassLoader(String classPath) {
        this.classPath = classPath;
    }

    @Override
    protected Class<?> findClass(String name) throws ClassNotFoundException {
        // find class in specified path
        byte[] classData = loadClassData(name);
        if (classData == null) {
            throw new ClassNotFoundException();
        }
        return defineClass(name, classData, 0, classData.length);
    }

    private byte[] loadClassData(String name) {
        try {
            String fileName = classPath + name.replace(".", "/") + ".class";
            InputStream inputStream = new FileInputStream(fileName);
            ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
            int len;
            while ((len = inputStream.read()) != -1) {
                outputStream.write(len);
            }
            inputStream.close();
            return outputStream.toByteArray();
        } catch (IOException e) {
            e.printStackTrace();
            return null;
        }
    }
}