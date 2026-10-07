# GitHub 提交指南（轻量聊天室）

> **这份文档是干什么的**：把本地 `chat` 项目上传到 GitHub 的完整步骤记录。
> 每一步都是本机实际执行过的，命令可以直接照抄。
> 答辩时如果老师问"代码为什么这么提交、哪些文件没上传"，照本文回答即可。

---

## 一、提交前必须确认的 3 件事

在敲任何命令之前，先确认下面三点，否则会把自己的隐私一起传上公网。

### 1. 哪些文件**绝对不能**上传

| 文件 / 目录 | 大小 | 为什么不能传 |
|---|---|---|
| `backend\.venv\` | 约 48 MB | 虚拟环境，别人电脑上重建就好，传上去只会把仓库撑大 |
| `backend\chat.db` | 不定 | 数据库，里面有**真实账号和聊天记录** |
| `tools\cpolar_token.txt` | 很小 | **你个人的穿透平台凭证，泄露等于把账号给了别人** |
| `tools\cpolar\cpolar.exe` | 约 19 MB | 第三方客户端，不是项目源码，要用时从官网下载 |
| `.vscode\` | 很小 | 里面写的是**你这台电脑的绝对路径**，别人拿到没用 |
| `__pycache__\`、`*.pyc`、`*.log` | 很小 | Python 运行缓存和日志，属于自动生成物 |

### 2. 用一个 `.gitignore` 文件"拦住"它们

Git 靠项目根目录的 `.gitignore` 判断哪些文件不跟踪。本项目的内容和逐条解释：

```
# ---- Python 的临时文件 ----
__pycache__/
*.pyc

# ---- 虚拟环境：48 MB，绝对不能提交 ----
backend/.venv/

# ---- 数据库：里面有你的聊天记录和账号 ----
*.db

# ---- 内网穿透的个人凭证 ----
tools/cpolar_token.txt

# ---- 第三方穿透客户端：18 MB，要用时从官网下载 ----
tools/cpolar/cpolar.exe

# ---- VS Code 的本地设置 ----
.vscode/

# ---- 测试脚本的日志 ----
*.log
```

> 注意：`.gitignore` 只对**还没被 Git 跟踪**的文件生效。
> 如果不小心已经 `git add` 过一个文件（例如 `chat.db`），光加进 `.gitignore` 是没用的，
> 要先用 `git rm --cached backend/chat.db` 把它从跟踪列表里踢出去再重新提交。

### 3. 用一条命令自查（提交前跑一次）

```
git status
```

看输出的 `Untracked files` / `Changes to be committed` 里有没有上面表格里的东西。
更直接的办法是列出"已被跟踪的文件"，一条条对：

```
git ls-files
```

**判断标准**：输出里**不应该**出现 `.venv`、`chat.db`、`cpolar.exe`、`cpolar_token.txt`。
本项目实际输出为 27 个文件，全部是源码、脚本和文档。

---

## 二、一次性准备

### 1. 确认装了 Git

打开命令行敲：

```
git --version
```

本机结果是 `git version 2.56.0.windows.2`。没有的话去 <https://git-scm.com> 下载安装，一路默认即可。

### 2. 设置"署名"（每台电脑只需做一次）

Git 每次提交都要记录"是谁提交的"，所以必须先告诉它名字和邮箱。
以下 4 条命令在**任意目录**敲都行（`--global` 表示对这台电脑所有仓库生效）：

```
git config --global user.name "hlh228"
git config --global user.email "312868540@qq.com@example.com"
git config --global core.quotepath false
git config --global core.autocrlf true
```

四条命令分别解决什么：

| 命令 | 作用 | 不设置会怎样 |
|---|---|---|
| `user.name` | 提交记录里的署名（建议用 GitHub 用户名） | 提交时报错 `Please tell me who you are` |
| `user.email` | 提交记录里的邮箱（**建议填 GitHub 账号的邮箱**） | 同上；邮箱不对，GitHub 不会把提交算到你账号名下 |
| `core.quotepath false` | 正常显示中文文件名 | 中文文件名会变成 `\346\226\207\344\273\266` 这种乱码 |
| `core.autocrlf true` | 提交时把换行符统一成 LF，检出时还原成 CRLF | 脚本换行符被打乱，`.bat` 双击可能出问题 |

> ⚠️ 本机 `user.email` 当时写成了 `312868540@qq.com@example.com`（多了一截 `@example.com`），
> 属于笔误。它不影响提交和推送，只是 GitHub 上不会显示"这是你的提交"。
> 要改正：`git config --global user.email "你的真实邮箱"`（改完只影响以后的提交）。

### 3. 补充：换行符的"双保险"——`.gitattributes`

`.gitignore` 管"哪些文件不传"，`.gitattributes` 管"传上去以后换行符按什么规矩存"。
本项目根目录的 `.gitattributes`：

```
*.bat text eol=crlf
*.py  text eol=lf
*.js  text eol=lf
```

意思是：`.bat` 脚本在别人电脑上检出时用 Windows 换行（保证双击能跑），
`.py` / `.js` 用 Linux 换行（跨平台最安全）。
配合上面的 `core.autocrlf true`，两边都不会被改坏。

### 4. 确认自己在正确的目录

后面所有 Git 命令**都要在项目根目录**（也就是含 `PRD.md`、`backend`、`frontend` 的那个文件夹）里敲：

```
cd /d C:\Users\XiaoXin\Desktop\code\chat
```

> CMD 里换盘符必须用 `cd /d`；只写 `cd C:\...` 有时切不过去。
> 敲完看提示符结尾是不是 `\code\chat>`，或敲 `git status` 看会不会报
> `fatal: not a git repository`（报这个就说明目录不对）。

---

## 三、把本地文件夹变成 Git 仓库，并做第一次提交

在 `chat` 目录里依次敲（顺序不能乱）：

```
git init -b main
git add .
git status
git commit -m "首次提交：轻量聊天室（前后端 + 测试 + 文档）"
```

逐条解释：

| 命令 | 做什么 |
|---|---|
| `git init -b main` | 在当前文件夹里建一个隐藏的 `.git` 文件夹，把这里变成"仓库"，初始分支名叫 `main` |
| `git add .` | 把当前目录下**没有被 `.gitignore` 排除**的所有文件放进"待提交区" |
| `git status` | **只查看不修改**。确认待提交清单里没有被排除的大文件/隐私文件 |
| `git commit -m "..."` | 把待提交区的内容打包成一个"版本"，引号里是这次提交的说明 |

> 本项目的**分界线就在 `git add` 这一步**：
> `.venv`、`chat.db`、`cpolar.exe`、`cpolar_token.txt` 都已写进 `.gitignore`，
> 所以它们不会被加进来，`git status` 里看不到，GitHub 上也不会有。
>
> 本机实际结果：`git ls-files` 输出 27 个文件，`git log --oneline` 显示
> `593032c 首次提交：轻量聊天室（前后端 + 测试 + 文档）`。

**如果 `git commit` 报 `Please tell me who you are`**：回去做第二节第 2 步（设置名字和邮箱）。

---

## 四、在 GitHub 上建一个**空**仓库

1. 登录 <https://github.com>，右上角 `+` → `New repository`
2. `Repository name` 填 **`chat`**（和本地文件夹同名，好对应）
3. 选 **`Public`**（评阅/答辩方便老师直接看；选 Private 的话对方要登录才能看）
4. **关键**：下面三个复选框**一个都不要勾**
   - ❌ `Add a README file`
   - ❌ `Add .gitignore`
   - ❌ `Choose a license`
5. 点 `Create repository`

> **为什么必须留空？** 如果 GitHub 帮你生成了 README 等文件，远程仓库里就有本地没有的提交，
> 之后 `git push` 会被拒绝（报 `rejected ... non-fast-forward`）。
> 留空仓库第一次推送才顺畅。README 本地已经有了，会随本次推送一起上去。
>
> 建好后页面上会出现 3 条命令提示，告诉我们远程地址是：
> `https://github.com/hlh228/chat.git`

---

## 五、把本地仓库和 GitHub 连起来（2 条命令）

在 `chat` 目录里敲：

```
git remote add origin https://github.com/hlh228/chat.git
git remote -v
git push -u origin main
```

| 命令 | 做什么 |
|---|---|
| `git remote add origin <网址>` | 给本地仓库登记一个"远程仓库地址"，给它起的代号叫 `origin`（习惯叫法，不是关键字） |
| `git remote -v` | 查看登记结果，正常会打印出 fetch / push 两行同样的地址 |
| `git push -u origin main` | 把本地 `main` 分支推送到 `origin`；`-u` 表示"记住这套搭配"，以后只敲 `git push` 就行 |

> `git remote -v` 如果**没有任何输出**，说明 `git remote add` 那一步没成功（多半是拼错了网址），重敲一次即可。

### 推送时的登录（第一次会遇到）

第一次推送会弹出 **Connect to GitHub** 窗口，有两个标签页，任选其一：

**办法 A（推荐，最省事）** —— 用浏览器登录
1. 选 `Browser/Device` 标签 → 点 **`Sign in with your browser`**
2. 弹出浏览器，用 GitHub 账号登录后点绿色的 **Authorize / 授权** 按钮
3. 浏览器显示授权成功后，**回到原来的命令行窗口**（不要关它），push 会自动继续

**办法 B** —— 用令牌（Token）
1. 打开 <https://github.com/settings/tokens/new>（Settings → Developer settings → Personal access tokens → Tokens (classic)）
2. `Note` 随便填，比如 `chat-push`；`Expiration` 选个较短的期限（如 30 天）
3. 勾选 **`repo`** 这个权限（一个勾就够）
4. 点最下面 `Generate token`，页面会显示一串 `ghp_xxxxxxxx...`
5. **立刻复制**（关掉页面就再也看不到了）
6. 回到弹窗选 `Token` 标签：`Username` 填 `hlh228`，`Password` 处**粘贴这串 token**
   （⚠️ 不是 GitHub 登录密码！GitHub 早已禁止用账号密码推送）

> 无论 A 还是 B，成功后凭据都由 Windows 凭据管理器保存，以后再 push 不用重复输入。
> **安全提醒**：办法 B 用的是长期有效的令牌，推送完成后建议到 <https://github.com/settings/tokens>
> 把它 **Delete** 掉；下次需要时重新生成一个即可，本地已保存的凭据不受影响。

### 怎么算成功了

命令行出现类似下面的输出就是成功：

```
* [new branch]      main -> main
branch 'main' set up to track 'origin/main'.
```

再刷新 <https://github.com/hlh228/chat> 页面，应该能看到 27 个文件
（`.gitignore`、`README.md`、`PRD.md`、`TECH_DESIGN.md`、`database.md`、
`backend/`、`frontend/`、`一键内网穿透.bat` 等）。

想在本机再次确认，敲：

```
git log --oneline
git branch -vv
```

`git branch -vv` 里若出现 `[origin/main]`，说明本地和远程已对上，提交确实推上去了。

---

## 六、以后改完代码，怎么再传一次（日常三步）

只需三条命令，不用再 `init` / `add remote`：

```
git add .
git commit -m "简单说明这次改了什么"
git push
```

> 建议改成"看得到"的两步走，避免手滑把不想传的东西带上：
> `git status`（看清单）→ `git add .` → `git status`（再确认一次）→ `git commit -m "..."` → `git push`。

**只改了一个文件时**也可以单独提交：`git add PRD.md`。

---

## 七、常见报错对照表（照着右边做就行）

| 报错 / 现象 | 原因 | 怎么办 |
|---|---|---|
| `fatal: not a git repository` | 不在 `chat` 目录里，或还没 `git init` | `cd /d C:\Users\XiaoXin\Desktop\code\chat` |
| `Please tell me who you are` | 没配名字/邮箱 | `git config --global user.name "hlh228"` 和 `user.email` |
| `Support for password authentication was removed` | 把 GitHub 登录密码当密码填了 | 改用浏览器授权，或改用 `ghp_` 开头的 token |
| `fatal: remote origin already exists` | `origin` 已经加过了 | 改地址：`git remote set-url origin https://github.com/hlh228/chat.git` |
| `remote -v` 没有任何输出 | `git remote add` 没成功 | 重新敲一次并核对网址拼写 |
| `src refspec main does not match any` | 还没有任何提交，或分支名不是 `main` | 先 `git commit`；用 `git branch` 看当前分支名 |
| `rejected ... non-fast-forward` / `failed to push some refs` | 远程有本地没有的提交（例如建仓库时勾了 README） | `git pull --rebase origin main` 再 `git push` |
| `Failed to connect to github.com` | 网络/代理问题 | 换个网络重试；再不行检查是否有代理软件 |
| `LF will be replaced by CRLF` （黄色 warning） | 换行符自动转换的**正常提示** | 不用管，不影响提交 |
| `Unable to create '.../.git/index.lock'` | 上一次 Git 被中途关掉了 | 删掉 `.git\index.lock` 后重试，并确保没有其他 Git 窗口在跑 |
| 中文文件名显示成 `\346\226\207...` | Git 默认转义中文 | `git config --global core.quotepath false` |
| 双击 `.bat` 一闪而过 | 换行符被改成 LF 了 | 确认 `.gitattributes` 里有 `*.bat text eol=crlf`，然后重新检出该文件 |

---

## 八、CMD 和 PowerShell 的区别（本次踩过的坑）

本次推送是在 **CMD 窗口**（提示符形如 `C:\...\code\chat>`）里做的。
CMD 和 PowerShell 有些命令不一样，混淆了会报"无法识别"：

| 用途 | CMD 写法 | PowerShell 写法 |
|---|---|---|
| 切到另一个盘符 | `cd /d C:\Users\XiaoXin\Desktop\code\chat` | `cd C:\Users\XiaoXin\Desktop\code\chat` |
| 查看文件内容 | `type README.md` | `Get-Content README.md` |
| 统计有几行 | `find /c /v ""` | `(Get-Content xxx).Count` |
| 清屏 | `cls` | `cls` 或 `Clear-Host` |

**结论：整篇文档的命令全是 Git 自己的命令（`git ...`），CMD 和 PowerShell 里都能用。**
只有"辅助查看文件"这类命令要注意别串用。
最省事的做法：直接用 **VS Code 自带终端**（菜单 `终端 → 新建终端`，快捷键 <kbd>Ctrl</kbd>+<kbd>`</kbd>），
它默认就在项目根目录，且默认是 PowerShell——本文档的 `git` 命令都能直接跑。

---

## 九、安全与收尾（重要）

1. **数据库不上传**：`chat.db` 被 `.gitignore` 排除，仓库里只有代码。
   自己演示时数据库照旧在 `backend\chat.db`，功能不受任何影响。
2. **穿透凭证要清理**：`tools\cpolar_token.txt` 是你的个人 token，
   上交或公开仓库前删除；cpolar 还会在 `C:\Users\XiaoXin\.cpolar\cpolar.yml` 里存一份，需要时两处都删。
3. **令牌用完就删**：如果走了"办法 B"，推送完去 <https://github.com/settings/tokens> 把它 Delete。
4. **公网演示完立刻关隧道**：穿透开着时，任何人拿到地址都能注册账号、读写数据。
5. **`.vscode/` 不上传**：里面的 `tasks.json` 写死了本机绝对路径，别人拿了也用不了，
   已被 `.gitignore` 排除（本机仍在，`Ctrl + Shift + B` 一键启动后端照常可用）。
6. **提交后想改文档**：直接改文件，再走第六节的 `add / commit / push` 三条命令即可。

---

## 十、本次提交记录（可作为答辩时的"提交证据"）

| 项目 | 内容 |
|---|---|
| Git 版本 | `git version 2.56.0.windows.2` |
| 本地仓库路径 | `C:\Users\XiaoXin\Desktop\code\chat` |
| 远程仓库地址 | <https://github.com/hlh228/chat>（Public） |
| 远程地址（命令用） | `https://github.com/hlh228/chat.git` |
| 分支 | `main`（本地与 `origin/main` 同步） |
| 首次提交 | `593032c` 首次提交：轻量聊天室（前后端 + 测试 + 文档） |
| 提交文件数 | 27 个（源码 + 脚本 + 文档） |
| 未上传（按设计排除） | `backend\.venv\`、`backend\chat.db`、`tools\cpolar_token.txt`、`tools\cpolar\cpolar.exe`、`.vscode\`、`__pycache__\` |
| 提交日期 | 2026-10-07 |

**注意**：`README.md` 是仓库的"门面"，GitHub 打开仓库首页会自动展示它，
所以它是老师最先看到的东西，内容保持简洁、突出"怎么启动、怎么测试"即可。

---

*本文件由项目作者整理，属于项目文档的一部分。若与实际操作有出入，以实际命令输出为准。*
