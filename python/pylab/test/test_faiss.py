import pandas as pd
import pytest
import faiss
import numpy as np

def get_data(d: int, nb: int) -> np.ndarray:
    np.random.seed(123)
    data = np.random.random((nb, d)).astype('float32')
    print(data)
    return data

def test_basic_index():
    print(faiss.__version__)  

    d = 12  # 向量维度
    nb = 10  # 数据库向量数量
    data = get_data(d, nb)

    # 创建索引
    index = faiss.IndexFlatL2(d)  # L2 距离
    print("Is trained:", index.is_trained)  # 对于 `IndexFlatL2`，始终为 True

    # 添加向量到索引
    index.add(data)
    print("Number of vectors in the index:", index.ntotal)

    # 查询
    query = np.random.random((5, d)).astype('float32')  # 查询向量
    print("Query:", query)
    k = 3  # 查询最近的 3 个邻居
    distances, indices = index.search(query, k)

    print("Distances:", distances)
    print("Indices:", indices)

def test_basic_ivflat():
    d = 12  # 向量维度
    nb = 10  # 数据库向量数量
    data = get_data(d, nb)
    # 创建索引
    nlist = nb # 聚类中心数量
    quantizer = faiss.IndexFlatL2(d)  # 基础量化器
    index_ivf = faiss.IndexIVFFlat(quantizer, d, nlist, faiss.METRIC_L2)

    # 训练索引
    index_ivf.train(data)  # 训练阶段
    index_ivf.add(data)    # 添加向量

    # 查询
    k = 3
    query = np.random.random((5, d)).astype('float32')  # 查询向量
    print("Query:", query)

    index_ivf.nprobe = 10  # 查询时的簇数量
    distances, indices = index_ivf.search(query, k)
    print("Distances:", distances)
    print("Indices:", indices)

def test_basic_iqflat():
    d = 12  # 向量维度
    nb = 256
    data = get_data(d, nb)

    nlist = nb
    m = d              # PQ 的子向量数量
    quantizer = faiss.IndexFlatL2(d)  # 用于初始粗聚类的 L2 索引
    index_ivfpq = faiss.IndexIVFPQ(quantizer, d, nlist, m, 8)  # 8 位编码
    index_ivfpq.train(data)
    index_ivfpq.add(data)

    # 查询
    k = 3
    query = np.random.random((5, d)).astype('float32')  # 查询向量
    print("Query:", query)
    distances, indices = index_ivfpq.search(query, k)
    print("Distances:", distances)
    print("Indices:", indices)