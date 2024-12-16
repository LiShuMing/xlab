package org.jlab.jvm;

import jdk.incubator.vector.FloatVector;
import jdk.incubator.vector.VectorSpecies;

public class VectorizedAddition {
    static final VectorSpecies<Float> SPECIES = FloatVector.SPECIES_PREFERRED;
    /**
     *         float[] a = {1.0f, 2.0f, 3.0f, 4.0f};
     *         float[] b = {5.0f, 6.0f, 7.0f, 8.0f};
     *         float[] c = new float[4];
     *
     *         for (int i = 0; i < a.length; i++) {
     *             c[i] = a[i] + b[i];
     *         }
     *
     *         for (float v : c) {
     *             System.out.println(v);
     *         }
     * @param args
     */
    public static void main(String[] args) {
        float[] a = {1.0f, 2.0f, 3.0f, 4.0f};
        float[] b = {5.0f, 6.0f, 7.0f, 8.0f};
        float[] c = new float[4];

        // 矢量化操作
        for (int i = 0; i < a.length; i += SPECIES.length()) {
            // 加载数据到矢量寄存器
            var va = FloatVector.fromArray(SPECIES, a, i);
            var vb = FloatVector.fromArray(SPECIES, b, i);

            // 执行加法
            var vc = va.add(vb);

            // 将结果存回数组
            vc.intoArray(c, i);
        }

        for (float v : c) {
            System.out.println(v);
        }
    }
}