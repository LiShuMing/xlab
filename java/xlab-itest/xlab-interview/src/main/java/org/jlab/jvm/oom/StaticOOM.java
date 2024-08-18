package org.jlab.jvm.oom;

import org.apache.log4j.Logger;

import java.util.ArrayList;
import java.util.List;

public class StaticOOM {
    private static final Logger LOG = Logger.getLogger(StaticOOM.class);
    public static List<Double> list = new ArrayList<>();
    public void populateList() {
        for (int i = 0; i < 10000000; i++) {
            list.add(Math.random());
        }
        LOG.info("Debug Point 2");
    }
    public static void main(String[] args) {
        LOG.info("Debug Point 1");
        new StaticOOM().populateList();
        LOG.info("Debug Point 3");
    }
}
