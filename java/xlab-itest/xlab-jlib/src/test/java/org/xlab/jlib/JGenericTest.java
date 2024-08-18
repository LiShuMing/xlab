package org.xlab.jlib;

import com.google.common.collect.Maps;
import org.junit.Test;
import org.xlab.jlib.common.PCell;
import org.xlab.jlib.common.PListCell;
import org.xlab.jlib.common.PRangeCell;

import java.util.Map;

public class JGenericTest {
    private void fun1(Map<String, PCell> m) {
    }

    private void fun2(Map<String, PCell> m) {
//        m.put("", new PListCell());
//        PCell pCell = new PListCell();
        PListCell pCell = new PListCell();
        m.put("", pCell);
    }

    @Test
    public void testGenerate() {
        Map<String, PCell> listCellMap = Maps.newHashMap();
//        Map<String, PRangeCell> rangeCellMap = Maps.newHashMap();
        Map<String, PCell> cellMap = Maps.newHashMap();
//        fun1(listCellMap);

        fun2(cellMap);
        fun2(listCellMap);
//        fun2(rangeCellMap);
    }
}
