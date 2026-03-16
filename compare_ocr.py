"""Document Intelligence と Content Understanding の OCR 比較スクリプト。

使い方:
    python compare_ocr.py <ファイルパス> [--di-only | --cu-only] [--doc-type TYPE]

環境変数 (.env) が必要です。.env.sample を参照してください。
"""

import argparse
import difflib
import json
import os
import sys

from dotenv import load_dotenv
from tabulate import tabulate

from document_intelligence_ocr import (
    DIResult,
    analyze_document as di_analyze,
    create_client as di_create_client,
)
from content_understanding_ocr import (
    CUResult,
    ContentUnderstandingClient,
)

load_dotenv()

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "analyzer_config.json")


def _load_config() -> dict:
    """analyzer_config.json を読み込む。"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_doc_type_config(doc_type: str) -> dict:
    """指定された書類形式の設定を返す。"""
    config = _load_config()
    types = config.get("doc_types", {})
    if doc_type not in types:
        available = ", ".join(sorted(types.keys()))
        raise ValueError(
            f"未定義の書類形式: '{doc_type}'\n利用可能な形式: {available}"
        )
    return types[doc_type]


def run_document_intelligence(file_path: str) -> DIResult | None:
    """Document Intelligence で OCR を実行する。"""
    endpoint = os.environ.get("DOCUMENT_INTELLIGENCE_ENDPOINT", "")
    key = os.environ.get("DOCUMENT_INTELLIGENCE_KEY", "")

    if not endpoint:
        print("[Document Intelligence] DOCUMENT_INTELLIGENCE_ENDPOINT が設定されていません。スキップします。")
        return None

    print("[Document Intelligence] 分析を開始します...")
    client = di_create_client(endpoint, key or None)
    result = di_analyze(client, file_path)
    print(f"[Document Intelligence] 分析完了 ({result.elapsed_seconds:.2f} 秒)")
    return result


def run_content_understanding(file_path: str, doc_type: str = "generic") -> CUResult | None:
    """Content Understanding で OCR を実行する。"""
    endpoint = os.environ.get("CONTENT_UNDERSTANDING_ENDPOINT", "")
    key = os.environ.get("CONTENT_UNDERSTANDING_KEY", "")

    if not endpoint:
        print("[Content Understanding] CONTENT_UNDERSTANDING_ENDPOINT が設定されていません。スキップします。")
        return None

    type_config = _get_doc_type_config(doc_type)
    analyzer_id = type_config["analyzer_id"]
    field_schema = type_config.get("field_schema")
    description = type_config.get("description", "OCR アナライザー")

    client = ContentUnderstandingClient(endpoint, key or None)

    # アナライザーが既に存在するか確認
    if client.analyzer_exists(analyzer_id):
        print(f"[Content Understanding] 既存アナライザーを使用: {analyzer_id}")
    else:
        print(f"[Content Understanding] アナライザーを新規作成しています: {analyzer_id}")
        client.create_analyzer(
            analyzer_id,
            description=description,
            field_schema=field_schema,
        )
        client.wait_for_analyzer_ready(analyzer_id)
        print(f"[Content Understanding] アナライザー作成完了: {analyzer_id}")

    print("[Content Understanding] 分析を開始します...")
    result = client.analyze_document(analyzer_id, file_path)
    print(f"[Content Understanding] 分析完了 ({result.elapsed_seconds:.2f} 秒)")
    return result


def print_di_result(result: DIResult) -> None:
    """Document Intelligence の結果を表示する。"""
    print("\n" + "=" * 70)
    print("  Document Intelligence 結果")
    print("=" * 70)
    print(f"  モデル ID    : {result.model_id}")
    print(f"  処理時間     : {result.elapsed_seconds:.2f} 秒")
    print(f"  ページ数     : {len(result.pages)}")
    total_words = sum(len(p.words) for p in result.pages)
    total_lines = sum(len(p.lines) for p in result.pages)
    print(f"  検出行数     : {total_lines}")
    print(f"  検出単語数   : {total_words}")

    if result.pages:
        avg_conf = _avg_confidence_di(result)
        print(f"  平均信頼度   : {avg_conf:.4f}")

    print("-" * 70)
    print("  抽出テキスト:")
    print("-" * 70)
    print(result.full_text[:2000])
    if len(result.full_text) > 2000:
        print(f"\n  ... (以降 {len(result.full_text) - 2000} 文字省略)")
    print()


def print_cu_result(result: CUResult) -> None:
    """Content Understanding の結果を表示する。"""
    print("\n" + "=" * 70)
    print("  Content Understanding 結果")
    print("=" * 70)
    print(f"  アナライザーID : {result.analyzer_id}")
    print(f"  処理時間       : {result.elapsed_seconds:.2f} 秒")
    print(f"  ページ数       : {len(result.pages)}")
    total_words = sum(len(p.words) for p in result.pages)
    total_lines = sum(len(p.lines) for p in result.pages)
    print(f"  検出行数       : {total_lines}")
    print(f"  検出単語数     : {total_words}")

    if result.pages and any(p.words for p in result.pages):
        avg_conf = _avg_confidence_cu(result)
        print(f"  平均信頼度     : {avg_conf:.4f}")

    if result.fields:
        print(f"  抽出フィールド : {len(result.fields)} 件")
        for name, field in result.fields.items():
            if isinstance(field, dict):
                val = field.get("valueNumber", field.get("valueString", field.get("valueDate", "")))
                conf = field.get("confidence")
                conf_str = f" (信頼度: {conf:.4f})" if conf is not None else ""
                if isinstance(val, (int, float)):
                    val_str = f"{val:,.2f}" if isinstance(val, float) else f"{val:,}"
                else:
                    val_str = str(val)
                print(f"    {name}: {val_str}{conf_str}")
            else:
                print(f"    {name}: {field}")

    print("-" * 70)
    print("  抽出テキスト:")
    print("-" * 70)
    print(result.full_text[:2000])
    if len(result.full_text) > 2000:
        print(f"\n  ... (以降 {len(result.full_text) - 2000} 文字省略)")
    print()


def print_comparison(di_result: DIResult | None, cu_result: CUResult | None) -> None:
    """両サービスの結果を比較表示する。"""
    if not di_result or not cu_result:
        print("\n比較には両方のサービスの結果が必要です。")
        return

    print("\n" + "=" * 70)
    print("  比較サマリー")
    print("=" * 70)

    di_total_words = sum(len(p.words) for p in di_result.pages)
    cu_total_words = sum(len(p.words) for p in cu_result.pages)
    di_total_lines = sum(len(p.lines) for p in di_result.pages)
    cu_total_lines = sum(len(p.lines) for p in cu_result.pages)

    rows = [
        ["処理時間 (秒)", f"{di_result.elapsed_seconds:.2f}", f"{cu_result.elapsed_seconds:.2f}"],
        ["ページ数", len(di_result.pages), len(cu_result.pages)],
        ["検出行数", di_total_lines, cu_total_lines],
        ["検出単語数", di_total_words, cu_total_words],
        ["テキスト文字数", len(di_result.full_text), len(cu_result.full_text)],
    ]

    if di_result.pages:
        rows.append(["平均信頼度", f"{_avg_confidence_di(di_result):.4f}", "-"])

    if cu_result.pages and any(p.words for p in cu_result.pages):
        rows[-1][2] = f"{_avg_confidence_cu(cu_result):.4f}"

    print(tabulate(rows, headers=["項目", "Document Intelligence", "Content Understanding"], tablefmt="grid"))

    # テキスト差分
    _print_text_diff(di_result.full_text, cu_result.full_text)


def _avg_confidence_di(result: DIResult) -> float:
    """Document Intelligence の平均信頼度を計算する。"""
    all_confs = [w.confidence for p in result.pages for w in p.words]
    return sum(all_confs) / len(all_confs) if all_confs else 0.0


def _avg_confidence_cu(result: CUResult) -> float:
    """Content Understanding の平均信頼度を計算する。"""
    all_confs = [w.confidence for p in result.pages for w in p.words]
    return sum(all_confs) / len(all_confs) if all_confs else 0.0


def _print_text_diff(text_a: str, text_b: str) -> None:
    """2つのテキストの差分を表示する。"""
    lines_a = text_a.splitlines()
    lines_b = text_b.splitlines()

    # 類似度を計算
    matcher = difflib.SequenceMatcher(None, text_a, text_b)
    similarity = matcher.ratio()
    print(f"\n  テキスト類似度: {similarity:.2%}")

    # 差分の概要
    diff = list(difflib.unified_diff(
        lines_a[:50],
        lines_b[:50],
        fromfile="Document Intelligence",
        tofile="Content Understanding",
        lineterm="",
    ))

    if diff:
        print("\n  テキスト差分 (先頭 50 行):")
        print("-" * 70)
        for line in diff[:60]:
            print(f"  {line}")
        if len(diff) > 60:
            print(f"  ... (以降 {len(diff) - 60} 行省略)")
    else:
        print("\n  テキスト差分: なし (完全一致)")
    print()


def _delete_analyzer_command(doc_type: str) -> None:
    """指定した書類形式のアナライザーを削除する。"""
    endpoint = os.environ.get("CONTENT_UNDERSTANDING_ENDPOINT", "")
    key = os.environ.get("CONTENT_UNDERSTANDING_KEY", "")
    if not endpoint:
        print("CONTENT_UNDERSTANDING_ENDPOINT が設定されていません。")
        return

    type_config = _get_doc_type_config(doc_type)
    analyzer_id = type_config["analyzer_id"]
    client = ContentUnderstandingClient(endpoint, key or None)

    if not client.analyzer_exists(analyzer_id):
        print(f"アナライザー '{analyzer_id}' は存在しません。")
        return

    client.delete_analyzer(analyzer_id)
    print(f"アナライザー '{analyzer_id}' (書類形式: {doc_type}) を削除しました。")


def main() -> None:
    """メインエントリーポイント。"""
    parser = argparse.ArgumentParser(
        description="Document Intelligence と Content Understanding の OCR 比較"
    )
    parser.add_argument("file", nargs="?", help="分析するドキュメントファイルのパス (PDF, JPG, PNG, TIFF, BMP)")
    parser.add_argument("--di-only", action="store_true", help="Document Intelligence のみ実行")
    parser.add_argument("--cu-only", action="store_true", help="Content Understanding のみ実行")
    parser.add_argument(
        "--di-model",
        default="prebuilt-read",
        help="Document Intelligence のモデル ID (デフォルト: prebuilt-read)",
    )
    parser.add_argument(
        "--doc-type",
        default="generic",
        help="書類形式 (analyzer_config.json で定義, デフォルト: generic)",
    )
    parser.add_argument(
        "--list-types",
        action="store_true",
        help="利用可能な書類形式の一覧を表示",
    )
    parser.add_argument(
        "--delete-analyzer",
        metavar="DOC_TYPE",
        help="指定した書類形式のアナライザーを削除",
    )

    args = parser.parse_args()

    # 書類形式の一覧表示
    if args.list_types:
        config = _load_config()
        types = config.get("doc_types", {})
        print("利用可能な書類形式:")
        print("-" * 60)
        for name, info in sorted(types.items()):
            fields = list(info.get("field_schema", {}).get("fields", {}).keys())
            print(f"  {name:<20} {info.get('description', '')}")
            if fields:
                print(f"  {'':20} フィールド: {', '.join(fields)}")
        return

    # アナライザー削除
    if args.delete_analyzer:
        _delete_analyzer_command(args.delete_analyzer)
        return

    # ファイル分析
    if not args.file:
        parser.error("分析するファイルを指定してください (--list-types で書類形式一覧を確認できます)")

    if not os.path.exists(args.file):
        print(f"エラー: ファイルが見つかりません: {args.file}")
        sys.exit(1)

    print(f"対象ファイル: {args.file}")
    print(f"ファイルサイズ: {os.path.getsize(args.file):,} bytes")
    print()

    di_result = None
    cu_result = None

    if not args.cu_only:
        try:
            di_result = run_document_intelligence(args.file)
        except Exception as e:
            print(f"[Document Intelligence] エラーが発生しました: {e}")

    if not args.di_only:
        try:
            cu_result = run_content_understanding(args.file, doc_type=args.doc_type)
        except Exception as e:
            print(f"[Content Understanding] エラーが発生しました: {e}")

    # 結果表示
    if di_result:
        print_di_result(di_result)

    if cu_result:
        print_cu_result(cu_result)

    # 比較
    if not args.di_only and not args.cu_only:
        print_comparison(di_result, cu_result)


if __name__ == "__main__":
    main()
