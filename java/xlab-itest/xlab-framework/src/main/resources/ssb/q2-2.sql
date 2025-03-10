SELECT
  SUM(lo_revenue),
  d_year,
  p_brand
FROM 
  lineorder,
  dates,
  part,
  supplier
WHERE 
  lo_orderdate = d_datekey
  AND lo_partkey = p_partkey
  AND lo_suppkey = s_suppkey
  AND p_brand BETWEEN 'MFGR#2221' AND 'MFGR#2228'
  AND s_region = 'ASIA'
GROUP BY 
  d_year,
  p_brand
ORDER BY 
  d_year,
  p_brand;
