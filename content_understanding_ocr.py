"""Content Understanding を使用した OCR 処理モジュール。

Content Understanding は REST API 経由で利用する。
アナライザーを作成し、ドキュメントを分析して結果を取得する。
"""

import base64
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.core.pipeline.policies import (
    BearerTokenCredentialPolicy,
    HeadersPolicy,
    RetryPolicy,
)
from azure.core.rest import HttpRequest, HttpResponse
from azure.core.pipeline import Pipeline
from azure.core.pipeline.transport import RequestsTransport
from azure.identity import DefaultAzureCredential


API_VERSION = "2025-11-01"


@dataclass
class CUWordDetail:
    """Content Understanding で検出された単語情報。"""

    text: str
    confidence: float
    polygon: list[float] = field(default_factory=list)


@dataclass
class CUPageResult:
    """Content Understanding のページ単位の結果。"""

    page_number: int
    lines: list[str]
    words: list[CUWordDetail]


@dataclass
class CUResult:
    """Content Understanding の OCR 全体結果。"""

    full_text: str
    pages: list[CUPageResult]
    elapsed_seconds: float
    analyzer_id: str
    fields: dict = field(default_factory=dict)


class ContentUnderstandingClient:
    """Content Understanding REST API クライアント。"""

    def __init__(self, endpoint: str, key: str | None = None):
        self._endpoint = endpoint.rstrip("/")

        headers_policy = HeadersPolicy()
        retry_policy = RetryPolicy()
        transport = RequestsTransport()

        if key:
            headers_policy.add_header("Ocp-Apim-Subscription-Key", key)
            self._pipeline = Pipeline(
                transport=transport,
                policies=[headers_policy, retry_policy],
            )
        else:
            credential = DefaultAzureCredential()
            auth_policy = BearerTokenCredentialPolicy(
                credential, "https://cognitiveservices.azure.com/.default"
            )
            self._pipeline = Pipeline(
                transport=transport,
                policies=[headers_policy, auth_policy, retry_policy],
            )

    def _send(self, request: HttpRequest) -> HttpResponse:
        """パイプライン経由でリクエストを送信する。"""
        response = self._pipeline.run(request)
        return response.http_response

    def create_analyzer(
        self,
        analyzer_id: str,
        description: str = "OCR analyzer",
        field_schema: dict | None = None,
    ) -> dict:
        """ドキュメント分析用のアナライザーを作成する。

        Args:
            analyzer_id: アナライザー ID
            description: アナライザーの説明
            field_schema: カスタムフィールドスキーマ。未指定時はデフォルトを使用。
        """
        url = (
            f"{self._endpoint}/contentunderstanding/analyzers/{analyzer_id}"
            f"?api-version={API_VERSION}"
        )
        if field_schema is None:
            field_schema = {
                "fields": {
                    "content": {
                        "type": "string",
                        "description": "Full text of the document",
                    }
                }
            }
        body = {
            "description": description,
            "baseAnalyzerId": "prebuilt-document",
            "config": {
                "returnDetails": True,
            },
            "fieldSchema": field_schema,
            "models": {
                "completion": "gpt-4.1-mini",
                "embedding": "text-embedding-3-large",
            },
        }
        request = HttpRequest(method="PUT", url=url, json=body)
        response = self._send(request)

        if response.status_code in (200, 201):
            return response.json()
        elif response.status_code == 409:
            # すでに存在する場合は既存を使用
            return self.get_analyzer(analyzer_id)
        else:
            raise RuntimeError(
                f"アナライザー作成に失敗しました (HTTP {response.status_code}): "
                f"{response.text()}"
            )

    def get_analyzer(self, analyzer_id: str) -> dict:
        """アナライザー情報を取得する。"""
        url = (
            f"{self._endpoint}/contentunderstanding/analyzers/{analyzer_id}"
            f"?api-version={API_VERSION}"
        )
        request = HttpRequest(method="GET", url=url)
        response = self._send(request)
        if response.status_code == 200:
            return response.json()
        raise RuntimeError(
            f"アナライザー取得に失敗しました (HTTP {response.status_code}): "
            f"{response.text()}"
        )

    def analyzer_exists(self, analyzer_id: str) -> bool:
        """アナライザーが存在するか確認する。"""
        url = (
            f"{self._endpoint}/contentunderstanding/analyzers/{analyzer_id}"
            f"?api-version={API_VERSION}"
        )
        request = HttpRequest(method="GET", url=url)
        response = self._send(request)
        return response.status_code == 200

    def wait_for_analyzer_ready(self, analyzer_id: str, max_wait: int = 60) -> None:
        """アナライザーが準備完了するまでポーリングで待機する。"""
        waited = 0
        interval = 2
        while waited < max_wait:
            info = self.get_analyzer(analyzer_id)
            status = info.get("status", "").lower()
            if status in ("ready", "succeeded", ""):
                # status が空の場合は準備完了と見なす
                return
            if status in ("failed", "error"):
                raise RuntimeError(f"アナライザーの作成に失敗しました: {info}")
            time.sleep(interval)
            waited += interval
        raise TimeoutError(f"アナライザーが {max_wait} 秒以内に準備完了しませんでした")

    def delete_analyzer(self, analyzer_id: str) -> None:
        """アナライザーを削除する。"""
        url = (
            f"{self._endpoint}/contentunderstanding/analyzers/{analyzer_id}"
            f"?api-version={API_VERSION}"
        )
        request = HttpRequest(method="DELETE", url=url)
        response = self._send(request)
        if response.status_code not in (200, 204, 404):
            raise RuntimeError(
                f"アナライザー削除に失敗しました (HTTP {response.status_code}): "
                f"{response.text()}"
            )

    def analyze_document(self, analyzer_id: str, file_path: str) -> CUResult:
        """ドキュメントを Content Understanding で分析する。

        Args:
            analyzer_id: 使用するアナライザー ID
            file_path: 分析するファイルのパス

        Returns:
            CUResult: 分析結果
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")

        with open(path, "rb") as f:
            file_bytes = f.read()

        content_type = _get_content_type(path.suffix.lower())

        start_time = time.time()

        # 分析を開始 (analyzeBinary でバイナリ送信)
        operation_url = self._start_analysis(analyzer_id, file_bytes, content_type)

        # ポーリングして結果を待つ
        analysis_result = self._poll_result(operation_url)

        elapsed = time.time() - start_time

        return _parse_analysis_result(analysis_result, elapsed, analyzer_id)

    def _start_analysis(self, analyzer_id: str, file_bytes: bytes, content_type: str) -> str:
        """分析を開始し、Operation-Location URL を返す。"""
        url = (
            f"{self._endpoint}/contentunderstanding/analyzers/{analyzer_id}:analyzeBinary"
            f"?api-version={API_VERSION}"
        )
        request = HttpRequest(
            method="POST",
            url=url,
            content=file_bytes,
            headers={"Content-Type": content_type},
        )
        response = self._send(request)

        if response.status_code in (200, 202):
            # Operation-Location ヘッダーから結果 URL を取得
            operation_location = response.headers.get("Operation-Location", "")
            if operation_location:
                return operation_location

            # ヘッダーがない場合、レスポンスボディから取得を試みる
            result = response.json()
            result_id = result.get("id") or result.get("resultId")
            if result_id:
                return (
                    f"{self._endpoint}/contentunderstanding/analyzers/{analyzer_id}"
                    f"/results/{result_id}?api-version={API_VERSION}"
                )

            raise RuntimeError("結果 ID を取得できませんでした")
        else:
            raise RuntimeError(
                f"分析開始に失敗しました (HTTP {response.status_code}): "
                f"{response.text()}"
            )

    def _poll_result(
        self, operation_url: str, max_wait: int = 120
    ) -> dict:
        """分析結果をポーリングで待機する。"""
        request = HttpRequest(method="GET", url=operation_url)

        waited = 0
        interval = 2
        while waited < max_wait:
            response = self._send(request)
            if response.status_code == 200:
                result = response.json()
                status = result.get("status", "").lower()
                if status in ("succeeded", "completed"):
                    return result
                elif status in ("failed", "error"):
                    error_detail = result.get("error", result)
                    raise RuntimeError(f"分析に失敗しました: {error_detail}")
                # まだ処理中
            elif response.status_code != 202:
                raise RuntimeError(
                    f"結果取得に失敗しました (HTTP {response.status_code}): "
                    f"{response.text()}"
                )

            time.sleep(interval)
            waited += interval

        raise TimeoutError(f"分析が {max_wait} 秒以内に完了しませんでした")


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


def _parse_analysis_result(result: dict, elapsed: float, analyzer_id: str) -> CUResult:
    """Content Understanding の分析結果をパースする。"""
    result_body = result.get("result", result)

    full_text = ""
    pages: list[CUPageResult] = []
    extracted_fields: dict = {}

    # GA API (2025-11-01): result.contents[] にドキュメント情報が格納される
    content_list = []
    if isinstance(result_body, dict) and "contents" in result_body:
        content_list = result_body["contents"]
    elif isinstance(result_body, list):
        content_list = result_body

    for content_item in content_list:
        if not isinstance(content_item, dict):
            continue

        # markdown テキストを連結
        md = content_item.get("markdown", "")
        if md:
            full_text = (full_text + "\n" + md).strip() if full_text else md

        # フィールド抽出結果
        if "fields" in content_item and not extracted_fields:
            extracted_fields = content_item["fields"]

        # ページ単位の詳細情報 (returnDetails=True 時)
        for page_data in content_item.get("pages", []):
            page_num = page_data.get("pageNumber", 1)
            lines = []
            words = []

            for line in page_data.get("lines", []):
                lines.append(line.get("content", ""))

            for word in page_data.get("words", []):
                words.append(
                    CUWordDetail(
                        text=word.get("content", ""),
                        confidence=word.get("confidence", 0.0),
                        polygon=[],
                    )
                )

            pages.append(
                CUPageResult(
                    page_number=page_num,
                    lines=lines,
                    words=words,
                )
            )

    if not full_text and not pages:
        full_text = str(result_body)

    return CUResult(
        full_text=full_text,
        pages=pages,
        elapsed_seconds=elapsed,
        analyzer_id=analyzer_id,
        fields=extracted_fields,
    )
