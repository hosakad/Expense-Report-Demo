# Expense Report Demo

## プロジェクト概要

Pendoのデモ用途で作られたFlaskベースの経費精算Webアプリケーション。経費入力・レポート作成・承認ワークフローを備え、Pendo Analyticsのトラッキングが組み込まれている。

実際のSaaS製品を模したデモアプリであり、本番運用を想定した設計ではない。

## 技術スタック

| 分類 | 技術 |
|---|---|
| バックエンド | Python 3.12.5 / Flask |
| データベース | PostgreSQL (psycopg2-binary / SQLAlchemy) |
| キャッシュ | Redis (i18nメッセージのキャッシュに使用) |
| 画像処理 | Pillow |
| HTTPクライアント | requests |
| デプロイ | Gunicorn / Heroku (Procfile) |
| アナリティクス | Pendo (埋め込みスクリプト + Track Events API) |
| フロントエンド | Jinja2テンプレート / HTML / CSS (フレームワーク不使用) |
| 多言語対応 | JSON辞書ファイル (ja-JP / en-US) |

## ディレクトリ構成

```
Expense-Report-Demo/
├── expense_report_demo.py   # Flaskアプリ本体。全ルートと業務ロジック
├── constants.py             # アプリ全体の定数定義
├── utilities.py             # Pendo連携・Redis・言語設定などのユーティリティ
├── db_operations.py         # PostgreSQL接続・SELECT/EXECUTEラッパー
├── file_operations.py       # レシート画像のアップロード・削除
├── requirements.txt
├── runtime.txt
├── Procfile
├── static/
│   ├── css/main.css
│   ├── images/receipt/      # アップロードされたレシート画像の保存先
│   └── json/
│       ├── messages_en-US.json
│       └── messages_ja-JP.json
├── templates/
│   ├── common/              # framework.html, header.html, navigator.html
│   ├── login.html / logout.html
│   ├── expense_*.html       # 経費関連画面
│   ├── report_*.html        # レポート関連画面
│   ├── approve_list.html    # 承認者画面
│   ├── employee_*.html      # 管理者向け従業員管理画面
│   └── error.html
└── docs/
    ├── todo.md
    ├── architecture.md
    ├── issues.md
    └── roadmap.md
```

## 必要な環境変数

```
FLASK_SECRET_KEY              # セッション暗号化キー
DATABASE_URL                  # PostgreSQL接続文字列
DATABASE_SCHEMA               # PostgreSQLのスキーマ名
PENDO_API_KEY                 # Pendo埋め込み用APIキー
PENDO_API_KEY_2               # Pendo埋め込み用APIキー（2つ目）
PENDO_TRACK_EVENT_SECRET_KEY  # PendoトラックイベントAPI用キー
REDIS_URL                     # Redis接続URL
```

## 作業上の注意事項

### 壊してはいけない部分

- **Pendo初期化スクリプト** (`templates/common/header.html`)
  - visitorId・accountIdの形式、渡すメタデータの構造を勝手に変えない
  - Pendoのデモ用途がこのアプリの本質であるため

- **多言語対応の仕組み** (`utilities.py` の `set_language()`, `get_text()`)
  - RedisキャッシュとAccept-Languageヘッダーを使って動作している
  - ja-JP と en-US の両JSONファイルのキー名は常に揃えておくこと

- **定数名** (`constants.py`)
  - SQLクエリ・テンプレート・JSONキーが定数名に依存している
  - `STATUS_APRROVED` のタイポも含め、DBデータと一致しているため**リネーム不可**

- **DBスキーマ** (`DATABASE_SCHEMA` 変数経由で全クエリに差し込まれる)
  - テーブル名・カラム名を変更する場合は全SQLを一括で更新すること

### 開発時の注意

- SQLは `db_operations.py` の `sql_select()` / `sql_execute()` を通じて実行する
- ファイル操作は `file_operations.py` を通じて行い、Pendoイベントも同時に送ること
- Pendoパラメータは `utilities.py` の `getPendoParams()` で生成し、全テンプレートに渡すこと
- ロール (`ROLE_ADMIN`, `ROLE_APPROVER`, `ROLE_USER`) による画面表示の出し分けは `navigator.html` と各ルートのセッションチェックで行っている
