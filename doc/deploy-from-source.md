# 本地源码部署指南（无 Docker / WSL2 场景）

本文记录在**没有 Docker** 的环境下，从源码把 RetainPDF 后端 + 前端跑起来的完整步骤，以及两个在 **WSL2** 下特别容易踩、但文档里没有明说的坑和对应解法。

## 一、本地源码部署的架构形态

不用 Docker 时，等价于手动跑起 `app` 和 `web` 两个服务：

- **后端**：`backend/rust_api`（Rust API 网关 / 任务调度）+ `backend/scripts`（Python 流水线：OCR 标准化 / 翻译 / Typst 渲染）+ Typst 可执行文件 + 中文字体
- **前端**：`frontend/` 静态资源。注意它**没有打包器**，是浏览器直接以 ES module 形式引用 `node_modules/` 里的依赖（`pdfjs-dist` / `pdf-lib` 等）

## 二、前置依赖

| 依赖 | 版本建议 | 用途 |
| --- | --- | --- |
| Rust 工具链 | 1.70+（项目按 1.88 构建） | 编译 `rust_api` 二进制 |
| Typst | 0.14.x | PDF 重排渲染引擎（外部二进制） |
| Python | **3.11**（`pyproject.toml` 要求 `>=3.11,<3.12`） | 运行翻译/渲染流水线 |
| Node.js + npm | 20+ | 安装前端 `node_modules` 依赖 |

> 说明：后端流水线只用少量 Python 三方库（Pillow / PyMuPDF / pikepdf / requests / urllib3），已整理在 `docker/requirements-app.txt`。

## 三、部署步骤

### 1. 编译 Rust API

```bash
# 安装 rustup（首次）
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs -o /tmp/rustup-init.sh
sh /tmp/rustup-init.sh -y --profile minimal

cd backend/rust_api
cargo build --release --locked          # 产出 target/release/rust_api
```

### 2. 安装 Typst

```bash
# 下载静态二进制（Linux x86_64 示例，按平台选择 target）
curl -fsSL https://github.com/typst/typst/releases/download/v0.14.2/typst-x86_64-unknown-linux-musl.tar.xz \
  -o /tmp/typst.tar.xz
mkdir -p /tmp/typst && tar -xJf /tmp/typst.tar.xz -C /tmp/typst --strip-components=1
install -m 0755 /tmp/typst/typst ~/.local/bin/typst
```

### 3. 准备 Python 3.11 环境

```bash
# 二选一：conda 或 venv，关键是版本必须是 3.11
conda create -n retainpdf python=3.11 -y
# 或 python3.11 -m venv .venv

# 安装后端流水线依赖
pip install -r docker/requirements-app.txt
```

### 4. 安装前端依赖（容易被漏掉，见「问题 2」）

```bash
cd frontend
npm ci
```

### 5. 配置鉴权与运行参数

- `backend/rust_api/auth.local.json`：后端访问白名单（`X-API-Key`），参见 `auth.local.example.json`
- 前端运行时配置 `frontend/runtime-config.local.js`：`apiBase`、`xApiKey`、OCR / 模型默认值，参见 `frontend/runtime-config.local.example.js`
- 环境变量：`RUST_API_DATA_ROOT`、`RUST_API_SCRIPTS_DIR`、`PYTHON_BIN`、`TYPST_BIN`、`RETAIN_PDF_FONT_PATH` 等（后端启动时读取，并透传给 Python 子进程）

## 四、两个关键问题与解决方案

### 问题 1：WSL2 下浏览器「无法连接后端」（`127.0.0.1:41000` 不通）

**现象**：后端明明已启动、`curl http://127.0.0.1:41000/health` 在 WSL 内返回正常，但 Windows 浏览器里前端一直报「当前前端无法连接后端」。

**根因**：WSL2 的 localhost 转发并不可靠——可能出现**前端端口（如 40001）能转发、后端端口（41000）转发失效**的不对称情况。此时 Windows 侧 `127.0.0.1:41000` 实际上到不了 WSL 里的服务。

**验证方法**（在 Windows 侧执行）：

```powershell
curl.exe http://127.0.0.1:41000/health   # 失败
curl.exe http://<WSL-IP>:41000/health    # 成功，说明服务本身没问题
```

在 WSL 内用 `ip -4 addr show eth0` 可拿到 WSL 的 IP。

**解决方案**：让前端**直连 WSL 的 eth0 IP**，而不是依赖 localhost 转发。在 `frontend/runtime-config.local.js` 里显式写：

```js
window.__FRONT_RUNTIME_CONFIG__ = {
  ...(window.__FRONT_RUNTIME_CONFIG__ || {}),
  apiBase: "http://<WSL-IP>:41000",   // 关键：用 WSL IP 直连
  xApiKey: "<backend-key>",
  // ... 其余 OCR / 模型默认值
};
```

后端绑定 `0.0.0.0` + 宽松 CORS，跨 IP 访问无问题。前端会把下载链接等也基于 `apiBase` 重建，因此一次性解决接口调用与产物下载。

> 备选根治方案：Windows PowerShell 执行 `wsl --shutdown` 重启 WSL，有时能修复 localhost 转发；但不保证，直连 IP 最稳妥。

### 问题 2：前端报 `Failed to fetch dynamically imported module ... /node_modules/pdfjs-dist/build/pdf.mjs`

**现象**：打开页面后控制台报找不到 `node_modules/.../pdf.mjs` 等模块。

**根因**：前端以 ES module 直接引用 `node_modules/`（无打包器），而源码部署时容易漏掉安装依赖这一步。

**解决方案**：

```bash
cd frontend
npm ci
```

安装后 `frontend/node_modules/` 会被静态服务提供，`pdfjs-dist` / `pdf-lib` 等模块即可正常加载。

## 五、一键启动脚本

仓库根目录提供了 `run.sh` + `run.env.example`，把上面的坑都固化进脚本：

1. **自动检测 WSL IP**（`ip -4 addr show eth0`）并写入 `apiBase`，重启 WSL 后无需手动改 IP；
2. 从 `run.env` 读取配置，生成 `frontend/runtime-config.local.js` 与 `backend/rust_api/auth.local.json`；
3. **幂等启动**后端（41000/42000）与前端（40001），日志落到 `data/*.log`。

用法：

```bash
cp run.env.example run.env    # 填入自己的 key / token / Python 路径
./run.sh
```

`run.env` 含密钥，已被 `.gitignore` 忽略，请勿提交。

## 六、启动后访问

- 前端：`http://<WSL-IP>:40001`（或 `http://127.0.0.1:40001`）
- 完整 API：`http://<WSL-IP>:41000`（`/health` 为公开健康检查）
- 同步翻译接口：`http://<WSL-IP>:42000`（`/api/v1/translate/bundle`）

除 `/health` 外接口均需请求头 `X-API-Key: <backend-key>`。
