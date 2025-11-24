# WP-AI GUI実装タスク

## フェーズ1: AIチャットGUI（MVP）

### Foundation
- [x] LLMClientにストリーミングAPI追加
- [x] chat_window.pyの実装
- [x] dialogs.pyの実装
- [x] GUIランチャーバッチファイル作成

### Core Features  
- [x] チャット表示とストリーミング対応
- [x] ホスト選択機能
- [x] コンテキスト制御パネル統合
- [x] LLM設定ダイアログ
- [x] エラーハンドリング

### Testing & Polish
- [ ] GUIの動作確認
- [ ] UTF-8エンコーディング対応確認
- [ ] UI調整（フォント、色）

## フェーズ2: メインランチャー（後続）
- [ ] launcher.pyの実装
- [ ] メニューボタン配置
- [ ] 既存CLI機能との統合

## フェーズ3: AIプランナー（後続）
- [ ] プラン生成UIの実装
- [ ] SSH実行の可視化
- [ ] 実行履歴管理
