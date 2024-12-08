ALTER TABLE customer SET ("unique_constraints" = "c_custkey");
ALTER TABLE part SET ("unique_constraints" = "p_partkey");
ALTER TABLE supplier SET ("unique_constraints" = "s_suppkey");
ALTER TABLE dates SET ("unique_constraints" = "d_datekey");
ALTER TABLE lineorder SET ("foreign_key_constraints" = "(lo_custkey) REFERENCES customer(c_custkey);(lo_partkey) REFERENCES part(p_partkey);(lo_suppkey) REFERENCES supplier(s_suppkey);(lo_orderdate) REFERENCES dates(d_datekey)");
