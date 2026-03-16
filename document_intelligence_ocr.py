"""Document Intelligence を使用した OCR 処理モジュール。"""

import time
from dataclasses import dataclass, field
from pathlib import Path

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    AnalyzeDocumentRequest,
    AnalyzeResult,
    DocumentPage,
)
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential


@dataclass
class DIWordDetail:
    """Document Intelligence で検出された単語情報。"""

    text: str
    confidence: float
    polygon: list[float] = field(default_factory=list)


@dataclass
class DIPageResult:
    """Document Intelligence のページ単位の結果。"""

    page_number: int
    width: float | None
    height: float | None
    unit: str | None
    lines: list[str]
    words: list[DIWordDetail]


@dataclass
class DIResult:
    """Document Intelligence の OCR 全体結果。"""

    full_text: str
    pages: list[DIPageResult]
    elapsed_seconds: float
    model_id: str


def create_client(endpoint: str, key: str | None = None) -> DocumentIntelligenceClient:
    """Document Intelligence クライアントを作成する。"""
    if key:
        credential = AzureKeyCredential(key)
    else:
        credential = DefaultAzureCredential()
    return DocumentIntelligenceClient(endpoint=endpoint, credential=credential)


def analyze_document(
    client: DocumentIntelligenceClient,
    file_path: str,
    model_id: str = "prebuilt-read",
) -> DIResult:
    """ドキュメントを Document Intelligence で分析する。

    Args:
        client: Document Intelligence クライアント
        file_path: 分析するファイルのパス
        model_id: 使用するモデル ID (デフォルト: prebuilt-read)

    Returns:
        DIResult: 分析結果
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")

    with open(path, "rb") as f:
        file_bytes = f.read()

    content_type = _get_content_type(path.suffix.lower())

    start_time = time.time()

    poller = client.begin_analyze_document(
        model_id=model_id,
        body=file_bytes,
        content_type=content_type,
    )
    result: AnalyzeResult = poller.result()

    elapsed = time.time() - start_time

    pages = _parse_pages(result)
    full_text = result.content or ""

    return DIResult(
        full_text=full_text,
        pages=pages,
        elapsed_seconds=elapsed,
        model_id=model_id,
    )


def _get_content_type(suffix: str) -> str:
    """ファイル拡張子からコンテンツタイプを返す。"""
    mapping = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".heif": "image/heif",
    }
    ct = mapping.get(suffix)
    if ct is None:
        raise ValueError(f"サポートされていないファイル形式: {suffix}")
    return ct


def _parse_pages(result: AnalyzeResult) -> list[DIPageResult]:
    """AnalyzeResult からページ情報を抽出する。"""
    pages: list[DIPageResult] = []
    if not result.pages:
        return pages

    for page in result.pages:
        lines = []
        words = []

        if page.lines:
            for line in page.lines:
                lines.append(line.content)

        if page.words:
            for word in page.words:
                words.append(
                    DIWordDetail(
                        text=word.content,
                        confidence=word.confidence or 0.0,
                        polygon=list(word.polygon) if word.polygon else [],
                    )
                )

        pages.append(
            DIPageResult(
                page_number=page.page_number or 0,
                width=page.width,
                height=page.height,
                unit=page.unit,
                lines=lines,
                words=words,
            )
        )

    return pages
