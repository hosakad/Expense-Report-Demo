# ロードマップ

## 目標アーキテクチャ

現状のモノリシックなSSR構成を、Flask REST APIとフロントエンドに分離する。

```
現状:
  ブラウザ ──HTTP──▶ Flask (ルート + HTML生成 + SQLが混在)

目標:
  ブラウザ ──HTTP──▶ フロントエンド (SPA or 静的HTML+JS)
                          │ API呼び出し
                          ▼
                     Flask REST API (JSONを返す)
                          │
                     DB / Redis / Pendo
```

---

## フェーズ別の改修計画

### フェーズ1: 内部整理（破壊的変更なし）

既存の動作を壊さずに、コードの構造を整える。

**1-1. DB操作をルートハンドラから分離する**
- `db_operations.py` にクエリ関数を移す（例: `get_expenses_by_user()`, `create_report()` など）
- `expense_report_demo.py` のルートはDB関数を呼ぶだけにする
- 優先度: **高**（テスト追加の前提となる）

**1-2. SQLパラメータのバグ修正**
- タプル化漏れ (`params = (value,)`) を全箇所修正
- IN句の動的生成を適切なプレースホルダーに変更
- 優先度: **高**（現在バグが潜在している）

**1-3. ファイル操作の堅牢化**
- サーバーサイドのファイルサイズ・MIMEタイプ検証を追加
- `receipt_image` が `None` のチェックを追加
- 優先度: **中**

**1-4. DBコネクション管理の改善**
- 接続切断後の再接続ロジックを追加、またはコネクションプール（SQLAlchemy の pool）に移行
- 優先度: **中**

---

### フェーズ2: API化

Flaskのルートを JSON APIとして再設計する。

**2-1. 認証エンドポイントをAPI化**
- `POST /api/auth/login` → JWTまたはセッショントークンを返す
- `POST /api/auth/logout`

**2-2. リソースごとにAPIエンドポイントを整備**
- `GET/POST /api/expenses`
- `GET/PUT/DELETE /api/expenses/<id>`
- `GET/POST /api/reports`
- `GET/PUT/DELETE /api/reports/<id>`
- `POST /api/reports/<id>/submit`
- `POST /api/reports/<id>/approve`
- `POST /api/reports/<id>/reject`
- `GET/POST /api/employees` (管理者のみ)

**2-3. 認可ミドルウェアの追加**
- ロールベースのアクセス制御をデコレータで実装
- 会社IDによるデータ分離の保証

---

### フェーズ3: フロントエンド分離

**3-1. テンプレートをSPAに移行**
- 既存の Jinja2 テンプレートをベースに Vue.js または素の JavaScript で書き換え
- または Next.js などのSSRフレームワークで再実装

**3-2. 静的ファイルの外部配信**
- レシート画像を S3 等のオブジェクトストレージに移行
- `static/images/receipt/` への直接保存をやめる

---

## 改修の優先順位まとめ

| 優先度 | 内容 | 理由 |
|---|---|---|
| 1 | SQLパラメータのバグ修正 | 現在動かない機能がある可能性 |
| 2 | DB操作の分離 | テスト追加・API化の前提 |
| 3 | ファイル操作の堅牢化 | ユーザー向けのコア機能 |
| 4 | コネクション管理改善 | 長時間稼働時の安定性 |
| 5 | REST API化 | フロント分離の前提 |
| 6 | フロントエンド分離 | デモ用途では後回しでよい |

---

## デモアプリとしての割り切り

以下はデモ用途のため**対応しない**と判断してよい項目:

- パスワードのハッシュ化（デモのため平文でユーザーが確認できることが優先）
- CSRF保護（デモ環境でのセキュリティリスクは許容）
- `STATUS_APRROVED` タイポの修正（DBデータとの整合性維持コストが高い）
