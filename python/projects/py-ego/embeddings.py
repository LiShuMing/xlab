# embeddings.py
import os
import sys
import re
import hashlib
import numpy as np

# 抑制 HuggingFace 和 transformers 的日志
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'

# 先设置日志级别再导入其他库
import logging
for logger_name in ['sentence_transformers', 'transformers', 'urllib3', 'httpcore', 'openai', 
                    'huggingface_hub', 'httpx', 'tqdm', 'torch']:
    logging.getLogger(logger_name).setLevel(logging.ERROR)
    logging.getLogger(logger_name).disabled = True

from config import USE_LOCAL_EMBEDDING, EMBEDDING_MODEL, get_openai_client

# 本地 embedding 模型缓存
_local_embedder = None


def _clean_text(text):
    """
    清理文本，移除 surrogate 字符和其他可能导致编码错误的字符
    """
    if text is None:
        return ""
    
    # 转换为字符串
    text = str(text)
    
    # 移除 surrogate 字符 (U+D800-U+DFFF)
    # 这些字符在 UTF-8 中是无效的
    text = text.encode('utf-8', 'ignore').decode('utf-8')
    
    # 移除控制字符（保留正常的换行和制表符）
    text = ''.join(char for char in text if char == '\n' or char == '\t' or (ord(char) >= 32 and ord(char) <= 0x10FFFF))
    
    # 清理多余空白
    text = text.strip()
    
    return text if text else "empty"


def _get_local_embedder():
    """获取本地 embedding 模型（延迟加载）"""
    global _local_embedder
    if _local_embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            print(f"[Embedding] 正在加载本地模型: {EMBEDDING_MODEL}...")
            # 禁用进度条输出
            _local_embedder = SentenceTransformer(EMBEDDING_MODEL, device='cpu')
            print(f"[Embedding] 模型加载完成")
        except ImportError:
            raise ImportError(
                "sentence-transformers 未安装，请运行: pip install sentence-transformers\n"
                "或使用简单的哈希 embedding（用于测试）: export USE_SIMPLE_EMBEDDING=true"
            )
    return _local_embedder


def _simple_hash_embedding(text, dim=512):
    """
    简单的哈希 embedding（仅用于测试，不具备语义相似性）
    当 sentence-transformers 不可用时作为降级方案
    """
    # 清理文本
    text = _clean_text(text)
    
    # 使用多个哈希函数生成固定维度的向量
    np.random.seed(int(hashlib.md5(text.encode('utf-8')).hexdigest(), 16) % (2**32))
    vec = np.random.randn(dim)
    # 归一化
    vec = vec / (np.linalg.norm(vec) + 1e-8)
    return vec.astype(np.float32)


def get_embedding(text):
    """
    获取文本的 embedding 向量
    优先使用本地模型（默认），如果配置了远程 API 则使用远程
    """
    # 清理文本
    text = _clean_text(text)
    
    # 检查是否使用简单哈希 embedding（测试用途）
    if os.getenv("USE_SIMPLE_EMBEDDING", "false").lower() == "true":
        return _simple_hash_embedding(text)
    
    try:
        if USE_LOCAL_EMBEDDING:
            # 使用本地模型
            try:
                embedder = _get_local_embedder()
                # 使用 normalize_embeddings 避免某些编码问题
                embedding = embedder.encode(
                    text, 
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=False
                )
                return embedding.astype(np.float32)
            except ImportError as e:
                print(f"[Embedding Warning] {e}")
                print("[Embedding] 使用简单的哈希 embedding 作为替代（仅用于测试）")
                return _simple_hash_embedding(text)
            except Exception as e:
                print(f"[Embedding Error] {e}")
                return _simple_hash_embedding(text)
        else:
            # 使用远程 API（OpenAI 兼容格式）
            client = get_openai_client()
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text
            )
            return np.array(response.data[0].embedding, dtype=np.float32)
    except Exception as e:
        print(f"[Embedding Error] {e}")
        # 降级到简单哈希
        return _simple_hash_embedding(text)


def get_embeddings_batch(texts, batch_size=32):
    """
    批量获取文本的 embedding 向量（更高效）
    """
    if not texts:
        return []
    
    # 清理所有文本
    texts = [_clean_text(t) for t in texts]
    
    # 检查是否使用简单哈希 embedding
    if os.getenv("USE_SIMPLE_EMBEDDING", "false").lower() == "true":
        return [_simple_hash_embedding(t) for t in texts]
    
    try:
        if USE_LOCAL_EMBEDDING:
            try:
                embedder = _get_local_embedder()
                embeddings = embedder.encode(
                    texts, 
                    convert_to_numpy=True,
                    batch_size=batch_size,
                    show_progress_bar=False,
                    normalize_embeddings=True
                )
                return [e.astype(np.float32) for e in embeddings]
            except ImportError:
                # 降级到简单哈希
                return [_simple_hash_embedding(t) for t in texts]
            except Exception as e:
                print(f"[Batch Embedding Error] {e}")
                return [_simple_hash_embedding(t) for t in texts]
        else:
            client = get_openai_client()
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=texts
            )
            return [np.array(d.embedding, dtype=np.float32) for d in response.data]
    except Exception as e:
        print(f"[Batch Embedding Error] {e}")
        # 降级到简单哈希
        return [_simple_hash_embedding(t) for t in texts]
