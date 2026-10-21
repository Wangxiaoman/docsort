# docsort — 本地文档识别分类路由工具

单机版文档分类服务：PDF/图片 → 图像预处理（去噪/纠偏/去阴影/增强）→ 本地 OCR → 规则计分分类（发票/合同/身份证/名片/未知）→ 按配置路由（文件夹/邮件/ERP·OA webhook）。纯本地运行，命令行直接调用。

## 安装

```bash
cd docsort
./install.sh            # 国内环境推荐: ./install.sh --mirror
```

脚本会创建 `.venv` 虚拟环境并安装依赖。默认安装 PaddleOCR（约 500MB）；想更轻量可编辑 `requirements.txt` 换 RapidOCR（<100MB，onnxruntime 推理），并把配置里 `ocr.backend` 改为 `rapidocr`。

## 配置

```bash
cp rules.example.yaml rules.yaml   # 然后按需修改
```

关键配置项：

| 配置 | 说明 |
|---|---|
| `ocr.backend` | `paddle`（默认）/ `rapidocr` / `text`（仅读 PDF 文本层，用于电子版或测试） |
| `preprocess.enabled` | 预处理总开关：`false` 则跳过全部预处理，图像直接 OCR |
| `preprocess.max_side` | 长边降采样阈值（性能保护，默认 2000） |
| `preprocess.deshadow/denoise/deskew/clahe` | 各步骤独立开关 |
| `classification` | `early_stop` 提前终止、`max_pages` 最多识别前几页（默认 3）、`min_margin` 安全边际 |
| `templates.<类型>.rules` | 正则规则 + 权重，跨页累计计分 |
| `templates.<类型>.threshold` | 定类阈值 |
| `route.folder/email/webhook` | 三种路由可同时配置；文件名模板支持 `{yyyy} {MM} {dd} {filename} {type} {confidence}` |
| `routing.output_dir` | 分类输出根目录（模板中用 `{output_dir}` 引用），默认 `./sorted` |
| `routing.mail` | SMTP 公共配置；密码建议走环境变量 `DOCSORT_SMTP_PASS` |

## 使用

```bash
# 单文件 / 批量
./docsort.sh run ./scan001.pdf --config rules.yaml
./docsort.sh run ./scans/ --config rules.yaml

# 常驻监控（新文件自动处理，文件写入稳定后触发）
./docsort.sh watch ./inbox --config rules.yaml

# 预处理控制（命令行优先于配置文件）
./docsort.sh run ./scans/ --no-preprocess              # 全部预处理跳过，图像直接 OCR（最快）
./docsort.sh run ./scans/ --no-denoise --no-deshadow   # 只关个别步骤

# 指定输出根目录（覆盖配置的 routing.output_dir，各类型子结构不变）
./docsort.sh run ./scans/ --output-dir /data/output
```

## 工作机制

1. PDF 逐页处理：单页有文本层（≥30 字符）直接用文本，否则按 300 DPI 渲染成图做 OCR；
2. 预处理顺序：去阴影 → 去噪 → 纠偏 → CLAHE 增强（每步可关）；
3. 分类：正则规则跨页累计计分，第一名达到阈值且领先第二名 `min_margin` 以上即**提前终止**（长合同只需扫前 1~2 页）；
4. 路由失败或识别异常的文件移入 `routing.failed_folder`，不中断批处理；
5. 每次识别在 `audit/docsort.jsonl` 追加一条记录（得分、命中规则、页数、路由结果），可回溯可调参。

## 信创环境部署（麒麟 / 统信 UOS）

先在信创机上确认 CPU 架构：`uname -m`

| CPU | 架构 | 路线 |
|---|---|---|
| 飞腾 / 鲲鹏 | aarch64 | ✅ 离线包（见下）或联网直接装 |
| 海光 / 兆芯 | x86_64 | ✅ 同上，把架构参数换 x86_64 |
| 龙芯 | loongarch64 | ⚠️ PyPI 无官方 wheel，需用龙芯源 pypi.loongnix.cn 源码编译，或走容器方案 |
| 申威 | sw_64 | ❌ 生态缺失，不建议 |

**方式一：离线安装包（内网推荐）**——在任意联网机器上制作：

```bash
sh make_offline_bundle.sh aarch64 39       # 飞腾/鲲鹏 + Python 3.9
sh make_offline_bundle.sh x86_64 311       # 海光/兆芯 + Python 3.11
# 生成 docsort_offline_<架构>_<版本>.tar.gz（约 145MB，含源码+全部 wheel）
```

拷贝到目标机后：

```bash
tar xzf docsort_offline_aarch64_39.tar.gz && cd docsort
sh install.sh --offline pkgs               # 纯离线安装，不需要任何外网访问
.venv/bin/python tests/ocr_probe.py        # 验证 OCR
./docsort.sh run /data/case --config rules.yaml --output-dir /data/output
```

**方式二：容器交付**（目标机有 docker 时最省事）：

```bash
docker build -t docsort:1.0 .              # 在目标架构机器上构建
docker run --rm -v /data/case:/data -v /data/output:/out \
  docsort:1.0 run /data --config /app/rules.yaml --output-dir /out
```

信创环境注意事项：

- **信创 PC（个人电脑）**：2025 年主流整机为华为擎云（麒麟 9006C，ARM64）、长城/紫光（飞腾 D2000/D3000，ARM64）、联想开天/浪潮（飞腾、龙芯 3A6000、兆芯）、软通/中科可控（海光，x86_64）；系统为银河麒麟桌面版 V10 SP1、统信 UOS V20、方德 V5。ARM64/x86_64 机型均走上述离线包路线；
- **PC 自带 Python 往往偏旧（3.7/3.8）**：先离线装一个 Miniconda（`Miniconda3-latest-Linux-aarch64.sh`，单文件安装器自带 3.9+ Python），然后用 `PYTHON=/opt/miniconda3/bin/python3 sh install.sh --offline pkgs` 指定它创建环境；
- 性能预期：飞腾 D2000 级 CPU 单页 OCR 约 3~8 秒，日常批处理可用；建议 `preprocess.denoise: false` 提速；
- 麒麟 V10 / 统信 UOS 自带 Python 3.7~3.9；目标机 Python 必须与离线包第二个参数一致（`python3 -V` 确认），缺失组件用 `apt install python3-venv`（UOS/麒麟桌面版）或 `yum install python3`（麒麟 V10 服务版）；
- 所有依赖均有 manylinux2014 ARM64/x86_64 官方 wheel，不需要系统装 libGL/poppler；rapidocr 模型内置，装完完全离线；
- 归档/交付建议保留 `docsort_offline_*.tar.gz` 作为版本基线，升级时重新制作。

## Windows 部署

把整个 `docsort/` 目录拷到 Windows 机器（**不要拷 `.venv`**，那是 macOS 二进制），然后：

```bat
:: 前置：从 python.org 安装 Python 3.9~3.13，勾选 "Add python.exe to PATH"
install.bat              :: 国内网络: install.bat mirror
docsort.bat run case --config rules.yaml
docsort.bat watch C:\inbox --config rules.yaml
```

要点：

- `install.bat` / `docsort.bat` 自动处理 venv、UTF-8 编码（中文文件名/控制台输出）；
- 依赖全有 Windows 官方 wheel，代码零修改；rapidocr 模型内置，装完离线可用；
- 打单 exe（PyInstaller）必须在 Windows 上打包，macOS 无法交叉打包；
- 离线安装同 Linux：联网机 `pip download -r requirements.txt -d pkgs/`，目标机 `pip install --no-index --find-links pkgs/ -r requirements.txt`。

## 新服务器部署（全新系统）

```bash
# ① 装基础组件（Debian/Ubuntu 最小系统）
apt update && apt install -y python3 python3-venv python3-pip
# CentOS/RHEL: yum install -y python3

# ② 拷贝项目目录后安装（需联网下载 pip 包，约 60MB）
sh install.sh            # 国内服务器: sh install.sh --mirror

# ③ 验证
.venv/bin/python tests/ocr_probe.py
./docsort.sh run case --config rules.yaml
```

兼容性要点：

- **Python 3.9~3.12** 全功能支持；3.13 只能用 rapidocr 后端（默认即是），paddle 后端需 3.9~3.12；
- 依赖全部为 pip 二进制 wheel（PyMuPDF/OpenCV-headless/onnxruntime），**不需要**系统装 libGL、poppler 等额外库，glibc ≥ 2.17 的发行版均可；
- rapidocr 的模型打包在 wheel 内，**装完即离线可用**；paddle 后端首次运行需联网下载模型到 `~/.paddleocr`；
- 极简容器/无 UTF-8 locale 的环境，`docsort.sh` 会自动设置 `LANG=C.UTF-8`，保证中文目录名正常；
- 资源需求：2GB 内存、1 核 CPU 即可运行（详见前文内存分析）；
- 离线服务器：在联网机器上 `pip download -r requirements.txt -d pkgs/`，拷过去后 `pip install --no-index --find-links pkgs/ -r requirements.txt`。

## 目录约定（运行后生成）

```
sorted/发票/合同/身份证/名片/待人工   # 分类输出
failed/                              # 处理失败文件
audit/docsort.jsonl                  # 审计日志
```
