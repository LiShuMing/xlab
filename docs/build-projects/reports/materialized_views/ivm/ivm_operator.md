
我是一名拥有 10 年以上经验的资深研发工程师，目前是顶尖开源 OLAP 数据库
（[StarRocks](https://github.com/StarRocks/starrocks)）的核心开发者与 Committer。

我的日常技术栈围绕 C++、高并发、分布式系统、向量化执行以及底层性能压榨。
同时，我也在积极拥抱 AI 时代，探索 LLM、RAG 和前沿编程语言（如 Rust、Haskell）。

背景前提，可以假设如下条件成立：
- 增量计算本质上是通过维护状态或者按照affected rows进行重算的逻辑，而本方案采用不维护额外状态，基于重算的逻辑进行推导。
- 每个表均可以做MVCC查询，比如表R，可以查询R_from(上一个delta）/R_to(最新）/R_d(delta)数据；

请基于代数关系退到增量计算设计，主要在Optimizer内完成推导，尽量复用现有的算子，将一个输入的SQL(MV定义Query)转换成一个增量计算的、可以执行的Plan。请帮我分析设计每个算子的推导逻辑、公式。

注意输出时：
- 在推导过程请不要使用除输入表，需要增量计算的地方均通过affected rows进行重新推导。
- 增量计算的推导，尽量保障Optimizer的表达，可以在一个rule中完整输出的，同时兼顾性能、通用性。
- 按照Markdown文档的格式输出，方便整理；
- 算子的增量计算，先用关系代数的语言推导计算，再用SQL展开的方式推导展开 ；

请按照上述格式先推到Left Anti Join的增量计算，以R left anti join S为例。
- 先统一计算出来S key的cnt变化,分成：不变化，不匹配->匹配，匹配->不匹配
- 然后根据这上述关系，再结合R的多版本，输出最终的Delta变化；

# 增量算子推导

## Left Anti JOin
R left anti join S


> select R.* from R anti semi join S on R.k = S.k;

Solution 1
```
WITH 
-- 1. 聚合 S_d 获取 key 的净变化量
cte_s_delta_agg AS (
    SELECT 
        join_key, 
        SUM(_delta_op) AS delta_cnt 
    FROM S_d 
    GROUP BY join_key
),

-- 2. 探测 S_to 获取当前计数值 (利用 Runtime Filter 下推)
cte_s_to_cnt AS (
    SELECT 
        S.join_key, 
        COUNT(*) AS to_cnt
    FROM S_to AS S
    LEFT SEMI JOIN cte_s_delta_agg AS D ON S.join_key = D.join_key
    GROUP BY S.join_key
),

-- 3. 计算 S 状态变迁
cte_s_transitions AS (
    SELECT 
        D.join_key,
        CASE 
            WHEN (COALESCE(T.to_cnt, 0) - D.delta_cnt) <= 0 AND COALESCE(T.to_cnt, 0) > 0 THEN 'T_01' -- 不匹配 -> 匹配
            WHEN (COALESCE(T.to_cnt, 0) - D.delta_cnt) > 0 AND COALESCE(T.to_cnt, 0) <= 0 THEN 'T_10' -- 匹配 -> 不匹配
            ELSE 'UNCHANGED' 
        END AS trans_type
    FROM cte_s_delta_agg D
    LEFT JOIN cte_s_to_cnt T ON D.join_key = T.join_key
),

-- 4. 分支 A: R_d 直接与 S_to 进行 Anti Join (解耦 S 变迁)
cte_out_rd AS (
    SELECT R.* FROM R_d AS R
    WHERE NOT EXISTS (
        SELECT 1 FROM S_to AS S WHERE S.join_key = R.join_key
    )
),

-- 5. 分支 B: S 变迁 T_01 导致 R_from 被隐藏，产生 Delete (-1)
cte_out_r_from_delete AS (
    SELECT R.*, -1 AS _override_delta_op
    FROM R_from AS R
    LEFT SEMI JOIN cte_s_transitions AS T 
      ON R.join_key = T.join_key AND T.trans_type = 'T_01'
),

-- 6. 分支 C: S 变迁 T_10 导致 R_from 暴露，产生 Insert (+1)
cte_out_r_from_insert AS (
    SELECT R.*, 1 AS _override_delta_op
    FROM R_from AS R
    LEFT SEMI JOIN cte_s_transitions AS T 
      ON R.join_key = T.join_key AND T.trans_type = 'T_10'
)

-- 7. 合并输出
SELECT col1, col2, _delta_op FROM cte_out_rd
UNION ALL
SELECT col1, col2, _override_delta_op AS _delta_op FROM cte_out_r_from_delete
UNION ALL
SELECT col1, col2, _override_delta_op AS _delta_op FROM cte_out_r_from_insert;
```

Solution 2
```

-- 原始
select R.* from R anti semi join S on R.k = S.k;

-- 改写后
WITH
/* 0) 只计算“可能用到”的 key：
      - ΔR 里出现的 key（因为要做 ΔR|K11）
      - ΔS 里出现的 key（因为这些 key 的门控可能翻转）
   这样避免全量扫所有 key。
*/
K AS (
  SELECT DISTINCT k FROM dR
  UNION
  SELECT DISTINCT k FROM dS
),

/* 1) c0 = cnt_S_from(k)：只在 K 上统计即可 */
c0 AS (
  SELECT k, COUNT(*) AS c0
  FROM S_from
  JOIN K USING (k)
  GROUP BY k
),

/* 2) cd = cnt_dS(k)：ΔS 在 key 上的净变化（+1/-1 累加） */
cd AS (
  SELECT k, SUM(action) AS cd
  FROM dS
  GROUP BY k
),

/* 3) 合并得到 c0, c1=c0+cd，并划分四象限 key 集合 */
flip AS (
  SELECT
    k.k1, k.k2,
    COALESCE(c0.c0, 0) AS c0,
    COALESCE(c0.c0, 0) + COALESCE(cd.cd, 0) AS c1
  FROM K k
  LEFT JOIN c0 USING (k)
  LEFT JOIN cd USING (k)
),

K_up AS (      /* c0=0 且 c1>0：不匹配 -> 匹配 */
  SELECT k FROM flip WHERE c0 = 0 AND c1 > 0
),
K_down AS (    /* c0>0 且 c1=0：匹配 -> 不匹配 */
  SELECT k FROM flip WHERE c0 > 0 AND c1 = 0
),
K_00 AS (      /* c0=0 且 c1=0：一直不匹配 */
  SELECT k FROM flip WHERE c0 =0 0 AND c1 = 0
),

/* -------- 三段互斥输出（天然 canonical，不需要 consolidate） */

/* (1) ΔR|K00：只透传那些“一直不匹配”的 key 上的 ΔR，action 保持不变 */
part1 AS (
  SELECT dR.*
  FROM dR
  JOIN K_00 USING (k)
),

/* (2) -R|Kup：从不匹配->匹配，R_from 中这些 key 的行整体变成删除 */
part2 AS (
  SELECT R_from.*, -1 AS action
  FROM R_from
  JOIN K_up USING (k)
),

/* (3) +R|Kdown：从匹配->不匹配，R_to 中这些 key 的行整体变成新增 */
part3 AS (
  SELECT R_to.*, +1 AS action
  FROM R_to
  JOIN K_down USING (k)
)

SELECT * FROM part1
UNION ALL
SELECT * FROM part2
UNION ALL
SELECT * FROM part3;


```

## Left Semi Join
原始
> select R.* from R left semi join S on R.k = S.k;


Solution 1
```
-- [前置步骤：cte_s_delta_agg, cte_s_to_cnt, cte_s_transitions 逻辑与 Anti Join 完全相同]

-- ==========================================
-- 第二阶段：生成 Left Semi Join 正交增量输出
-- ==========================================

-- 分支 A: R_d 直接与 S_to 进行 Semi Join
cte_out_rd AS (
    SELECT R.* FROM R_d AS R
    WHERE EXISTS (
        SELECT 1 FROM S_to AS S WHERE S.join_key = R.join_key
    )
),

-- 分支 B: S 变迁 T_01 导致 R_from 暴露，产生 Insert (+1)
-- 注意：符号与 Anti Join 相反
cte_out_r_from_insert AS (
    SELECT R.*, 1 AS _override_delta_op
    FROM R_from AS R
    LEFT SEMI JOIN cte_s_transitions AS T 
      ON R.join_key = T.join_key AND T.trans_type = 'T_01'
),

-- 分支 C: S 变迁 T_10 导致 R_from 被隐藏，产生 Delete (-1)
-- 注意：符号与 Anti Join 相反
cte_out_r_from_delete AS (
    SELECT R.*, -1 AS _override_delta_op
    FROM R_from AS R
    LEFT SEMI JOIN cte_s_transitions AS T 
      ON R.join_key = T.join_key AND T.trans_type = 'T_10'
)

-- ==========================================
-- 第三阶段：合并输出
-- ==========================================
SELECT col1, col2, _delta_op FROM cte_out_rd
UNION ALL
SELECT col1, col2, _override_delta_op AS _delta_op FROM cte_out_r_from_insert
UNION ALL
SELECT col1, col2, _override_delta_op AS _delta_op FROM cte_out_r_from_delete;
```


Solution 2

```
-- 改写后
WITH
/* 0) 只计算“可能用到”的 key：
      - ΔR 里出现的 key（因为要做 ΔR|K11）
      - ΔS 里出现的 key（因为这些 key 的门控可能翻转）
   这样避免全量扫所有 key。
*/
K AS (
  SELECT DISTINCT k FROM dR
  UNION
  SELECT DISTINCT k FROM dS
),

/* 1) c0 = cnt_S_from(k)：只在 K 上统计即可 */
c0 AS (
  SELECT k, COUNT(*) AS c0
  FROM S_from
  JOIN K USING (k)
  GROUP BY k
),

/* 2) cd = cnt_dS(k)：ΔS 在 key 上的净变化（+1/-1 累加） */
cd AS (
  SELECT k, SUM(action) AS cd
  FROM dS
  GROUP BY k
),

/* 3) 合并得到 c0, c1=c0+cd，并划分四象限 key 集合 */
flip AS (
  SELECT
    k.k1, k.k2,
    COALESCE(c0.c0, 0) AS c0,
    COALESCE(c0.c0, 0) + COALESCE(cd.cd, 0) AS c1
  FROM K k
  LEFT JOIN c0 USING (k)
  LEFT JOIN cd USING (k)
),

K_up AS (      /* c0=0 且 c1>0：不匹配 -> 匹配 */
  SELECT k FROM flip WHERE c0 = 0 AND c1 > 0
),
K_down AS (    /* c0>0 且 c1=0：匹配 -> 不匹配 */
  SELECT k FROM flip WHERE c0 > 0 AND c1 = 0
),
K_11 AS (      /* c0>0 且 c1>0：一直匹配 */
  SELECT k FROM flip WHERE c0 > 0 AND c1 > 0
),

/* -------- 三段互斥输出（天然 canonical，不需要 consolidate） */

/* (1) ΔR|K11：只透传那些“一直匹配”的 key 上的 ΔR，action 保持不变 */
part1 AS (
  SELECT dR.*
  FROM dR
  JOIN K_11 USING (k)
),

/* (2) +R'|Kup：从不匹配->匹配，R_to 中这些 key 的行整体变成新增 */
part2 AS (
  SELECT R_to.*, +1 AS action
  FROM R_to
  JOIN K_up USING (k)
),

/* (3) -R|Kdown：从匹配->不匹配，R_from 中这些 key 的行整体变成删除 */
part3 AS (
  SELECT R_from.*, -1 AS action
  FROM R_from
  JOIN K_down USING (k)
)

SELECT * FROM part1
UNION ALL
SELECT * FROM part2
UNION ALL
SELECT * FROM part3;
```

## Left Outer Join
```
WITH 
-- ==========================================
-- 步骤 1：基于 S_d 计算边界变迁 (复用逻辑)
-- ==========================================
cte_s_delta_agg AS (
    SELECT join_key, SUM(_delta_op) AS delta_cnt FROM S_d GROUP BY join_key
),
cte_s_to_cnt AS (
    SELECT S.join_key, COUNT(*) AS to_cnt FROM S_to AS S
    LEFT SEMI JOIN cte_s_delta_agg AS D ON S.join_key = D.join_key
    GROUP BY S.join_key
),
cte_s_transitions AS (
    SELECT 
        D.join_key,
        CASE 
            WHEN (COALESCE(T.to_cnt, 0) - D.delta_cnt) <= 0 AND COALESCE(T.to_cnt, 0) > 0 THEN 'T_01' 
            WHEN (COALESCE(T.to_cnt, 0) - D.delta_cnt) > 0 AND COALESCE(T.to_cnt, 0) <= 0 THEN 'T_10' 
            ELSE 'UNCHANGED' 
        END AS trans_type
    FROM cte_s_delta_agg D
    LEFT JOIN cte_s_to_cnt T ON D.join_key = T.join_key
),

-- ==========================================
-- 步骤 2：生成 Left Outer Join 的四个正交增量分支
-- ==========================================

-- 分支 A: R_d 的直接 LOJ (处理所有的 R 端增量)
-- S_to 包含最新状态，自动处理匹配与不匹配产生的 NULL
cte_out_rd_loj AS (
    SELECT 
        R.col1 AS r_col1, R.col2 AS r_col2, 
        S.col1 AS s_col1, S.col2 AS s_col2, 
        R._delta_op
    FROM R_d AS R
    LEFT OUTER JOIN S_to AS S ON R.join_key = S.join_key
),

-- 分支 B: R_from 与 S_d 的 Inner Join (处理 S 端数量变化，如 1->2 或 2->1)
cte_out_inner_sd AS (
    SELECT 
        R.col1 AS r_col1, R.col2 AS r_col2, 
        S.col1 AS s_col1, S.col2 AS s_col2, 
        S._delta_op -- 继承 S_d 的操作符
    FROM R_from AS R
    INNER JOIN S_d AS S ON R.join_key = S.join_key
),

-- 分支 C: S 变迁 T_10 导致匹配变为空，补偿输出 NULL 行 (Insert)
cte_out_r_from_t10_insert AS (
    SELECT 
        R.col1 AS r_col1, R.col2 AS r_col2, 
        NULL AS s_col1, NULL AS s_col2, -- 强行填充 NULL
        1 AS _delta_op
    FROM R_from AS R
    LEFT SEMI JOIN cte_s_transitions AS T ON R.join_key = T.join_key AND T.trans_type = 'T_10'
),

-- 分支 D: S 变迁 T_01 导致空变为匹配，撤销原有的 NULL 行 (Delete)
cte_out_r_from_t01_delete AS (
    SELECT 
        R.col1 AS r_col1, R.col2 AS r_col2, 
        NULL AS s_col1, NULL AS s_col2, -- 强行填充 NULL
        -1 AS _delta_op
    FROM R_from AS R
    LEFT SEMI JOIN cte_s_transitions AS T ON R.join_key = T.join_key AND T.trans_type = 'T_01'
)

-- ==========================================
-- 步骤 3：合并输出
-- ==========================================
SELECT * FROM cte_out_rd_loj
UNION ALL
SELECT * FROM cte_out_inner_sd
UNION ALL
SELECT * FROM cte_out_r_from_t10_insert
UNION ALL
SELECT * FROM cte_out_r_from_t01_delete;
```

## Group By

### Retractable Agg Functions

```
WITH 
-- 1. 对增量数据进行局部聚合 (提取受影响的 keys 并计算 delta 净值)
cte_delta_agg AS (
    SELECT 
        key, 
        SUM(v * _delta_op) AS delta_sum,
        SUM(_delta_op) AS delta_cnt
    FROM T_d
    GROUP BY key
),

-- 2. 探测 T_to 获取最新状态 (利用 HashJoin/SemiJoin 向上推 Runtime Filter)
cte_to_agg AS (
    SELECT 
        T.key, 
        SUM(T.v) AS to_sum,
        COUNT(T.v) AS to_cnt
    FROM T_to AS T
    LEFT SEMI JOIN cte_delta_agg AS D ON T.key = D.key
    GROUP BY T.key
),

-- 3. 核心：通过代数逆运算反推历史状态 (Full Join 应对 Key 被完全 Delete 的情况)
cte_transition AS (
    SELECT 
        COALESCE(N.key, D.key) AS key,
        -- 新状态 (如果完全被删，则新状态的 sum/cnt 为 0)
        COALESCE(N.to_sum, 0) AS to_sum,
        COALESCE(N.to_cnt, 0) AS to_cnt,
        -- 旧状态 = 新状态 - 增量净值
        (COALESCE(N.to_sum, 0) - D.delta_sum) AS from_sum,
        (COALESCE(N.to_cnt, 0) - D.delta_cnt) AS from_cnt
    FROM cte_delta_agg AS D
    LEFT JOIN cte_to_agg AS N ON D.key = N.key
)

-- 4. 输出 -Old 与 +New 
-- (可附加过滤条件：剔除 from_sum = to_sum 且 from_cnt = to_cnt 的无变化行)
SELECT key, from_sum AS sum_v, from_cnt AS cnt_v, -1 AS _delta_op FROM cte_transition WHERE from_cnt > 0
UNION ALL
SELECT key, to_sum AS sum_v, to_cnt AS cnt_v, 1 AS _delta_op FROM cte_transition WHERE to_cnt > 0;
```

### Non Retractable Agg Functions

```
WITH 
-- 1. 提取受影响的 keys (去重)
cte_delta_keys AS (
    SELECT DISTINCT key FROM T_d
),

-- 2. 重算历史版本状态 (RF 下推至 T_from)
cte_from_agg AS (
    SELECT T.key, MAX(T.v) AS from_max
    FROM T_from AS T
    LEFT SEMI JOIN cte_delta_keys AS D ON T.key = D.key
    GROUP BY T.key
),

-- 3. 重算最新版本状态 (RF 下推至 T_to)
cte_to_agg AS (
    SELECT T.key, MAX(T.v) AS to_max
    FROM T_to AS T
    LEFT SEMI JOIN cte_delta_keys AS D ON T.key = D.key
    GROUP BY T.key
),

-- 4. 状态对比
cte_transition AS (
    SELECT 
        COALESCE(O.key, N.key) AS key,
        O.from_max,
        N.to_max
    FROM cte_from_agg AS O
    FULL OUTER JOIN cte_to_agg AS N ON O.key = N.key
    -- 核心剪枝：仅保留 MAX 值真正发生变化的记录
    WHERE O.from_max IS DISTINCT FROM N.to_max
)

-- 5. 输出 -Old 与 +New
SELECT key, from_max AS max_v, -1 AS _delta_op FROM cte_transition WHERE from_max IS NOT NULL
UNION ALL
SELECT key, to_max AS max_v, 1 AS _delta_op FROM cte_transition WHERE to_max IS NOT NULL;
```

## Window Operator
```
WITH 
-- 1. 提取受影响的分区键 (Partition Keys)
cte_delta_partitions AS (
    SELECT DISTINCT partition_key FROM T_d
),

-- 2. 裁剪历史版本数据并计算旧窗口值
-- 依赖 Runtime Filter 将 partition_key 下推至 T_from 的 Scan 层
cte_window_from AS (
    SELECT 
        T.uk, 
        T.partition_key, 
        T.order_key, 
        T.v,
        WINDOW_FUNC(T.v) OVER (PARTITION BY T.partition_key ORDER BY T.order_key FRAME_DEF) AS win_val
    FROM T_from AS T
    LEFT SEMI JOIN cte_delta_partitions AS D ON T.partition_key = D.partition_key
),

-- 3. 裁剪最新版本数据并计算新窗口值
-- 依赖 Runtime Filter 将 partition_key 下推至 T_to 的 Scan 层
cte_window_to AS (
    SELECT 
        T.uk, 
        T.partition_key, 
        T.order_key, 
        T.v,
        WINDOW_FUNC(T.v) OVER (PARTITION BY T.partition_key ORDER BY T.order_key FRAME_DEF) AS win_val
    FROM T_to AS T
    LEFT SEMI JOIN cte_delta_partitions AS D ON T.partition_key = D.partition_key
),

-- 4. 通过 Unique Key 对齐多版本，提取发生突变的增量
cte_window_diff AS (
    SELECT 
        COALESCE(O.uk, N.uk) AS uk,
        COALESCE(O.partition_key, N.partition_key) AS partition_key,
        COALESCE(O.order_key, N.order_key) AS order_key,
        O.win_val AS from_win_val,
        N.win_val AS to_win_val
    FROM cte_window_from AS O
    FULL OUTER JOIN cte_window_to AS N ON O.uk = N.uk
    -- 核心：只保留被删除、被新增、或者窗口函数计算结果发生改变的记录
    WHERE O.win_val IS DISTINCT FROM N.win_val
       OR O.uk IS NULL 
       OR N.uk IS NULL
)

-- 5. 格式化输出 -Old 与 +New 的 Delta 流
SELECT uk, partition_key, order_key, from_win_val AS win_val, -1 AS _delta_op 
FROM cte_window_diff WHERE from_win_val IS NOT NULL
UNION ALL
SELECT uk, partition_key, order_key, to_win_val AS win_val, 1 AS _delta_op 
FROM cte_window_diff WHERE to_win_val IS NOT NULL;
```

## Set Operator

### Union
```
WITH 
-- 1. 底层 Union All 增量
cte_union_all_delta AS (
    SELECT * FROM R_d
    UNION ALL 
    SELECT * FROM S_d
),

-- 2. 对增量数据进行局部聚合 (Key 为所有列)
cte_delta_agg AS (
    SELECT 
        col1, col2, 
        SUM(_delta_op) AS delta_cnt
    FROM cte_union_all_delta
    GROUP BY col1, col2
),

-- 3. 探测最新状态 T_to (T_to 等价于 R_to UNION ALL S_to，但更优的做法是探测包含去重结果的 MV 本身，或分别探测 R_to 和 S_to)
-- 为保持与单一输入一致，假设我们探测全局最新视图 V_to
cte_to_agg AS (
    SELECT 
        V.col1, V.col2,
        COUNT(*) AS to_cnt
    FROM V_to AS V
    LEFT SEMI JOIN cte_delta_agg AS D ON V.col1 = D.col1 AND V.col2 = D.col2
    GROUP BY V.col1, V.col2
),

-- 4. 状态差分与变迁提取 (逻辑同 Group By)
cte_transition AS (
    SELECT 
        COALESCE(N.col1, D.col1) AS col1,
        COALESCE(N.col2, D.col2) AS col2,
        COALESCE(N.to_cnt, 0) AS to_cnt,
        (COALESCE(N.to_cnt, 0) - D.delta_cnt) AS from_cnt
    FROM cte_delta_agg AS D
    LEFT JOIN cte_to_agg AS N ON D.col1 = N.col1 AND D.col2 = N.col2
)

-- 5. 输出边界变迁 (0 -> 1 产生 Insert, 1 -> 0 产生 Delete)
SELECT col1, col2, -1 AS _delta_op FROM cte_transition WHERE from_cnt > 0 AND to_cnt = 0
UNION ALL
SELECT col1, col2, 1 AS _delta_op FROM cte_transition WHERE from_cnt = 0 AND to_cnt > 0;
```

### Except


Except Distinct本质上是全部列的anti join，其展开跟left anti join算法一致：
```
WITH 
-- 1. S_d 的行级变迁监控 (所有列作为分组键)
cte_s_delta_agg AS (
    SELECT col1, col2, SUM(_delta_op) AS delta_cnt 
    FROM S_d GROUP BY col1, col2
),
cte_s_to_cnt AS (
    SELECT S.col1, S.col2, COUNT(*) AS to_cnt FROM S_to AS S
    LEFT SEMI JOIN cte_s_delta_agg AS D ON S.col1 = D.col1 AND S.col2 = D.col2
    GROUP BY S.col1, S.col2
),
cte_s_transitions AS (
    SELECT 
        D.col1, D.col2,
        CASE 
            WHEN (COALESCE(T.to_cnt, 0) - D.delta_cnt) <= 0 AND COALESCE(T.to_cnt, 0) > 0 THEN 'T_01' 
            WHEN (COALESCE(T.to_cnt, 0) - D.delta_cnt) > 0 AND COALESCE(T.to_cnt, 0) <= 0 THEN 'T_10' 
            ELSE 'UNCHANGED' 
        END AS trans_type
    FROM cte_s_delta_agg D
    LEFT JOIN cte_s_to_cnt T ON D.col1 = T.col1 AND D.col2 = T.col2
),

-- 2. 分支 A: R_d 直接 Anti Join S_to
cte_out_rd AS (
    SELECT R.* FROM R_d AS R
    WHERE NOT EXISTS (
        SELECT 1 FROM S_to AS S WHERE S.col1 = R.col1 AND S.col2 = R.col2
    )
),

-- 3. 分支 B: S 行级 T_01 导致 R_from 的历史数据被隐藏 (-1)
cte_out_r_from_delete AS (
    SELECT R.*, -1 AS _override_delta_op
    FROM R_from AS R
    LEFT SEMI JOIN cte_s_transitions AS T 
      ON R.col1 = T.col1 AND R.col2 = T.col2 AND T.trans_type = 'T_01'
),

-- 4. 分支 C: S 行级 T_10 导致 R_from 的历史数据重新暴露 (+1)
cte_out_r_from_insert AS (
    SELECT R.*, 1 AS _override_delta_op
    FROM R_from AS R
    LEFT SEMI JOIN cte_s_transitions AS T 
      ON R.col1 = T.col1 AND R.col2 = T.col2 AND T.trans_type = 'T_10'
)

-- 5. 合并输出
SELECT col1, col2, _delta_op FROM cte_out_rd
UNION ALL
SELECT col1, col2, _override_delta_op AS _delta_op FROM cte_out_r_from_delete
UNION ALL
SELECT col1, col2, _override_delta_op AS _delta_op FROM cte_out_r_from_insert;
```

Except All
```
WITH 
-- 1. 提取受影响的行并计算增量计数 (L_d 和 R_d)
cte_delta_agg AS (
    SELECT 
        col1, col2, 
        SUM(CASE WHEN source = 'L' THEN _delta_op ELSE 0 END) AS l_delta_cnt,
        SUM(CASE WHEN source = 'R' THEN _delta_op ELSE 0 END) AS r_delta_cnt
    FROM (
        SELECT col1, col2, _delta_op, 'L' AS source FROM L_d
        UNION ALL
        SELECT col1, col2, _delta_op, 'R' AS source FROM R_d
    ) t
    GROUP BY col1, col2
),

-- 2. 探测最新状态 (利用 RF 下推)
cte_to_agg AS (
    SELECT 
        D.col1, D.col2,
        (SELECT COUNT(*) FROM L_to WHERE L_to.col1 = D.col1 AND L_to.col2 = D.col2) AS l_to_cnt,
        (SELECT COUNT(*) FROM R_to WHERE R_to.col1 = D.col1 AND R_to.col2 = D.col2) AS r_to_cnt
    FROM cte_delta_agg D
),

-- 3. 反推历史状态并计算 DISTINCT 输出差值
cte_transition AS (
    SELECT 
        D.col1, D.col2,
        T.l_to_cnt, T.r_to_cnt,
        (T.l_to_cnt - D.l_delta_cnt) AS l_from_cnt,
        (T.r_to_cnt - D.r_delta_cnt) AS r_from_cnt
    FROM cte_delta_agg D
    JOIN cte_to_agg T ON D.col1 = T.col1 AND D.col2 = T.col2
),

-- 4. 应用 DISTINCT 判定逻辑
cte_calc_diff AS (
    SELECT 
        col1, col2,
        -- F_to
        CASE WHEN l_to_cnt > 0 AND r_to_cnt = 0 THEN 1 ELSE 0 END AS out_to,
        -- F_from
        CASE WHEN l_from_cnt > 0 AND r_from_cnt = 0 THEN 1 ELSE 0 END AS out_from
    FROM cte_transition
)

-- 5. 输出非零的增量操作
SELECT col1, col2, (out_to - out_from) AS _delta_op 
FROM cte_calc_diff 
WHERE (out_to - out_from) != 0;
```