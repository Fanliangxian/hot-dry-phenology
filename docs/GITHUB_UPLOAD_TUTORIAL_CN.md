# GitHub 上传教程（中文）

## 一、上传前必须完成的检查

1. 打开 `CITATION.cff`，填写最终作者、仓库网址和论文/Zenodo DOI。
2. 在 `README.md` 中补充通讯作者的公开联系方式。
3. 确认原始数据、WDPA/GAIA 文件、GEE 凭证和私人资产 ID 均未复制进仓库。
4. 在仓库根目录运行：

```powershell
python scripts/check_release.py
pytest -q
```

5. 查看待上传文件总大小，确认没有单个文件超过100 MB。

## 二、最稳妥的方法：GitHub 网页创建仓库＋本地 Git 上传

### 1. 在 GitHub 创建空仓库

1. 登录 https://github.com/ 。
2. 右上角点击 `+` → `New repository`。
3. Repository name 建议使用 `hot-dry-phenology`。
4. 简介可写：`Code and source data for compound hot–dry event effects on vegetation phenology.`
5. 投稿审稿阶段可以先选 `Private`；论文接收或数据政策要求公开时再改成 `Public`。
6. 不要勾选自动创建 README、LICENSE 或 `.gitignore`，因为本地包中已经存在。
7. 点击 `Create repository`。

### 2. 在本地初始化并首次上传

在 PowerShell 中进入本发布包目录：

```powershell
cd "<你的本地路径>\hot-dry-phenology-release"
git init
git branch -M main
git add .
git status
git commit -m "Initial research code release"
git remote add origin https://github.com/YOUR_ACCOUNT/hot-dry-phenology.git
git push -u origin main
```

把 `YOUR_ACCOUNT` 替换成你的 GitHub 用户名。如果 GitHub 要求登录，推荐使用浏览器授权或 Personal Access Token，不要把 Token 写入脚本、README 或远程地址。

### 3. 检查线上仓库

上传后逐项检查：

- README 首页是否正常显示；
- 图片能否打开；
- `DATA.md` 和复现说明链接是否有效；
- 是否意外出现本地路径、用户名、凭证或大型数据；
- `CITATION.cff` 是否被 GitHub 识别为 `Cite this repository`。

## 三、日常更新

修改文件后运行：

```powershell
git status
git add README.md src data docs
git commit -m "Update analysis documentation and figures"
git push
```

不要习惯性使用 `git add .` 上传未经检查的新数据。先看 `git status`，再选择具体目录。

## 四、创建可引用版本

1. 确认论文版本对应的代码已经冻结。
2. GitHub 仓库右侧点击 `Releases` → `Draft a new release`。
3. Tag 建议用 `v1.0.0`。
4. 标题可用 `Code and source data accompanying the manuscript`。
5. 在 release notes 中写明论文版本、主要分析基线和数据 DOI。
6. 发布 Release。

## 五、获取软件 DOI（推荐）

1. 登录 https://zenodo.org/ 并用 GitHub 账户授权。
2. 在 Zenodo 的 GitHub 设置中启用该仓库。
3. 回到 GitHub 发布新的 Release；Zenodo 会自动归档并生成 DOI。
4. 将 DOI 更新到 `CITATION.cff`、README 和论文 Code Availability statement。
5. 再发布一个只修改引用信息的小版本，例如 `v1.0.1`。

## 六、论文中的 Code Availability 建议写法

> The analysis and figure-generation code, together with lightweight figure source data and reproducibility documentation, are available at [GitHub URL] and archived at Zenodo ([DOI]). Raw third-party datasets are not redistributed and can be obtained from the original providers listed in the repository documentation.

## 七、常见问题

- **文件超过100 MB：** 不要强行上传；移出仓库，使用 Figshare/Zenodo，或在确认许可后使用 Git LFS。
- **推送时要求密码：** GitHub 已不支持账户密码进行 Git HTTPS 验证，使用浏览器登录、GitHub Desktop 或 Personal Access Token。
- **误传敏感文件：** 若尚未 push，先移出并重新 commit；若已经 push，立即把仓库设为 Private、撤销凭证，并使用 Git 历史清理工具。仅删除最新版本并不能从历史中移除秘密。
- **审稿期是否公开：** 可先保持 Private，并按期刊政策提供匿名归档；接收后再公开并创建正式 Release/DOI。
