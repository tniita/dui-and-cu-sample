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

# ── ANSI カラー定義 ──────────────────────────────────────────────────

class _C:
    """ANSI エスケープシーケンス。NO_COLOR 環境変数で無効化可能。"""
    _enabled = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

    RESET   = "\033[0m"   if _enabled else ""
    BOLD    = "\033[1m"    if _enabled else ""
    DIM     = "\033[2m"    if _enabled else ""
    CYAN    = "\033[36m"   if _enabled else ""
    GREEN   = "\033[32m"   if _enabled else ""
    YELLOW  = "\033[33m"   if _enabled else ""
    BLUE    = "\033[34m"   if _enabled else ""
    MAGENTA = "\033[35m"   if _enabled else ""
    RED     = "\033[31m"   if _enabled else ""
    WHITE   = "\033[97m"   if _enabled else ""
    BG_BLUE = "\033[44m"   if _enabled else ""
    BG_CYAN = "\033[46m"   if _enabled else ""


def _banner(title: str, color: str = _C.CYAN, width: int = 72) -> None:
    """装飾付きセクションバナーを出力する。"""
    border = "━" * width
    print(f"\n{color}{_C.BOLD}{border}{_C.RESET}")
    print(f"{color}{_C.BOLD}  {title}{_C.RESET}")
    print(f"{color}{_C.BOLD}{border}{_C.RESET}")


def _sub_header(title: str) -> None:
    """サブセクションヘッダーを出力する。"""
    print(f"\n  {_C.DIM}{'─' * 68}{_C.RESET}")
    print(f"  {_C.BOLD}{title}{_C.RESET}")
    print(f"  {_C.DIM}{'─' * 68}{_C.RESET}")


def _kv(key: str, value: str, indent: int = 4) -> None:
    """キー・バリューペアを出力する。"""
    pad = " " * indent
    print(f"{pad}{_C.DIM}{key:<16}{_C.RESET} {_C.WHITE}{value}{_C.RESET}")


def _status(icon: str, msg: str) -> None:
    """ステータスメッセージを出力する。"""
    print(f"  {icon} {msg}")


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
        _status("⚠️ ", f"{_C.YELLOW}DOCUMENT_INTELLIGENCE_ENDPOINT が未設定。スキップします。{_C.RESET}")
        return None

    _status("🔍", f"{_C.BLUE}Document Intelligence{_C.RESET} 分析中...")
    client = di_create_client(endpoint, key or None)
    result = di_analyze(client, file_path)
    _status("✅", f"{_C.GREEN}Document Intelligence 完了{_C.RESET} ({result.elapsed_seconds:.2f} 秒)")
    return result


def run_content_understanding(file_path: str, doc_type: str = "generic") -> CUResult | None:
    """Content Understanding で OCR を実行する。"""
    endpoint = os.environ.get("CONTENT_UNDERSTANDING_ENDPOINT", "")
    key = os.environ.get("CONTENT_UNDERSTANDING_KEY", "")

    if not endpoint:
        _status("⚠️ ", f"{_C.YELLOW}CONTENT_UNDERSTANDING_ENDPOINT が未設定。スキップします。{_C.RESET}")
        return None

    type_config = _get_doc_type_config(doc_type)
    analyzer_id = type_config["analyzer_id"]
    field_schema = type_config.get("field_schema")
    description = type_config.get("description", "OCR アナライザー")

    client = ContentUnderstandingClient(endpoint, key or None)

    if client.analyzer_exists(analyzer_id):
        _status("♻️ ", f"既存アナライザーを使用: {_C.CYAN}{analyzer_id}{_C.RESET}")
    else:
        _status("🆕", f"アナライザーを新規作成: {_C.CYAN}{analyzer_id}{_C.RESET}")
        client.create_analyzer(
            analyzer_id,
            description=description,
            field_schema=field_schema,
        )
        client.wait_for_analyzer_ready(analyzer_id)
        _status("✅", f"アナライザー作成完了: {_C.CYAN}{analyzer_id}{_C.RESET}")

    _status("🔍", f"{_C.MAGENTA}Content Understanding{_C.RESET} 分析中...")
    result = client.analyze_document(analyzer_id, file_path)
    _status("✅", f"{_C.GREEN}Content Understanding 完了{_C.RESET} ({result.elapsed_seconds:.2f} 秒)")
    return result


def print_di_result(result: DIResult) -> None:
    """Document Intelligence の結果を表示する。"""
    _banner("📄 Document Intelligence 結果", _C.BLUE)

    total_words = sum(len(p.words) for p in result.pages)
    total_lines = sum(len(p.lines) for p in result.pages)

    _kv("モデル ID", result.model_id)
    _kv("処理時間", f"{result.elapsed_seconds:.2f} 秒")
    _kv("ページ数", str(len(result.pages)))
    _kv("検出行数", str(total_lines))
    _kv("検出単語数", str(total_words))

    if result.pages:
        avg_conf = _avg_confidence_di(result)
        _kv("平均信頼度", f"{avg_conf:.4f}")

    _sub_header("📝 抽出テキスト")
    print()
    for line in result.full_text[:2000].splitlines():
        print(f"    {line}")
    if len(result.full_text) > 2000:
        print(f"\n    {_C.DIM}... 以降 {len(result.full_text) - 2000} 文字省略{_C.RESET}")
    print()


def print_cu_result(result: CUResult) -> None:
    """Content Understanding の結果を表示する。"""
    _banner("🤖 Content Understanding 結果", _C.MAGENTA)

    total_words = sum(len(p.words) for p in result.pages)
    total_lines = sum(len(p.lines) for p in result.pages)

    _kv("アナライザーID", result.analyzer_id)
    _kv("処理時間", f"{result.elapsed_seconds:.2f} 秒")
    _kv("ページ数", str(len(result.pages)))
    _kv("検出行数", str(total_lines))
    _kv("検出単語数", str(total_words))

    if result.pages and any(p.words for p in result.pages):
        avg_conf = _avg_confidence_cu(result)
        _kv("平均信頼度", f"{avg_conf:.4f}")

    if result.fields:
        _sub_header(f"🏷️  抽出フィールド ({len(result.fields)} 件)")
        print()
        for name, field in result.fields.items():
            if isinstance(field, dict):
                val = field.get("valueNumber", field.get("valueString", field.get("valueDate", "")))
                conf = field.get("confidence")
                if isinstance(val, (int, float)):
                    val_str = f"{val:,.2f}" if isinstance(val, float) else f"{val:,}"
                else:
                    val_str = str(val)

                conf_bar = ""
                if conf is not None:
                    filled = int(conf * 10)
                    bar_color = _C.GREEN if conf >= 0.8 else (_C.YELLOW if conf >= 0.5 else _C.RED)
                    conf_bar = f" {bar_color}{'█' * filled}{'░' * (10 - filled)}{_C.RESET} {conf:.1%}"

                print(f"    {_C.CYAN}{name:<20}{_C.RESET} {_C.WHITE}{_C.BOLD}{val_str}{_C.RESET}{conf_bar}")
            else:
                print(f"    {_C.CYAN}{name:<20}{_C.RESET} {field}")
        print()

    _sub_header("📝 抽出テキスト")
    print()
    for line in result.full_text[:2000].splitlines():
        print(f"    {line}")
    if len(result.full_text) > 2000:
        print(f"\n    {_C.DIM}... 以降 {len(result.full_text) - 2000} 文字省略{_C.RESET}")
    print()


def print_comparison(di_result: DIResult | None, cu_result: CUResult | None) -> None:
    """両サービスの結果を比較表示する。"""
    if not di_result or not cu_result:
        print(f"\n  {_C.YELLOW}⚠️  比較には両方のサービスの結果が必要です。{_C.RESET}")
        return

    _banner("⚖️  比較サマリー", _C.GREEN)

    di_total_words = sum(len(p.words) for p in di_result.pages)
    cu_total_words = sum(len(p.words) for p in cu_result.pages)
    di_total_lines = sum(len(p.lines) for p in di_result.pages)
    cu_total_lines = sum(len(p.lines) for p in cu_result.pages)

    rows = [
        ["⏱️  処理時間 (秒)", f"{di_result.elapsed_seconds:.2f}", f"{cu_result.elapsed_seconds:.2f}"],
        ["📄 ページ数", len(di_result.pages), len(cu_result.pages)],
        ["📏 検出行数", di_total_lines, cu_total_lines],
        ["🔤 検出単語数", di_total_words, cu_total_words],
        ["📊 テキスト文字数", len(di_result.full_text), len(cu_result.full_text)],
    ]

    if di_result.pages:
        di_conf = f"{_avg_confidence_di(di_result):.4f}"
        cu_conf = "-"
        if cu_result.pages and any(p.words for p in cu_result.pages):
            cu_conf = f"{_avg_confidence_cu(cu_result):.4f}"
        rows.append(["🎯 平均信頼度", di_conf, cu_conf])

    print()
    print(
        tabulate(
            rows,
            headers=[
                f"{_C.BOLD}項目{_C.RESET}",
                f"{_C.BLUE}{_C.BOLD}Document Intelligence{_C.RESET}",
                f"{_C.MAGENTA}{_C.BOLD}Content Understanding{_C.RESET}",
            ],
            tablefmt="rounded_outline",
            colalign=("left", "right", "right"),
        )
    )

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

    matcher = difflib.SequenceMatcher(None, text_a, text_b)
    similarity = matcher.ratio()

    # 類似度バー
    filled = int(similarity * 20)
    bar_color = _C.GREEN if similarity >= 0.9 else (_C.YELLOW if similarity >= 0.7 else _C.RED)
    bar = f"{bar_color}{'█' * filled}{'░' * (20 - filled)}{_C.RESET}"
    print(f"\n  📊 テキスト類似度: {bar} {_C.BOLD}{similarity:.1%}{_C.RESET}")

    diff = list(difflib.unified_diff(
        lines_a[:50],
        lines_b[:50],
        fromfile="Document Intelligence",
        tofile="Content Understanding",
        lineterm="",
    ))

    if diff:
        _sub_header("📝 テキスト差分 (先頭 50 行)")
        print()
        for line in diff[:60]:
            if line.startswith("+") and not line.startswith("+++"):
                print(f"    {_C.GREEN}{line}{_C.RESET}")
            elif line.startswith("-") and not line.startswith("---"):
                print(f"    {_C.RED}{line}{_C.RESET}")
            elif line.startswith("@@"):
                print(f"    {_C.CYAN}{line}{_C.RESET}")
            else:
                print(f"    {_C.DIM}{line}{_C.RESET}")
        if len(diff) > 60:
            print(f"    {_C.DIM}... 以降 {len(diff) - 60} 行省略{_C.RESET}")
    else:
        print(f"\n  ✨ {_C.GREEN}テキスト差分なし (完全一致){_C.RESET}")
    print()


def _delete_analyzer_command(doc_type: str) -> None:
    """指定した書類形式のアナライザーを削除する。"""
    endpoint = os.environ.get("CONTENT_UNDERSTANDING_ENDPOINT", "")
    key = os.environ.get("CONTENT_UNDERSTANDING_KEY", "")
    if not endpoint:
        _status("❌", f"{_C.RED}CONTENT_UNDERSTANDING_ENDPOINT が未設定です。{_C.RESET}")
        return

    type_config = _get_doc_type_config(doc_type)
    analyzer_id = type_config["analyzer_id"]
    client = ContentUnderstandingClient(endpoint, key or None)

    if not client.analyzer_exists(analyzer_id):
        _status("ℹ️ ", f"アナライザー '{_C.CYAN}{analyzer_id}{_C.RESET}' は存在しません。")
        return

    client.delete_analyzer(analyzer_id)
    _status("🗑️ ", f"アナライザー '{_C.CYAN}{analyzer_id}{_C.RESET}' ({_C.DIM}{doc_type}{_C.RESET}) を削除しました。")


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
        _banner("📋 利用可能な書類形式", _C.CYAN)
        print()
        for name, info in sorted(types.items()):
            fields = list(info.get("field_schema", {}).get("fields", {}).keys())
            analyzer_id = info.get("analyzer_id", "")
            print(f"    {_C.BOLD}{_C.CYAN}{name}{_C.RESET}")
            print(f"      {_C.DIM}説明:{_C.RESET}        {info.get('description', '')}")
            print(f"      {_C.DIM}アナライザー:{_C.RESET}  {analyzer_id}")
            if fields:
                print(f"      {_C.DIM}フィールド:{_C.RESET}    {', '.join(fields)}")
            print()
        return

    # アナライザー削除
    if args.delete_analyzer:
        _delete_analyzer_command(args.delete_analyzer)
        return

    # ファイル分析
    if not args.file:
        parser.error("分析するファイルを指定してください (--list-types で書類形式一覧を確認できます)")

    if not os.path.exists(args.file):
        _status("❌", f"{_C.RED}ファイルが見つかりません: {args.file}{_C.RESET}")
        sys.exit(1)

    _banner("🔎 OCR 比較分析", _C.WHITE)
    _kv("対象ファイル", args.file)
    _kv("ファイルサイズ", f"{os.path.getsize(args.file):,} bytes")
    if not args.di_only and not args.cu_only:
        _kv("モード", "両サービス比較")
    elif args.di_only:
        _kv("モード", "Document Intelligence のみ")
    else:
        _kv("モード", f"Content Understanding のみ (書類形式: {args.doc_type})")
    print()

    di_result = None
    cu_result = None

    if not args.cu_only:
        try:
            di_result = run_document_intelligence(args.file)
        except Exception as e:
            _status("❌", f"{_C.RED}Document Intelligence エラー: {e}{_C.RESET}")

    if not args.di_only:
        try:
            cu_result = run_content_understanding(args.file, doc_type=args.doc_type)
        except Exception as e:
            _status("❌", f"{_C.RED}Content Understanding エラー: {e}{_C.RESET}")

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
