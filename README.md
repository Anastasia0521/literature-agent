# Python 文献自动推送（Web of Science + Q1 + GPT 方法抽取 + Excel + 163 邮件）

本项目用于定时抓取近 3 个月 **Web of Science** 新发表/在线发表文献，按 **JCR 分区（默认 Q1）** 做期刊质量筛选，使用 **GPT** 辅助抽取“研究方法”，生成 Excel，并通过 **163 邮箱 SMTP** 自动推送。

同时预留一个“带密码的简单网页后台”（FastAPI），用于修改搜索关键词、推送频率、接收邮箱、每次返回上限、期刊筛选等级等配置，并做到**修改后立即生效**（配置落盘到 `data/settings.json`）。

---

## 目录结构

- `main.py`：主程序（拉取→过滤→抽取→导出→邮件）
- `config.py`：配置与环境变量读取（适配 GitHub Actions Secrets）
- `modules/`：功能模块（WoS、期刊筛选、GPT 抽取、Excel、邮件、设置存储）
- `data/settings.json`：可被网页后台修改的运行时配置（立即生效）
- `data/journals_q1.csv`：可选的 **Q1 期刊白名单**（推荐维护）
- `output/`：导出的 Excel
- `.github/workflows/literature_push.yml`：GitHub Actions 定时运行

---

## 你需要准备的账号与密钥

### 1) Web of Science API
- 你需要可用的 **Web of Science API Key**（不同机构开通的 API 类型可能不同）。
- 本项目以“REST/JSON”方式请求；如果你用的是不同版本（如 Starter/Expanded），只需要在 `config.py` 里调整 `WOS_BASE_URL` 与字段解析即可。

### 2) 163 邮箱 SMTP
- 需要 163 邮箱账号 + **SMTP 授权码**（不是登录密码）。
- SMTP：`smtp.163.com`，SSL 端口通常为 `465`。

### 3) GPT（OpenAI 兼容）
- 支持 OpenAI 官方或“兼容 OpenAI API 的服务商”。
- 需要 `OPENAI_API_KEY`，可选 `OPENAI_BASE_URL`、`OPENAI_MODEL`。

---

## 本地运行

1) 安装依赖

```bash
pip install -r requirements.txt
```

2) 复制并填写环境变量

把下方环境变量放到系统环境变量或新建 `.env`（不要提交到仓库）：

- `WOS_API_KEY`
- `EMAIL_163_USER`
- `EMAIL_163_PASS`（SMTP 授权码）
- `OPENAI_API_KEY`

3) 运行

```bash
python main.py
```

导出文件在 `output/`，并会邮件推送给 `data/settings.json` 配置的收件人。

---

## GitHub Actions 部署（定时推送）

1) 把本项目推到 GitHub 仓库
2) 在仓库 Settings → Secrets and variables → Actions → Secrets 添加：
- `WOS_API_KEY`
- `EMAIL_163_USER`
- `EMAIL_163_PASS`
- `OPENAI_API_KEY`
- （可选）`OPENAI_BASE_URL`、`OPENAI_MODEL`
3) 启用 Actions。工作流会按 `.github/workflows/literature_push.yml` 的 cron 定时运行。

---

## 关于 “JCR Q1” 过滤说明（重要）

**JCR 分区不是所有 WoS API 响应都直接返回**，且 JCR 本身也属于付费数据。

因此本项目提供两种筛选路径（可以同时启用）：
- **白名单法（推荐）**：维护 `data/journals_q1.csv`（期刊名一列），程序只保留在白名单中的期刊；
- **字段法（若可用）**：若 WoS 返回中包含可识别的 quartile/Q1 标记字段，则直接使用该字段过滤。

默认策略是：**优先使用字段法；字段缺失则退化到白名单法；两者都不可用则给出告警并按“不过滤/或严格过滤”策略运行（可在 settings 配置）。**

---

## （预留）带密码网页后台

后续你要的后台功能会落在 `modules/admin_app.py`（FastAPI）：
- 登录（简单口令）
- 在线编辑 `data/settings.json`
- 保存后立即生效（下一次运行 `main.py` 读取最新 settings）

你可以用：

```bash
uvicorn modules.admin_app:app --host 0.0.0.0 --port 8000
```

> 说明：GitHub Actions 的定时任务环境不适合长期运行网页后台；后台更适合部署在一台常驻机器/容器里（带持久化磁盘），Actions 只负责定时执行推送脚本。

