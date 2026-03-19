# openclaw-feishu-search-bridge

这是一个在 **中国大陆 + Windows + WSL2/Ubuntu** 环境下，给 OpenClaw 增加 **Brave Search 搜索能力** 的实战方案。

这个项目不讲完整 OpenClaw 安装，也不讲飞书云文档。  
它只解决一件事：

> **在不搞坏飞书链路的前提下，把 Brave Search API 稳定打通。**

---

## 这个项目是做什么的

这个项目把 OpenClaw 的“搜索能力”从主进程里拆出来，做成一个单独的 Search Bridge 服务。

最终效果是：

- 飞书消息继续稳定收发
- OpenClaw 可以正常调用 Brave Search
- 网页正文可以正常抓取
- 搜索链路和飞书链路互不干扰

核心思路就一句话：

> **飞书直连，搜索单独代理。**

---

## 这个项目解决什么问题

在中国大陆环境下，直接给 OpenClaw 主进程挂代理，通常会出现这些问题：

- 飞书能收消息，但回复不稳定
- `bot/v3/info` 超时
- `tenant_access_token` 超时
- `final reply failed`
- 搜索链路和飞书链路互相污染

这个项目解决的，就是这个冲突：

### 解决前
- OpenClaw 主进程既要连飞书，又要走代理搜索
- 最后两边一起抽风

### 解决后
- OpenClaw 主进程只负责飞书和 Agent 本体，**不挂全局代理**
- Search Bridge 单独挂代理，专门负责 Brave Search 和网页抓取

---

## 前置条件

在开始之前，你至少需要具备这些条件：

### 1. 基础环境
- Windows
- WSL2
- Ubuntu

### 2. OpenClaw 已经能在 WSL 里跑起来
这里不要求你已经把所有功能都配好，但至少要满足：
- OpenClaw Gateway 能正常运行
- 飞书机器人已经接入
- 飞书 1 对 1 聊天能正常收发消息

### 3. 代理软件
- Windows 端使用 **v2rayN**
- **必须开启「允许来自局域网的连接」**

这一条很关键。  
不开的话，WSL 访问不到 Windows 侧的代理端口。

### 4. Brave Search API Key
你需要先申请一个 Brave Search API Key。

---

## 这个方案的基本结构

下面只讲这个项目的两部分。

### A. OpenClaw 主进程
职责：
- 飞书收消息
- 飞书回消息
- 模型推理
- 调用 Search Bridge 工具

特点：
- **不挂全局代理**
- 保持飞书链路稳定

### B. Search Bridge
职责：
- 调 Brave Search API
- 抓取网页正文

特点：
- **单独挂代理**
- 监听本地 `127.0.0.1:8787`

---

## 为什么代理地址是 `http://172.27.208.1:10808`

这一点必须讲清楚，不然很多人会抄错。

在这个项目里，Search Bridge 用的代理地址是：

```text
http://172.27.208.1:10808
```

它的含义是：

- `172.27.208.1`：WSL 里访问 Windows 宿主机的地址
- `10808`：v2rayN 开启的 HTTP 代理端口

也就是说：

> Search Bridge 在 WSL 里，通过这个地址，去访问 Windows 侧的 v2rayN 代理。

### 注意
这个地址不是所有机器都固定一样。

你需要自己确认两件事：

1. v2rayN 的 HTTP 代理端口是不是 `10808`
2. 你当前 WSL 看到的 Windows 宿主机地址是不是 `172.27.208.1`

---

## 解决步骤

下面只写这套方案的核心步骤。

### 第一步：保证 OpenClaw 主进程不挂全局代理

#### 这一步要做什么
检查 `openclaw.json`，确保 OpenClaw 主进程里**没有**这两个配置：

```json
"HTTP_PROXY": "...",
"HTTPS_PROXY": "..."
```

#### 这一步的思路
飞书链路对代理非常敏感。  
只要你把全局代理挂到 OpenClaw 主进程上，飞书开放平台接口就容易超时。

所以这里的原则很明确：

> **主进程不代理，飞书走直连。**

---

### 第二步：保留飞书插件，增加 Search Bridge 插件

#### 这一步要做什么
在 OpenClaw 配置里：

- 保持 `feishu` 插件启用
- 加载 `search-bridge` 插件
- 让 Agent 能调用 Search Bridge 提供的工具

#### 这一步的思路
OpenClaw 主进程本身不直接联网搜索，  
而是通过插件去调本地的 Search Bridge 服务。

也就是说：

> OpenClaw 不直接连 Brave，OpenClaw 只连本机的 Search Bridge。

---

### 第三步：单独启动 Search Bridge 服务

#### 这一步要做什么
把 `search_bridge.py` 做成一个独立常驻服务，监听：

```text
127.0.0.1:8787
```

建议用 `systemd --user` 常驻。

#### 这一步的思路
Search Bridge 是一个本地中间层，它做两件事：

1. 接收 OpenClaw 发来的搜索请求
2. 带着代理去请求 Brave Search 或网页

这样做的好处是：

- 飞书链路不受影响
- 搜索链路独立可控
- 出问题更容易排查

---

### 第四步：只给 Search Bridge 挂代理

#### 这一步要做什么
在 Search Bridge 的 service 配置里单独写：

```ini
Environment=HTTP_PROXY=http://172.27.208.1:10808
Environment=HTTPS_PROXY=http://172.27.208.1:10808
Environment=NO_PROXY=127.0.0.1,localhost,::1
```

#### 这一步的思路
代理不是不能用，而是不能乱挂。

这个方案里：

- 飞书：直连
- 搜索：代理

两条链分开以后，整个系统才稳定。

---

### 第五步：先做本地验证，再做飞书验证

#### 这一步要做什么
先验证 Search Bridge 本地服务：

##### 健康检查
```bash
curl http://127.0.0.1:8787/health
```

##### 搜索
```bash
curl -s http://127.0.0.1:8787/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"OpenClaw Feishu 文档","count":3}'
```

##### 抓取网页
```bash
curl -s http://127.0.0.1:8787/fetch \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://docs.openclaw.ai/channels/feishu.md"}'
```

然后再去飞书里验证搜索。

#### 这一步的思路
不要一上来就用飞书排障。  
先把本地 `/health`、`/search`、`/fetch` 跑通，说明 Bridge 本身没问题。  
然后再看 OpenClaw 有没有真的调用到它。

---

### 第六步：通过日志确认请求真的走了 Bridge

#### 这一步要做什么
观察 Search Bridge 日志：

```bash
journalctl --user -u openclaw-search-bridge.service -f
```

如果你在飞书里发起搜索后，日志里出现：

```text
POST /search HTTP/1.1" 200
```

或者：

```text
POST /fetch HTTP/1.1" 200
```

就说明请求已经真的走到 Bridge 了。

#### 这一步的思路
“飞书里搜出来了结果”不代表一定走了你的 Bridge。  
因为有时候内置搜索也可能返回结果。

所以真正的验收标准不是“有结果”，而是：

> **Bridge 日志里出现对应请求，并且返回 200。**

---

## 当前已经验证通过的内容

这套方案当前已经确认通过的部分包括：

- OpenClaw Gateway 正常运行
- 飞书链路稳定
- Search Bridge 服务正常常驻
- `/health` 正常
- `/search` 正常
- `/fetch` 正常
- 飞书发起搜索请求时，Bridge 日志能看到 `POST /search 200`
- 飞书发起抓取请求时，Bridge 日志能看到 `POST /fetch 200`

也就是说，这个方案不是“理论可行”，而是已经实测打通。

---

## 常见问题

### 1. 飞书能收消息，但不能稳定回复
高概率是你把代理挂到了 OpenClaw 主进程。

### 2. `Address already in use`
说明 8787 端口已经被另一份 Search Bridge 进程占用了。

### 3. `/search` 返回 `not_found`
通常是你用错了方法。  
`/search` 和 `/fetch` 都应该用 **POST**，不是 GET。

### 4. Search Bridge 能启动，但搜索报解码错误
这是之前遇到过的 gzip 解码问题。  
解决方式是不要强行请求 gzip 压缩，先保证稳定。

---

## 这个项目当前的边界

这个仓库当前只解决：

> **中国大陆 + Windows + WSL2 下 Brave Search API 的稳定桥接问题**

它暂时不负责：

- OpenClaw 完整安装
- 飞书云文档桥接
- 文档改写自动化

这些会在后续单独整理。

---

## 一句话总结

这个项目的核心经验不是“怎么调 API”，而是：

> **在中国大陆环境下，把 OpenClaw 的飞书链路和搜索链路彻底拆开。**

最终结论就是这句：

# 飞书直连，搜索单独代理
