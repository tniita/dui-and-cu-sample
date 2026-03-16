# OCR 比較サンプル: Document Intelligence vs Content Understanding

Azure AI **Document Intelligence** と **Content Understanding** の OCR 機能を同一ドキュメントで比較し、結果を並べて確認するためのサンプルです。

## サービス概要

| サービス | 特徴 |
|---|---|
| **Document Intelligence** | 構造化ドキュメント分析に特化した OCR サービス。テキスト、テーブル、キー・バリューペア、レイアウト情報を高精度で抽出。`prebuilt-read` モデルで純粋な OCR に対応。 |
| **Content Understanding** | ドキュメント、画像、音声、動画を統一的に分析できる新しいサービス。「アナライザー」を定義してカスタムフィールド抽出が可能。OCR に加えてセマンティックな理解を提供。 |

## 前提条件

- Python 3.10 以上
- Azure サブスクリプション
- 以下のいずれか / 両方のリソースをデプロイ済み:
  - [Azure AI Document Intelligence](https://learn.microsoft.com/azure/ai-services/document-intelligence/)
  - [Azure AI Content Understanding](https://learn.microsoft.com/azure/ai-services/content-understanding/)
- `az login` 済み、または API キーを取得済み

## セットアップ

```bash
# 依存パッケージをインストール
pip install -r requirements.txt

# 環境変数を設定
cp .env.sample .env
# .env を編集してエンドポイント / キーを記入
```

### 環境変数

| 変数名 | 説明 |
|---|---|
| `DOCUMENT_INTELLIGENCE_ENDPOINT` | Document Intelligence のエンドポイント URL |
| `DOCUMENT_INTELLIGENCE_KEY` | (任意) API キー。未設定時は `DefaultAzureCredential` を使用 |
| `CONTENT_UNDERSTANDING_ENDPOINT` | Content Understanding のエンドポイント URL |
| `CONTENT_UNDERSTANDING_KEY` | (任意) API キー。未設定時は `DefaultAzureCredential` を使用 |

## 使い方

### 両サービスで比較

```bash
python compare_ocr.py path/to/document.pdf
```

### Document Intelligence のみ

```bash
python compare_ocr.py path/to/document.pdf --di-only
```

### Content Understanding のみ

```bash
python compare_ocr.py path/to/document.pdf --cu-only
```

### Document Intelligence のモデルを指定

```bash
# レイアウト分析モデルを使用
python compare_ocr.py path/to/document.pdf --di-model prebuilt-layout
```

### 書類形式を指定して分析

`--doc-type` で書類形式を指定すると、形式に応じたフィールド（合計金額、請求番号など）が自動抽出されます。アナライザーは初回に自動作成され、2回目以降は再利用されます。

```bash
# 請求書として分析（InvoiceTotal, InvoiceNumber, InvoiceDate, VendorName を抽出）
python compare_ocr.py path/to/invoice.pdf --cu-only --doc-type invoice

# 燃料請求書として分析（TotalUsage, BillingPeriod, TotalAmount を抽出）
python compare_ocr.py path/to/fuel_invoice.pdf --cu-only --doc-type fuel_invoice

# 汎用（デフォルト）
python compare_ocr.py path/to/document.pdf --cu-only --doc-type generic
```

### アナライザーの管理

```bash
# 利用可能な書類形式の一覧を表示
python compare_ocr.py --list-types

# 指定した書類形式のアナライザーを削除（再作成したい場合など）
python compare_ocr.py --delete-analyzer invoice
```

### 書類形式の追加

`analyzer_config.json` にエントリを追加するだけで、新しい書類形式を定義できます。

```json
{
  "doc_types": {
    "my_receipt": {
      "analyzer_id": "ocrMyReceipt",
      "description": "レシート分析用",
      "field_schema": {
        "name": "ReceiptAnalysis",
        "fields": {
          "StoreName": {
            "type": "string",
            "description": "店舗名",
            "method": "extract"
          },
          "Total": {
            "type": "string",
            "description": "合計金額。カンマ区切り。",
            "method": "extract"
          }
        }
      }
    }
  }
}
```

## サポートするファイル形式

- PDF (`.pdf`)
- JPEG (`.jpg`, `.jpeg`)
- PNG (`.png`)
- BMP (`.bmp`)
- TIFF (`.tif`, `.tiff`)
- HEIF (`.heif`)

## 出力例

```
対象ファイル: sample.pdf
ファイルサイズ: 123,456 bytes

[Document Intelligence] 分析を開始します...
[Document Intelligence] 分析完了 (2.34 秒)
[Content Understanding] アナライザーを準備しています...
[Content Understanding] アナライザー作成完了: ocr-compare-a1b2c3d4
[Content Understanding] 分析を開始します...
[Content Understanding] 分析完了 (3.56 秒)

======================================================================
  比較サマリー
======================================================================
+----------------+-------------------------+-------------------------+
| 項目           | Document Intelligence   | Content Understanding   |
+================+=========================+=========================+
| 処理時間 (秒)  | 2.34                    | 3.56                    |
| ページ数       | 1                       | 1                       |
| 検出行数       | 25                      | 24                      |
| 検出単語数     | 180                     | 175                     |
| テキスト文字数 | 1250                    | 1230                    |
| 平均信頼度     | 0.9912                  | 0.9850                  |
+----------------+-------------------------+-------------------------+

  テキスト類似度: 95.32%
```

## ファイル構成

```
ocr-comparison/
├── README.md                          # このファイル
├── requirements.txt                   # Python 依存パッケージ
├── .env.sample                        # 環境変数テンプレート
├── analyzer_config.json               # 書類形式ごとのアナライザー定義
├── compare_ocr.py                     # 比較メインスクリプト
├── document_intelligence_ocr.py       # Document Intelligence モジュール
└── content_understanding_ocr.py       # Content Understanding モジュール
```

## 比較ポイント

このサンプルで確認できる観点:

1. **処理速度**: 同一ドキュメントに対する応答時間の差
2. **テキスト抽出精度**: 抽出されたテキストの一致度・差分
3. **単語検出数**: 検出した単語・行の数の違い
4. **信頼度**: 各単語の信頼度スコアの平均
5. **構造認識**: ページ単位での認識結果の差異

## 注意事項

- Content Understanding は GA (API バージョン `2025-11-01`) を使用しています。
- Content Understanding のアナライザーは `--doc-type` ごとに永続化され、再利用されます。不要になった場合は `--delete-analyzer` で削除してください。
- 大きなファイル（特に高解像度画像）はリクエストサイズ制限に注意してください。
- 認証には API キーまたは `DefaultAzureCredential`（`az login`、マネージド ID 等）が利用可能です。
