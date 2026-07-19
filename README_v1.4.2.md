# CookPlanner AI v1.4.2 - スマホ公開対応

## 今回の変更

- スマホ画面向けに余白、文字、ボタン、入力欄を調整
- スマホではサイドバーを初期状態で閉じる設定に変更
- 家族用パスワード画面を追加
- Streamlit Community Cloud向け設定を追加
- データ一式をZIPでバックアップ・復元できる機能を追加
- OpenAI APIは使わないため、AI利用の追加課金はなし

## ローカル起動

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

ローカルではパスワード未設定でも起動できます。
パスワードを試す場合は、`.streamlit/secrets.toml.example` を
`.streamlit/secrets.toml` にコピーし、`APP_PASSWORD`を書き換えてください。

## Streamlit Community Cloudへ公開

1. このフォルダの内容をGitHubリポジトリへPush
2. `share.streamlit.io`へGitHubでログイン
3. `Create app`を押す
4. 対象リポジトリ、ブランチ、`app.py`を選ぶ
5. Advanced settingsのSecretsへ次を入力

```toml
APP_PASSWORD = "家族だけが知っているパスワード"
```

6. Deployを押す
7. 発行された`*.streamlit.app`のURLをスマホで開く
8. Safari/Chromeの「ホーム画面に追加」でアプリ風に利用可能

## データについての重要事項

Community Cloud上のCSV更新は永続保存が保証されません。
アプリの再起動や再デプロイの前後には、
`設定・バックアップ`からデータZIPを保存してください。

この版は無料公開を優先した構成です。将来、完全な自動永続保存が必要になった場合は、
無料枠のある外部データベースへの移行を検討します。
