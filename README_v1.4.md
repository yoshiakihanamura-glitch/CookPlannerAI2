# CookPlanner AI v1.4 - AIシェフ MVP

## 追加機能

- 冷蔵庫、直近の献立、妊娠中の条件をOpenAI APIへ送信
- 主菜・副菜・汁物をAIが提案
- ウェブ検索対応モデルでは、一般的な料理情報を確認して提案
- 提案を今日の献立へワンクリック反映
- 新しい料理はレシピデータへ自動保存
- AIが作った料理名・材料・手順を採用前に確認可能

## 最初の1回だけ必要

```powershell
python -m pip install -r requirements.txt
```

OpenAI APIキーが必要です。AIシェフ画面で毎回入力するか、環境変数 `OPENAI_API_KEY` に設定してください。

## 起動

```powershell
python -m streamlit run app.py
```

## 注意

AIの提案は必ず材料・加熱方法を確認してから採用してください。妊娠中の食品安全や体調については、医師・管理栄養士の指示を優先してください。
