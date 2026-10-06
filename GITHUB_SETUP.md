# GitHub 上傳與更新

本機 repository 根目錄：`F:\HKBU_Y4\FYP\My_FYP`。
遠端：`https://github.com/Graham-Hz/FYP_Game.git`。

已初始化本機 Git、連接 origin，並接上遠端已有的 main 初始 commit。`.gitignore` 已排除大型資料和環境；原始資料仍留在磁碟。本次準備沒有替使用者執行 commit 或 push。

## 第一次上傳目前工作

在 PowerShell 逐行執行：

```powershell
Set-Location 'F:\HKBU_Y4\FYP\My_FYP'
git status --short
git add .
git diff --cached --stat
git commit -m "Add FYP data audit and candidate cleaning pipeline"
git push -u origin main
```

`git diff --cached --stat` 顯示這次準備提交的檔案。預期包括程式、研究報告、設定與資料來源文件，不應有大型 CSV／Parquet、ZIP 或 `.venv`；研究報告內的小型 CSV 應保留。

若 Git Credential Manager 要求登入，在它開啟的登入流程使用有此 repository 寫入權限的 GitHub 帳號。不要把密碼或 token 貼進程式、聊天或 repository。登入與 push 成功後，GitHub 的 main 頁面應顯示 Program、Dataset 的來源文件及根目錄 README。

## 日後更新

```powershell
Set-Location 'F:\HKBU_Y4\FYP\My_FYP'
git status
git add .
git diff --cached --stat
git commit -m "Describe this update"
git push
```

每次 commit 訊息應描述實際改動，例如 `Refine mobile price validation`。只有產生變更時才需要 commit。首次上傳後，日後開始工作前可在沒有未提交改動時執行 `git pull --ff-only`。

如果 push 顯示遠端有新 commit 而被拒絕，先執行 `git fetch origin` 並檢查差異，不要使用 `--force` 覆蓋遠端歷史。

## 官方參考

- [將本機 Git 專案上傳到 GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)
- [GitHub 大型檔案限制](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
