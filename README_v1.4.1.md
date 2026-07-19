# CookPlanner AI v1.4.1 - 無料AIブリッジ

## 今回の変更

- OpenAI APIキーとAPI課金を完全に廃止
- 冷蔵庫、期限、直近14日間の献立、妊娠情報をまとめたプロンプトを自動生成
- ChatGPTへ貼るプロンプトをワンクリックでコピー
- コピー前にプロンプト全文を確認可能
- ChatGPTの回答をアプリへ貼り戻して保存可能
- 既存の冷蔵庫、献立、買い物、レシピデータを同梱

## 起動

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## テスト手順

1. 左メニューの「🤖 AIシェフ」を開く
2. 今日の希望を選ぶ
3. 「ChatGPT用プロンプトをコピー」を押す
4. ChatGPTへ貼って送信する
5. 返答を「ChatGPTの回答を貼る」へ丸ごと貼る
6. 「この回答を保存」を押す

この版では回答の保存までです。次版で、回答を主菜・副菜・汁物・買い物へ自動分解します。
