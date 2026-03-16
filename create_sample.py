"""テスト用サンプル画像を生成するスクリプト。

Pillow を使って請求書風のテスト画像を生成する。
USD・EUR の海外通貨請求書と、基本的な OCR テスト画像を生成する。
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _load_fonts() -> tuple:
    """システムフォントを読み込む。(大・中・小) のタプルを返す。"""
    font_large = None
    font_medium = None
    font_normal = None
    font_small = None

    bold_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for font_path in bold_candidates:
        if Path(font_path).exists():
            try:
                font_large = ImageFont.truetype(font_path, 28)
                font_medium = ImageFont.truetype(font_path, 20)
                regular = font_path.replace("-Bold", "-Regular").replace("Bold", "Regular")
                font_normal = ImageFont.truetype(regular if Path(regular).exists() else font_path, 16)
                font_small = ImageFont.truetype(regular if Path(regular).exists() else font_path, 13)
            except OSError:
                pass
            break

    default = ImageFont.load_default()
    return (
        font_large or default,
        font_medium or default,
        font_normal or default,
        font_small or default,
    )


def _draw_table(draw: ImageDraw.Draw, x: int, y: int, headers: list[str],
                rows: list[list[str]], col_widths: list[int], font, font_bold) -> int:
    """テーブルを描画し、描画後の y 座標を返す。"""
    row_height = 24
    total_width = sum(col_widths)

    # ヘッダー背景
    draw.rectangle([(x, y), (x + total_width, y + row_height)], fill="#e8e8e8")

    # ヘッダーテキスト
    cx = x
    for i, header in enumerate(headers):
        draw.text((cx + 4, y + 4), header, fill="black", font=font_bold)
        cx += col_widths[i]
    y += row_height

    # ヘッダー下線
    draw.line([(x, y), (x + total_width, y)], fill="black", width=2)

    # データ行
    for row in rows:
        cx = x
        for i, cell in enumerate(row):
            draw.text((cx + 4, y + 4), cell, fill="black", font=font)
            cx += col_widths[i]
        y += row_height
        draw.line([(x, y), (x + total_width, y)], fill="#cccccc", width=1)

    # 外枠
    draw.rectangle(
        [(x, y - row_height * len(rows) - row_height), (x + total_width, y)],
        outline="black", width=1,
    )
    return y


def create_usd_invoice(output_path: str = "sample_documents/invoice_usd.png") -> str:
    """USD 請求書のサンプル画像を生成する。"""
    width, height = 900, 750
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    font_large, font_medium, font_normal, font_small = _load_fonts()

    # ヘッダー帯
    draw.rectangle([(0, 0), (width, 70)], fill="#1a3c6e")
    draw.text((30, 15), "INVOICE", fill="white", font=font_large)
    draw.text((width - 250, 25), "Acme Corporation", fill="white", font=font_medium)

    y = 90

    # 請求書情報
    info_lines = [
        ("Invoice No:", "INV-2026-00142"),
        ("Date:", "March 10, 2026"),
        ("Due Date:", "April 10, 2026"),
        ("Currency:", "USD (United States Dollar)"),
    ]
    for label, value in info_lines:
        draw.text((30, y), label, fill="#555555", font=font_normal)
        draw.text((180, y), value, fill="black", font=font_normal)
        y += 24

    y += 10

    # 宛先
    draw.text((30, y), "Bill To:", fill="#555555", font=font_medium)
    draw.text((500, y), "Ship To:", fill="#555555", font=font_medium)
    y += 26
    bill_to = ["GlobalTech Inc.", "1234 Innovation Drive", "San Francisco, CA 94105", "United States"]
    ship_to = ["GlobalTech Warehouse", "5678 Logistics Blvd", "Los Angeles, CA 90001", "United States"]
    for b, s in zip(bill_to, ship_to):
        draw.text((30, y), b, fill="black", font=font_normal)
        draw.text((500, y), s, fill="black", font=font_normal)
        y += 22

    y += 15

    # 明細テーブル
    headers = ["Description", "Qty", "Unit Price", "Amount"]
    col_widths = [400, 80, 130, 130]
    rows = [
        ["Cloud Infrastructure Setup", "1", "$12,500.00", "$12,500.00"],
        ["API Integration Service", "3", "$3,200.00", "$9,600.00"],
        ["Data Migration (per TB)", "5", "$1,800.00", "$9,000.00"],
        ["Security Audit & Compliance", "1", "$4,750.00", "$4,750.00"],
        ["Technical Support (monthly)", "6", "$850.00", "$5,100.00"],
    ]
    y = _draw_table(draw, 30, y, headers, rows, col_widths, font_normal, font_medium)

    y += 15

    # 合計
    totals = [
        ("Subtotal:", "$40,950.00"),
        ("Tax (8.25%):", "$3,378.38"),
        ("Shipping:", "$250.00"),
    ]
    for label, value in totals:
        draw.text((530, y), label, fill="#555555", font=font_normal)
        draw.text((680, y), value, fill="black", font=font_normal)
        y += 22

    y += 4
    draw.line([(530, y), (770, y)], fill="black", width=2)
    y += 6
    draw.text((530, y), "Total Due:", fill="black", font=font_medium)
    draw.text((680, y), "$44,578.38", fill="#1a3c6e", font=font_large)

    y += 45

    # 支払い情報
    draw.line([(30, y), (width - 30, y)], fill="#cccccc", width=1)
    y += 10
    draw.text((30, y), "Payment Instructions:", fill="#555555", font=font_medium)
    y += 26
    payment_lines = [
        "Bank: First National Bank of America",
        "Account Name: Acme Corporation",
        "Account No: 9876-5432-1098",
        "Routing No: 021000021",
        "SWIFT: FNBAUS33",
    ]
    for line in payment_lines:
        draw.text((30, y), line, fill="black", font=font_normal)
        y += 20

    # フッター
    draw.rectangle([(0, height - 35), (width, height)], fill="#f5f5f5")
    draw.text(
        (30, height - 28),
        "Thank you for your business! | Payment terms: Net 30 | Late fee: 1.5% per month",
        fill="#888888", font=font_small,
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out))
    print(f"USD 請求書を生成しました: {out}")
    return str(out)


def create_eur_invoice(output_path: str = "sample_documents/invoice_eur.png") -> str:
    """EUR 請求書のサンプル画像を生成する。"""
    width, height = 900, 780
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    font_large, font_medium, font_normal, font_small = _load_fonts()

    # ヘッダー帯
    draw.rectangle([(0, 0), (width, 70)], fill="#2e5a1e")
    draw.text((30, 15), "RECHNUNG / INVOICE", fill="white", font=font_large)
    draw.text((width - 280, 25), "Europa Consulting GmbH", fill="white", font=font_medium)

    y = 90

    # 請求書情報
    info_lines = [
        ("Rechnungsnr. / Invoice No:", "RE-2026-03871"),
        ("Datum / Date:", "05. March 2026"),
        ("Faellig / Due Date:", "04. April 2026"),
        ("Waehrung / Currency:", "€ (Euro)"),
        ("USt-IdNr. / VAT ID:", "DE123456789"),
    ]
    for label, value in info_lines:
        draw.text((30, y), label, fill="#555555", font=font_normal)
        draw.text((280, y), value, fill="black", font=font_normal)
        y += 24

    y += 10

    # 宛先
    draw.text((30, y), "Rechnungsempfaenger / Bill To:", fill="#555555", font=font_medium)
    y += 26
    bill_to = [
        "TechVentures Europe B.V.",
        "Keizersgracht 123",
        "1015 CJ Amsterdam",
        "Netherlands",
        "VAT: NL987654321B01",
    ]
    for line in bill_to:
        draw.text((30, y), line, fill="black", font=font_normal)
        y += 22

    y += 15

    # 明細テーブル
    headers = ["Beschreibung / Description", "Menge", "Einzelpreis", "Betrag"]
    col_widths = [400, 80, 130, 130]
    rows = [
        ["SAP S/4HANA Migration Beratung", "1", "€ 18.500,00", "€ 18.500,00"],
        ["Cloud-Architektur Design", "2", "€ 6.750,00", "€ 13.500,00"],
        ["Datenschutz-Audit (DSGVO)", "1", "€ 8.200,00", "€ 8.200,00"],
        ["Schulung / Training (pro Tag)", "4", "€ 2.400,00", "€ 9.600,00"],
        ["Projektmanagement (Monat)", "3", "€ 3.900,00", "€ 11.700,00"],
        ["Reisekosten / Travel expenses", "1", "€ 2.340,50", "€ 2.340,50"],
    ]
    y = _draw_table(draw, 30, y, headers, rows, col_widths, font_normal, font_medium)

    y += 15

    # 合計
    totals = [
        ("Zwischensumme / Subtotal:", "€ 63.840,50"),
        ("USt. / VAT (19%):", "€ 12.129,70"),
    ]
    for label, value in totals:
        draw.text((460, y), label, fill="#555555", font=font_normal)
        draw.text((690, y), value, fill="black", font=font_normal)
        y += 22

    y += 4
    draw.line([(460, y), (790, y)], fill="black", width=2)
    y += 6
    draw.text((460, y), "Gesamtbetrag / Total:", fill="black", font=font_medium)
    draw.text((690, y), "€ 75.970,20", fill="#2e5a1e", font=font_large)

    y += 45

    # 支払い情報
    draw.line([(30, y), (width - 30, y)], fill="#cccccc", width=1)
    y += 10
    draw.text((30, y), "Bankverbindung / Banking Details:", fill="#555555", font=font_medium)
    y += 26
    payment_lines = [
        "Bank: Deutsche Bank AG",
        "Kontoinhaber: Europa Consulting GmbH",
        "IBAN: DE89 3704 0044 0532 0130 00",
        "BIC/SWIFT: COBADEFFXXX",
    ]
    for line in payment_lines:
        draw.text((30, y), line, fill="black", font=font_normal)
        y += 20

    y += 10
    draw.text((30, y), "Zahlungsziel: 30 Tage netto / Payment terms: Net 30 days", fill="#555555", font=font_normal)

    # フッター
    draw.rectangle([(0, height - 35), (width, height)], fill="#f5f5f5")
    draw.text(
        (30, height - 28),
        "Europa Consulting GmbH | Friedrichstrasse 42, 10117 Berlin | HRB 12345 | GF: M. Schmidt",
        fill="#888888", font=font_small,
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out))
    print(f"EUR 請求書を生成しました: {out}")
    return str(out)


def create_sample_image(output_path: str = "sample_documents/sample.png") -> str:
    """基本的な OCR テスト用のサンプル画像を生成する。"""
    width, height = 800, 600
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    font_large, font_medium, font_normal, font_small = _load_fonts()

    # タイトル
    draw.text((50, 30), "OCR Comparison Test Document", fill="black", font=font_large)
    draw.line([(50, 65), (750, 65)], fill="gray", width=2)

    # 英語テキスト
    en_lines = [
        "1. Azure AI Document Intelligence provides OCR capabilities",
        "   for extracting text from documents and images.",
        "",
        "2. Azure AI Content Understanding offers unified content",
        "   analysis across documents, images, audio, and video.",
        "",
        "3. Both services support PDF, JPEG, PNG, TIFF, and BMP formats.",
        "",
        "4. Key comparison metrics:",
        "   - Processing speed",
        "   - Text extraction accuracy",
        "   - Word detection count",
        "   - Confidence scores",
    ]

    y = 90
    for line in en_lines:
        draw.text((50, y), line, fill="black", font=font_normal)
        y += 26

    # テーブル風のデータ
    draw.line([(50, y + 10), (750, y + 10)], fill="gray", width=1)
    y += 20
    draw.text((50, y), "Item           | Value     | Unit", fill="black", font=font_normal)
    y += 26
    draw.line([(50, y), (750, y)], fill="gray", width=1)
    y += 6
    table_rows = [
        "Temperature    | 23.5      | Celsius",
        "Humidity       | 65        | %",
        "Pressure       | 1013.25   | hPa",
        "Wind Speed     | 12.3      | km/h",
    ]
    for row in table_rows:
        draw.text((50, y), row, fill="black", font=font_normal)
        y += 24

    # フッター
    draw.line([(50, height - 50), (750, height - 50)], fill="gray", width=1)
    draw.text(
        (50, height - 40),
        "Generated for OCR comparison testing",
        fill="gray",
        font=font_normal,
    )

    # 出力
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out))
    print(f"サンプル画像を生成しました: {out}")
    return str(out)


def create_jpy_invoice(output_path: str = "sample_documents/invoice_jpy.png") -> str:
    """JPY 請求書のサンプル画像を生成する。"""
    width, height = 900, 820
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    font_large, font_medium, font_normal, font_small = _load_fonts()

    # 日本語フォント
    jp_font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/OTF/NotoSansCJK-Regular.ttc",
    ]
    jp_large = font_large
    jp_medium = font_medium
    jp_normal = font_normal
    jp_small = font_small
    for fp in jp_font_paths:
        if Path(fp).exists():
            try:
                jp_large = ImageFont.truetype(fp, 28)
                jp_medium = ImageFont.truetype(fp, 20)
                jp_normal = ImageFont.truetype(fp, 16)
                jp_small = ImageFont.truetype(fp, 13)
            except OSError:
                pass
            break

    # ヘッダー帯
    draw.rectangle([(0, 0), (width, 70)], fill="#c41e3a")
    draw.text((30, 15), "請 求 書", fill="white", font=jp_large)
    draw.text((width - 300, 25), "株式会社テクノソリューション", fill="white", font=jp_medium)

    y = 90

    # 請求書情報
    info_lines = [
        ("請求書番号:", "INV-2026-04521"),
        ("発行日:", "2026年3月10日"),
        ("支払期限:", "2026年4月10日"),
        ("通貨:", "JPY (日本円)"),
    ]
    for label, value in info_lines:
        draw.text((30, y), label, fill="#555555", font=jp_normal)
        draw.text((200, y), value, fill="black", font=jp_normal)
        y += 24

    y += 10

    # 宛先
    draw.text((30, y), "請求先:", fill="#555555", font=jp_medium)
    y += 26
    bill_to = [
        "グローバルテック株式会社",
        "東京都港区六本木1-2-3",
        "六本木ヒルズ 森タワー 42階",
        "担当: 田中 太郎 様",
    ]
    for line in bill_to:
        draw.text((30, y), line, fill="black", font=jp_normal)
        y += 22

    y += 15

    # 明細テーブル
    headers = ["品目 / 内容", "数量", "単価", "金額"]
    col_widths = [400, 80, 130, 130]
    rows = [
        ["システム基盤構築", "1", "¥3,500,000", "¥3,500,000"],
        ["API連携開発", "3", "¥850,000", "¥2,550,000"],
        ["データ移行作業 (1TB)", "2", "¥420,000", "¥840,000"],
        ["セキュリティ監査", "1", "¥1,200,000", "¥1,200,000"],
        ["運用保守 (月額)", "6", "¥180,000", "¥1,080,000"],
        ["技術研修 (1日)", "3", "¥250,000", "¥750,000"],
    ]
    y = _draw_table(draw, 30, y, headers, rows, col_widths, jp_normal, jp_medium)

    y += 15

    # 合計
    totals = [
        ("小計:", "¥9,920,000"),
        ("消費税 (10%):", "¥992,000"),
    ]
    for label, value in totals:
        draw.text((530, y), label, fill="#555555", font=jp_normal)
        draw.text((690, y), value, fill="black", font=jp_normal)
        y += 22

    y += 4
    draw.line([(530, y), (790, y)], fill="black", width=2)
    y += 6
    draw.text((530, y), "合計金額:", fill="black", font=jp_medium)
    draw.text((690, y), "¥10,912,000", fill="#c41e3a", font=jp_large)

    y += 45

    # 振込先情報
    draw.line([(30, y), (width - 30, y)], fill="#cccccc", width=1)
    y += 10
    draw.text((30, y), "お振込先:", fill="#555555", font=jp_medium)
    y += 26
    payment_lines = [
        "銀行名: 三菱UFJ銀行 東京営業部",
        "口座種別: 普通",
        "口座番号: 1234567",
        "口座名義: カ）テクノソリューション",
    ]
    for line in payment_lines:
        draw.text((30, y), line, fill="black", font=jp_normal)
        y += 20

    y += 10
    draw.text((30, y), "※ 振込手数料はお客様のご負担でお願いいたします。", fill="#555555", font=jp_normal)
    y += 20
    draw.text((30, y), "※ お支払期限を過ぎた場合、年14.6%の遅延損害金が発生いたします。", fill="#555555", font=jp_normal)

    # フッター
    draw.rectangle([(0, height - 35), (width, height)], fill="#f5f5f5")
    draw.text(
        (30, height - 28),
        "株式会社テクノソリューション | 東京都千代田区丸の内1-1-1 | TEL: 03-1234-5678 | 登録番号: T1234567890123",
        fill="#888888", font=jp_small,
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out))
    print(f"JPY 請求書を生成しました: {out}")
    return str(out)


if __name__ == "__main__":
    create_sample_image()
    create_usd_invoice()
    create_eur_invoice()
    create_jpy_invoice()
