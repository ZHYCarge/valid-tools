# 司法取向 OpenTimestamps + TSA 存证系统

[![Docker Image Version (latest semver)](https://img.shields.io/docker/v/zhycarge/valid-tools?sort=semver)](https://hub.docker.com/repository/docker/zhycarge/valid-tools/)
[![Docker Image Size](https://img.shields.io/docker/image-size/zhycarge/valid-tools/latest)](https://hub.docker.com/repository/docker/zhycarge/valid-tools/)


## 项目概述

> 本项目为个人想法与GPT-5.2-Codex进行实现，其中绝大部分代码均由AI完成。

本项目提供基于 OpenTimestamps 与 RFC3161 TSA 的存证与验证服务，支持文件/文本存证、验证、管理、日志导出与删除，并具备 SQLite 迁移与 Docker 部署能力。
前端提供四个页面：上传、验证、管理与首页导航，并对返回的 JSON 进行可视化解析与状态高亮（成功/失败/警告）。

## 目录结构
```
app/
  api/                # API 路由
  services/           # 业务服务（OTS/TSA/存证）
  storage/            # SQLite 数据访问
  utils/              # 工具与日志
  migrations/         # SQLite 迁移脚本
  config.py           # 配置读取
  main.py             # 应用入口
  run_test.py         # 本地运行脚本
static/
  index.html          # 首页
  upload.html         # 存证上传
  verify.html         # 存证验证
  manage.html         # 存证管理
Dockerfile
requirements.txt
README.md
```

## 运行说明
### 本地运行
1. 安装依赖
```
pip install -r requirements.txt
```
2. 设置 TSA URL
```
set TSA_URL=https://freetsa.org/tsr
```
3. 启动服务
```
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

4. 浏览器访问
```
http://localhost:8000/static/index.html
```

或
```
http://localhost:8000/
```
### Docker 运行
1. 构建镜像
```
docker build -t zhycarge/valid-tools .
```
2. 运行容器
```
docker run -d \
  -p 8000:8000 \ 
  -e TSA_URL=https://freetsa.org/tsr \
  -v /root/valid-datas:/data \
  --name valid-tools \
  zhycarge/valid-tools

```

## 功能与流程
### 1) 存证上传
- 前端本地计算 SHA-256 作为存证 Hash。
- 支持 OTS / TSA 任选其一或同时启用。
- 支持“是否保存到数据库”的可选项：
  - 勾选：写入数据库并保存 .ots/.tsr 文件到后端。
  - 不勾选：仅生成凭证，不写库不落盘；刷新页面后凭证消失。
- 当不保存时，下载凭证文件名与上传文件名一致（文本提交则使用 Hash）。

### 2) 存证验证
- 前端本地计算 Hash 后提交验证。
- 若数据库有记录，可自动读取已保存的 .ots/.tsr。
- 若数据库无记录，则需上传对应凭证文件进行验证。
- OTS 验证会尝试向日历服务器升级待确认的证明，并在返回信息中反映升级结果。

### 3) 存证管理
- 列出所有存证记录（需基础认证）。
- 支持下载 OTS/TSA 文件、删除记录、管理日志。

### 4) 日志管理
- 提供日志列表、下载、查看与删除。

### 5) SQLite 迁移
- 启动时自动检查 schema 版本并执行迁移脚本。

## API 接口
- `POST /api/evidence/upload` 上传存证（表单字段：`hash_value`、`ots_option`、`tsa_option`、`save_option`、`source_name`）。
- `POST /api/evidence/verify` 验证存证（表单字段：`hash_value`、`ots_option`、`tsa_option`、可选文件：`ots_file`、`tsa_file`）。
- `GET /api/evidence/list` 记录列表（需基础认证）。
- `GET /api/evidence/{hash}` 记录详情（需基础认证）。
- `DELETE /api/evidence/{hash}` 删除记录（需基础认证，参数 `keep_files`）。
- `GET /api/files/{hash}/ots` 下载 OTS 文件（需记录存在且 OTS 成功）。
- `GET /api/files/{hash}/tsa` 下载 TSA 文件（需记录存在且 TSA 成功）。
- `GET /api/logs` 日志列表（需基础认证）。
- `GET /api/logs/{name}` 下载日志（需基础认证）。
- `GET /api/logs/{name}/view` 查看日志（需基础认证，参数 `limit`）。
- `DELETE /api/logs/{name}` 删除日志（需基础认证）。

## 认证说明
- 登录后可访问 `/static/manage.html` 管理页面。
- 受保护的 API：`/api/evidence/list`、`/api/evidence/{hash}`、`/api/logs` 及其子路径。
- 未登录时勾选“保存到数据库”将返回 403。

## 环境变量
| 变量名 | 说明 |
| --- | --- |
| TSA_URL | RFC3161 TSA 服务地址，默认 `https://freetsa.org/tsr` |
| OTS_CALENDAR_URLS | OTS 日历服务器列表（逗号分隔） 默认采用<details><summary>常见的五个日历服务器</summary><p>https://a.pool.opentimestamps.org</p><p>https://b.pool.opentimestamps.org</p><p>https://a.pool.eternitywall.com</p><p>https://ots.btc.catallaxy.com</p><p>https://alice.btc.calendar.opentimestamps.org/</p></details>
| BTC_BLOCK_HASH_API | 比特币区块高度查询接口，默认 `https://blockstream.info/api/block-height/{height}` |
| LTC_BLOCK_HASH_API | 莱特币区块高度查询接口，默认 `https://sochain.com/api/v2/get_block/LTC/{height}` |
| BTC_EXPLORER_BLOCK_URL | 比特币区块浏览器链接（按区块哈希），默认 `https://blockchair.com/bitcoin/block/{hash}` |
| LTC_EXPLORER_BLOCK_URL | 莱特币区块浏览器链接（按区块哈希），默认 `https://blockchair.com/litecoin/block/{hash}` |
| BTC_EXPLORER_HEIGHT_URL | 比特币区块浏览器链接（按区块高度，哈希缺失时使用），默认 `https://blockchair.com/bitcoin/block/{height}` |
| LTC_EXPLORER_HEIGHT_URL | 莱特币区块浏览器链接（按区块高度，哈希缺失时使用），默认 `https://blockchair.com/litecoin/block/{height}` |
| ICP_INFO | ICP 备案信息文本（可选，链接固定指向 `https://beian.miit.gov.cn`） |
| MPS_INFO | 公安备案信息文本（可选，用于链接显示文案） |
| MPS_CODE | 公安备案验证值（可选，用于链接指向 `https://beian.mps.gov.cn/#/query/webSearch?code=...`） |
| DATA_DIR | 数据目录根路径，默认 `/data` 或 `./data` |
| BASIC_AUTH_USER | 登录用户名，默认 `admin` |
| BASIC_AUTH_PASS | 登录密码，默认 `admin` |

## 访问页面
- `/static/index.html` 首页
- `/static/upload.html` 存证上传
- `/static/verify.html` 存证验证
- `/static/manage.html` 存证管理（需基础认证）

## Third-Party Licenses

This project uses third-party libraries licensed under MIT, BSD-3-Clause,
and LGPL-3.0. See THIRD_PARTY_NOTICES for details.


# 版本更新

### v1.0.0
实现基础功能

### v1.1.0
- 增加更加严格的访问管理，防止部分情况下访问`manage.html`会被直接访问
- 匹配官网的验证逻辑。会直接用该节点的信息拉去时间戳，并返回该节点，而不是重新merge导致合并冲突。
- 美化`verfiy.html`页面，显示更加直观简洁

### v1.2.0
- 删除掉之前的基础验证，改为正常的后台登录管理模式
- 严格权限管理：未登录不允许访问管理页面，同时未登录不允许将数据保存在数据库中
- 增加ICP备案和公安备案的悬挂信息

### v1.2.1
- 完善公安备案要求信息
