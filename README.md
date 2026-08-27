# 微气候观测数据分析平台（Vercel 版）

这是原 `观测数据分析平台` 的 Vercel 部署副本，原文件夹未改动。
本目录即 `github/`，是需要上传到 GitHub 并交给 Vercel 部署的项目根目录。

## 主要改动

- 新增 `api/index.py` 作为 Vercel Python Serverless 函数入口。
- 新增 `vercel.json`，把请求全部交给 `api/index.py`。
- Vercel 函数运行时根目录只读，因此数据库和上传目录在 Vercel 上改用 `/tmp`：
  - `app/database.py` 在 Vercel 上使用 `/tmp/data/observations.db`，首次冷启动时从仓库内置的 `data/observations.db` 复制一份。
  - `app/main.py` 在 Vercel 上使用 `/tmp/uploads` 保存上传文件。
- 在导入入口时直接初始化数据库，避免 Serverless 包装没有触发 FastAPI startup 事件。

## 部署方法

1. 把这个文件夹推到一个 Git 仓库（或直接用 Vercel CLI 从该目录部署）。
2. 在 Vercel 导入仓库，Framework Preset 选 `Other` 即可，`vercel.json` 会自动指定 Python 构建。
3. 部署后访问部署域名。

## 注意事项

- Vercel 的 `/tmp` 是临时的，冷启动后会重新从仓库内的 `data/observations.db` 初始化；上传的新数据不会跨冷启动持久保存。
- 如果需要长期保存上传数据和数据库修改，建议后续接 Vercel Postgres 或 Vercel Blob，代码里已预留 `DATA_DIR` 和 `UPLOAD_DIR` 环境变量可覆盖默认路径。
