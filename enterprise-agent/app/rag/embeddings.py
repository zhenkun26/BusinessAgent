"""Embedding 服务(支持 OpenAI 与本地 HuggingFace)

默认本地 bge-m3(1024 维),无需 API Key。
切换 OpenAI 时只需改 .env:EMBEDDING_PROVIDER=openai。

开发期可用 EMBEDDING_PROVIDER=mock 跑通逻辑(纯 Python,无 torch 依赖)。
MockEmbeddings 基于字符 n-gram + 哈希签名,对中文关键词/数字有基本匹配能力,
适合 W4 代码逻辑验证与小规模评测;不可用于生产(无真实语义理解)。
"""

import hashlib
import math
import os
import re
from typing import Optional

from langchain_core.embeddings import Embeddings
from loguru import logger

from app.config import get_settings


class EmbeddingService:
    """Embedding 服务封装"""

    def __init__(self):
        self._settings = get_settings()
        self._embeddings: Optional[Embeddings] = None

    def get_embeddings(self) -> Embeddings:
        """获取 Embeddings 实例(单例)"""
        if self._embeddings is not None:
            return self._embeddings

        provider = self._settings.embedding_provider.lower()

        if provider == "openai":
            # OpenAI 兼容协议(text-embedding-3-small 等)
            from langchain_openai import OpenAIEmbeddings

            self._embeddings = OpenAIEmbeddings(
                model=self._settings.embedding_model,
                api_key=self._settings.openai_api_key,
                base_url=self._settings.openai_base_url,
            )
            logger.info(f"使用 OpenAI Embeddings: {self._settings.embedding_model}")

        elif provider == "local":
            # 本地 HuggingFace Embedding(默认 BAAI/bge-m3)
            # 设置 HF_HOME,避免每次容器启动重新下载
            if self._settings.hf_home:
                os.environ["HF_HOME"] = self._settings.hf_home
                os.environ["SENTENCE_TRANSFORMERS_HOME"] = self._settings.hf_home

            from langchain_huggingface import HuggingFaceEmbeddings

            # 模型路径处理:如果是本地目录(如 D:/models/bge-m3),直接用;
            # 如果是 HuggingFace repo id(如 BAAI/bge-m3),则从 hub 下载
            model_path = self._settings.embedding_model
            from pathlib import Path

            if Path(model_path).exists():
                # 本地路径,直接加载(不走 hub)
                logger.info(f"检测到本地模型路径: {model_path}")
                cache_folder = None
            else:
                # HuggingFace repo id,走 hub(可能触发下载)
                cache_folder = self._settings.hf_home or None

            self._embeddings = HuggingFaceEmbeddings(
                model_name=model_path,
                cache_folder=cache_folder,
                model_kwargs={"device": _detect_device()},
                encode_kwargs={"normalize_embeddings": True},  # bge 系列建议归一化
            )
            logger.info(
                f"使用本地 HuggingFace Embeddings: {model_path}, "
                f"device={_detect_device()}"
            )

        elif provider == "mock":
            # 纯 Python Mock(开发期验证逻辑用,无语义能力,命中率会很低)
            self._embeddings = MockEmbeddings(dim=self._settings.embedding_dim)
            logger.warning(
                f"使用 Mock Embeddings(dim={self._settings.embedding_dim}),"
                "仅用于代码逻辑验证,无真实语义检索能力"
            )

        else:
            raise ValueError(f"未知 embedding_provider: {provider}")

        return self._embeddings


def _detect_device() -> str:
    """检测可用设备;settings.local_model_device 可强制指定(cuda/cpu)"""
    from app.config import get_settings

    forced = (get_settings().local_model_device or "auto").lower()
    if forced in ("cuda", "cpu", "mps"):
        return forced
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception as e:  # noqa: BLE001
        logger.debug(f"torch 检测失败,回退 CPU: {e}")
    return "cpu"


# ============ Mock Embeddings(开发期,无 torch 依赖) ============


class MockEmbeddings(Embeddings):
    """基于字符 n-gram + 哈希签名的 Mock Embedding

    原理:
    1. 文本切分为字符 n-gram(中文 unigram/bigram,英文/数字 token)
    2. 每个 n-gram 用 MD5 哈希到 [0, dim) 的某个维度
    3. 该维度累加权重(带 IDF 近似:常见字符权重低)
    4. L2 归一化,使余弦相似度 = n-gram 重叠度

    局限:
    - 无真正语义理解(同义词不可识别)
    - 但对包含明确数字/术语的查询(如 "24小时"、"800元")命中率尚可
    - 仅用于 W4 代码逻辑验证,不可用于生产
    """

    # 中文停用词(权重折扣)
    _STOP_CHARS = set(" 的了是在我有和就不人都一上也很好到说要去你会着没有看好自己这那")

    def __init__(self, dim: int = 1024):
        self._dim = dim
        # 词频统计(用于 IDF 近似,首次 embed 时填充)
        self._doc_freq: dict[str, int] = {}
        self._total_docs = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量向量化文档"""
        # 更新文档频率统计(IDF 近似)
        self._total_docs += 1
        for text in texts:
            tokens = self._tokenize(text)
            unique = set(tokens)
            for tok in unique:
                self._doc_freq[tok] = self._doc_freq.get(tok, 0) + 1
        return [self._embed_one(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """向量化查询(不更新文档频率)"""
        return self._embed_one(text)

    def _embed_one(self, text: str) -> list[float]:
        """单个文本向量化:n-gram hashing + L2 归一化"""
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self._dim

        vec = [0.0] * self._dim
        for tok in tokens:
            # IDF 近似权重:未见过的 token 权重 1.0,常见 token 权重递减
            df = self._doc_freq.get(tok, 0)
            if self._total_docs > 0 and df > 0:
                idf = math.log((self._total_docs + 1) / df) + 1.0
            else:
                idf = 1.0
            # 停用字折扣
            if any(ch in self._STOP_CHARS for ch in tok):
                idf *= 0.3
            # 数字/英文术语加权(对政策类问答很关键)
            if any(ch.isdigit() for ch in tok):
                idf *= 2.0

            # 哈希到 dim 维
            h = hashlib.md5(tok.encode("utf-8")).digest()
            # 取 8 字节作为两个 uint32 索引(增加碰撞分散度)
            idx1 = int.from_bytes(h[:4], "little") % self._dim
            idx2 = int.from_bytes(h[4:8], "little") % self._dim
            sign = 1.0 if (h[8] & 1) == 0 else -1.0
            vec[idx1] += sign * idf
            vec[idx2] += sign * idf * 0.5

        # L2 归一化
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """中文/英文/数字 n-gram 切分"""
        if not text:
            return []
        tokens: list[str] = []
        # 英文 + 数字 token
        for m in re.finditer(r"[A-Za-z0-9]+", text):
            tok = m.group().lower()
            if len(tok) >= 2:
                tokens.append(tok)
            # 也把纯数字串单独加(如 "24"、"800")
            if tok.isdigit():
                tokens.append(tok)
        # 中文 unigram + bigram
        for seg in re.findall(r"[\u4e00-\u9fa5]+", text):
            if len(seg) >= 1:
                for ch in seg:
                    tokens.append(ch)
            if len(seg) >= 2:
                for i in range(len(seg) - 1):
                    tokens.append(seg[i : i + 2])
            if len(seg) >= 3:
                # trigram 只取关键片段(避免爆炸)
                for i in range(0, len(seg) - 2, 2):
                    tokens.append(seg[i : i + 3])
        return tokens


# 全局单例
_embedding_service: Optional[EmbeddingService] = None


def get_embeddings() -> Embeddings:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service.get_embeddings()
