"""文档加载与切分"""

import hashlib
from pathlib import Path
from typing import Optional

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger


class DocumentLoader:
    """企业文档加载器

    支持:
    - Markdown(.md)
    - PDF(.pdf)
    - Word(.docx)
    - 纯文本(.txt)
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separators: Optional[list[str]] = None,
    ):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators or ["\n\n", "\n", "。", "!", "?", ".", " ", ""],
            length_function=len,
        )

    def load_file(self, file_path: str | Path) -> list[Document]:
        """加载单个文件"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")

        suffix = path.suffix.lower()
        loader_map = {
            ".md": self._load_markdown,
            ".txt": self._load_text,
            ".pdf": self._load_pdf,
            ".docx": self._load_docx,
        }

        loader = loader_map.get(suffix)
        if loader is None:
            raise ValueError(f"不支持的文件格式: {suffix}")

        docs = loader(path)
        logger.info(f"加载文件 {path.name}: {len(docs)} 个文档块")
        return docs

    def load_directory(self, dir_path: str | Path) -> list[Document]:
        """加载目录下所有支持的文件"""
        path = Path(dir_path)
        if not path.exists():
            raise FileNotFoundError(f"目录不存在: {path}")

        all_docs = []
        for ext in ["*.md", "*.txt", "*.pdf", "*.docx"]:
            for file in path.rglob(ext):
                try:
                    docs = self.load_file(file)
                    all_docs.extend(docs)
                except Exception as e:
                    logger.warning(f"加载文件失败 {file}: {e}")

        logger.info(f"从 {path} 加载共 {len(all_docs)} 个文档块")
        return all_docs

    def split_documents(self, docs: list[Document]) -> list[Document]:
        """切分文档"""
        chunks = self.splitter.split_documents(docs)
        logger.info(f"切分为 {len(chunks)} 个块")
        return chunks

    # ============ 私有方法:各格式加载器 ============

    def _load_markdown(self, path: Path) -> list[Document]:
        from langchain_community.document_loaders import TextLoader

        loader = TextLoader(str(path), encoding="utf-8")
        return loader.load()

    def _load_text(self, path: Path) -> list[Document]:
        from langchain_community.document_loaders import TextLoader

        loader = TextLoader(str(path), encoding="utf-8")
        return loader.load()

    def _load_pdf(self, path: Path) -> list[Document]:
        from langchain_community.document_loaders import PyPDFLoader

        loader = PyPDFLoader(str(path))
        return loader.load()

    def _load_docx(self, path: Path) -> list[Document]:
        from langchain_community.document_loaders import Docx2txtLoader

        loader = Docx2txtLoader(str(path))
        return loader.load()

    @staticmethod
    def compute_hash(content: str) -> str:
        """计算内容哈希(用于去重)"""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
