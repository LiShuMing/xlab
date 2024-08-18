package com.starrocks.itest.framework.mv

interface Worker {
    /**
     * One worker may build a lot of blocks. One can use those blocks to get permutations of all kinds of bocks.
     */
    fun buildBlocks(): List<Block>;
}