# アーキテクチャ

## 現在の全体構成

```
ブラウザ
  │  HTTP(S)
  ▼
Gunicorn (WSGIサーバー)
  │
  ▼
Flask アプリ (expense_report_demo.py)
  │
  ├── PostgreSQL (psycopg2)   ← 全データの永続化
  ├── Redis                   ← i18nメッセージのセッションキャッシュ
  └── Pendo Track Events API  ← ファイル操作イベントの送信 (requests)
```

現状はサーバーサイドレンダリング（SSR）のモノリシック構成。FlaskルートがHTMLを直接返す。APIとフロントエンドの分離はない。

---

## データベース構成

### テーブル一覧

#### `company` テーブル
| カラム | 型 | 説明 |
|---|---|---|
| id | PK | 会社ID |
| name | text | 会社名 |
| plan | text | プラン (`Advanced` / `Standard`) |

#### `employee` テーブル
| カラム | 型 | 説明 |
|---|---|---|
| id | PK | 従業員ID |
| first_name | text | 名 |
| last_name | text | 姓 |
| email | text | メールアドレス（ユニーク） |
| password | text | パスワード（平文） |
| role | text | `ROLE_ADMIN` / `ROLE_APPROVER` / `ROLE_USER` |
| company_id | FK | 所属会社 |

#### `expense` テーブル
| カラム | 型 | 説明 |
|---|---|---|
| id | PK | 経費ID |
| name | text | 経費名 |
| date | date | 発生日 |
| amount | numeric | 金額 |
| currency | text | `CURRENCY_DOLLAR` / `CURRENCY_YEN` |
| description | text | 備考 |
| receipt_image | text | 画像ファイル名（NULLable） |
| user_id | FK | 作成者（employee.id） |
| report_id | FK | 紐付け先レポートID（NULLable） |

#### `report` テーブル
| カラム | 型 | 説明 |
|---|---|---|
| id | PK | レポートID |
| name | text | レポート名 |
| user_id | FK | 作成者（employee.id） |
| status | text | `STATUS_OPEN` / `STATUS_SUBMITTED` / `STATUS_APRROVED`(※) |
| submit_date | date | 提出日（NULLable） |
| approve_date | date | 承認日（NULLable） |

※ `STATUS_APRROVED` はタイポ。DBデータと一致しているため変更不可。

---

## 主要な処理フロー

### ログインフロー

```
POST /authenticate
  │
  ├── SQLで employee + company を JOIN して email/password で照合
  ├── 一致すればセッションに employee_id, role, company_id などを保存
  └── ロールに応じてリダイレクト
        ROLE_USER/ROLE_APPROVER → /user_home
        ROLE_ADMIN              → /employee_list_html
```

### 経費作成フロー

```
GET /expense_new_html
  └── フォーム表示（デフォルト通貨はAccept-Languageで決定）

POST /create_expense
  ├── ファイルがあれば file_operations.save_file() で保存
  │     └── static/images/receipt/{UUID}_{secure_filename} として保存
  │     └── Pendo Track Event "File Uploaded" 送信
  └── SQL INSERT INTO expense
```

### レポート提出・承認フロー

```
[User] POST /submit_report
  └── report.status → STATUS_SUBMITTED, submit_date に現在日付を設定

[Approver] GET /approve_list_html
  └── 自社の STATUS_SUBMITTED / STATUS_APRROVED のレポートを取得

[Approver] POST /approve_report
  └── report.status → STATUS_APRROVED, approve_date に現在日付を設定

[Approver] POST /reject_report
  └── report.status → STATUS_OPEN, submit_date → NULL にリセット
```

### 多言語対応フロー

```
リクエスト受信
  │
  ├── session に language が未設定の場合:
  │     Accept-Language ヘッダーからロケールを判定
  │     対応JSONファイルを読み込み、Redisにキャッシュ
  │     session['language'] にロケール文字列を保存
  │
  └── テンプレート内で get_text(key) を呼び出してRediから翻訳文字列を取得
```

### Pendo連携フロー

```
全ページレンダリング時:
  utilities.getPendoParams() でセッションから visitor/account データ収集
  └── header.html の pendo.initialize({...}) に渡す

ファイル操作時:
  file_operations.save_file() / delete_file()
  └── utilities.send_track_event() → Pendo Track Events API (HTTP POST)
```

---

## セッション管理

- Flask の cookie-based session を使用（`FLASK_SECRET_KEY` で署名）
- セッション有効期限: 24時間 (`session.permanent = True`)
- セッションに保存される主なキー:

| キー（constants.py） | 内容 |
|---|---|
| `SESSION_EMPLOYEE_ID` | ログイン中の従業員ID |
| `SESSION_EMAIL` | メールアドレス |
| `SESSION_ROLE` | ロール |
| `SESSION_COMPANY_ID` | 会社ID |
| `SESSION_COMPANY_NAME` | 会社名 |
| `SESSION_COMPANY_PLAN` | プラン |
| `SESSION_FIRST_NAME` / `SESSION_LAST_NAME` | 氏名 |
| `SESSION_LANGUAGE` | 表示言語 |
| `SESSION_REDIS_KEY` | RedisキャッシュキーのPrefix |
