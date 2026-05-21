# 部署到 Vercel

## ⚠ 重要前置说明

- **本目录是为 Vercel serverless 重构过的版本**，跟根目录的 `tipsy/` 是两套独立代码。
- Vercel **Hobby 免费版函数最长 60 秒**，单张立绘 30~60 秒，会有约 5~10% 概率超时；要稳定运行建议升级到 **Pro（$20/月，5 分钟超时）**。
- 没有持久磁盘，所有图片走 **Vercel Blob**，所有元数据走 **Vercel KV**（Upstash Redis）。**这两个存储都需要在 Vercel Dashboard 手动开通。**

---

## 一、把代码推到 GitHub

在项目根目录（`角色创建demo/`）：

```bash
# 假设你已经有一个空的 GitHub 私有仓库 git@github.com:YOU/tipsy-deploy.git
cd vercel-deploy
git init
git add .
git commit -m "init: vercel deploy"
git branch -M main
git remote add origin git@github.com:YOU/tipsy-deploy.git
git push -u origin main
```

**只把 `vercel-deploy/` 这一层推上去**，仓库根就是 `api/`、`public/`、`vercel.json`。

---

## 二、在 Vercel 上 Import Project

1. 打开 https://vercel.com/new
2. 选择刚才那个 GitHub 仓库 → Import
3. **Root Directory** 选默认（仓库根），不要选别的
4. **Framework Preset**：`Other`
5. 暂时不点 Deploy，先去开通存储

---

## 三、开通 Vercel Blob 和 KV

### 3.1 Blob

1. 进入这个项目 → Storage → Create Database → 选 **Blob**
2. 给个名字（比如 `tipsy-blob`）→ Create
3. Connect to Project：勾选当前 project → Connect

完成后会自动注入 `BLOB_READ_WRITE_TOKEN` 到环境变量。

### 3.2 KV (Upstash Redis)

1. 同一页 → Create Database → 选 **Upstash KV**（或写 "Redis"）
2. 给个名字（比如 `tipsy-kv`）→ Create
3. Connect to Project：勾选当前 project → Connect

完成后会自动注入：
- `KV_REST_API_URL`
- `KV_REST_API_TOKEN`
- `KV_URL` 等

---

## 四、添加 ARK 模型环境变量

进入 Project → Settings → Environment Variables，添加：

| Name | Value |
|---|---|
| `ARK_API_KEY` | `f0a12798-9295-4768-b301-8b8e232523de` |
| `ARK_BASE_URL` | `https://ark.ap-southeast.bytepluses.com/api/v3` |
| `ARK_TEXT_MODEL` | `seed-sc-260215` |
| `ARK_IMAGE_MODEL` | `seedream-5-0-260128` |

环境（Environments）三个全选：Production / Preview / Development。

---

## 五、Deploy

回到 Project 主页 → Deployments → Redeploy（或 push 一次新 commit 触发）。

构建完成后会拿到一个 `xxx.vercel.app` 域名，分享给公司同事即可。

---

## 六、自定义域名（可选）

Settings → Domains → 加你公司的域名。如果你没有域名，直接用 vercel.app 子域也行。

---

## 七、限制和已知问题

| 现象 | 原因 | 处理 |
|---|---|---|
| 角色立绘偶尔失败：`fetch error` 或 504 | Hobby 60s 超时，seedream 偶尔需要 50~70s | 重试一次；或升 Pro |
| 同时点了 10 个生成按钮，部分失败 | 浏览器到同域名的并发数有限（通常 6） | 拆批次操作 |
| 服务端"重启清空"逻辑没了 | 因为没有"启动"概念 | 想重置：手动调 `POST /api/scrape`（会自动覆盖 KV 中的 characters）；或在 Vercel KV Dashboard 手动 flush |
| 浏览器 a.download 不下载 Excel | Blob 跨域，浏览器忽略 download 属性 | 已在前端代码用 `?download=1` query 强制下载，正常工作 |

---

## 八、常用排查

**A. 部署后页面打开是空白**
- 检查 vercel.json 的 rewrites
- 检查 public/index.html 是否上传

**B. 抓取报错 500**
- 查看 Vercel Functions Logs
- 大概率是 KV 没开通，环境变量缺少 KV_REST_API_URL

**C. 生图报错 "BLOB_READ_WRITE_TOKEN not set"**
- Blob 没开通或没 Connect 到 project，回 Storage 页确认

**D. 丰容报 model not found**
- 确认 `ARK_TEXT_MODEL` 是 `seed-sc-260215`
- 确认 ARK_API_KEY 和 base_url 正确

---

## 九、本地开发（可选）

如果想在本地用 Vercel CLI 跑这套：

```bash
npm i -g vercel
cd vercel-deploy
vercel link        # 关联到 vercel project
vercel env pull    # 把环境变量拉到本地 .env.local
vercel dev         # 启动本地 Vercel runtime
# 访问 http://localhost:3000
```
