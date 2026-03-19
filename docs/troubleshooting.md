# 排障手册

这一页只做一件事：

> 当这套方案跑不通的时候，应该先查什么。

---

## 1. 飞书能收到消息，但机器人不稳定回复

### 常见表现
- 飞书能收到消息
- 但回复很慢，或者经常不回
- 日志里出现：
  - `bot/v3/info` 超时
  - `tenant_access_token` 超时
  - `final reply failed`

### 最常见原因
你把代理挂到了 **OpenClaw 主进程**。

### 正确做法
- OpenClaw 主进程不要挂 `HTTP_PROXY` / `HTTPS_PROXY`
- 飞书链路走直连
- 代理只给 Search Bridge 用

### 核心原则
> 飞书直连，搜索单独代理

---

## 2. Search Bridge 服务起不来

### 常见表现
- `systemctl --user status openclaw-search-bridge.service` 不是 running
- `/health` 连不上

### 先检查
```bash
systemctl --user status openclaw-search-bridge.service --no-pager
curl http://127.0.0.1:8787/health
```

### 正常结果
- service 是 `active (running)`
- `/health` 返回 `ok: true`

如果这两条都不过，就先不要测飞书。

---

## 3. 报错：`Address already in use`

### 常见原因
你同时启动了两份 Search Bridge：

- 一份是手动跑的 `python3 search_bridge.py`
- 一份是 `systemd --user` 在跑

两边都抢 `127.0.0.1:8787`，就会报端口占用。

### 正确做法
二选一：

- 要么手动跑
- 要么 systemd 常驻

不要两份一起跑。

### 建议
正式使用时，保留 `systemd --user` 常驻版。

---

## 4. `/health` 正常，但飞书里搜索还是不工作

### 这说明什么
说明 Search Bridge 服务本身活着，但 **OpenClaw 不一定真的调用到了它**。

### 怎么确认
看 Search Bridge 日志：

```bash
journalctl --user -u openclaw-search-bridge.service -f
```

然后去飞书里发搜索请求。

### 正确判断标准
如果日志里出现：

```text
POST /search HTTP/1.1" 200
```

说明搜索请求真的走到了 Search Bridge。

如果飞书有结果，但这里没有新请求，说明很可能还是别的工具在工作，不是 Search Bridge。

---

## 5. `/search` 返回 `not_found`

### 常见原因
你用错了请求方法。

### 错误写法
```bash
curl http://127.0.0.1:8787/search
```

这通常会变成 `GET /search`。

### 正确写法
`/search` 应该用 **POST**：

```bash
curl -s http://127.0.0.1:8787/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"OpenClaw Feishu 文档","count":3}'
```

---

## 6. `/fetch` 返回不了结果

### 先检查
先本地直接测：

```bash
curl -s http://127.0.0.1:8787/fetch \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://docs.openclaw.ai/channels/feishu.md"}'
```

### 正确判断标准
如果返回：

```json
{"ok": true, ...}
```

说明 fetch 后端正常。

然后再看 Search Bridge 日志里是否出现：

```text
POST /fetch HTTP/1.1" 200
```

---

## 7. Search Bridge 搜索时报“解码错误”

### 常见原因
之前实际遇到过这个问题：

- 请求头里要求了 gzip
- 返回内容被压缩
- 代码里又直接按 UTF-8 解码
- 最后报“解码错误”

### 解决思路
先不要强行要求 gzip 压缩。  
优先保证 `/search` 能稳定返回 JSON。

### 结论
这个问题不是 Brave Key 本身的问题，而是返回内容的处理方式有问题。

---

## 8. Brave Search API Key 看起来配了，但还是不通

### 先查这几件事
1. `BRAVE_API_KEY` 是否真的写进了环境变量
2. Search Bridge service 是否加载到了这个变量
3. `/health` 返回里 `has_brave_key` 是否为 `true`

### 怎么看
```bash
curl http://127.0.0.1:8787/health
```

如果看到：

```json
"has_brave_key": true
```

说明 Search Bridge 已经拿到 Key 了。

---

## 9. WSL 里访问不到代理

### 最常见原因
Windows 端的 v2rayN 没有开启：

> **允许来自局域网的连接**

### 表现
- 浏览器可能正常
- v2rayN 看起来也正常
- 但 WSL 里的 Search Bridge 连接不上代理

### 正确做法
在 v2rayN 里开启：

- `允许来自局域网的连接`

然后再确认你的代理地址是不是：

```text
http://172.27.208.1:10808
```

---

## 10. 为什么这里不是 `127.0.0.1:10808`

因为 Search Bridge 跑在 WSL 里。  
在 WSL 里写 `127.0.0.1`，访问的是 WSL 自己，不是 Windows 上的 v2rayN。

所以这里应该写：

- WSL 看到的 Windows 宿主机地址
- 再加上 v2rayN 的 HTTP 代理端口

---

## 11. 这套方案最重要的验收顺序

不要一上来就在飞书里瞎试。

正确顺序应该是：

### 第一步：先看服务活没活
```bash
systemctl --user status openclaw-search-bridge.service --no-pager
curl http://127.0.0.1:8787/health
```

### 第二步：本地测 `/search`
```bash
curl -s http://127.0.0.1:8787/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"OpenClaw Feishu 文档","count":3}'
```

### 第三步：本地测 `/fetch`
```bash
curl -s http://127.0.0.1:8787/fetch \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://docs.openclaw.ai/channels/feishu.md"}'
```

### 第四步：最后才去飞书里测
同时盯着日志：

```bash
journalctl --user -u openclaw-search-bridge.service -f
```

---

## 12. 一句话总结

如果你只记一条，就记这条：

> **先确认 Search Bridge 本地可用，再确认 OpenClaw 有没有真的调用到它。**


---

## 13. 看起来像“飞书又断了”，先别急着判死刑

### 常见误判
你会感觉像这样：
- 飞书消息没及时回
- 页面像卡住了
- 某次任务像挂住了
- 直觉上会以为“Gateway 死了”

### 先查这两个硬指标
```bash
openclaw gateway status
```

如果结果里这两项还在：
- `Runtime: running`
- `RPC probe: ok`

那通常说明：

> **主 Gateway 还活着，问题更可能出在任务链路、插件链路或搜索链路，不是主服务真的挂了。**

### 这一条为什么重要
这次排障里，一个很大的误区就是：
- 页面卡了，就以为服务挂了
- 飞书没秒回，就以为 Gateway 死了

但实际情况往往是：
- 某次任务卡住
- 插件链路有 warning
- 搜索桥没被真正调用
- 浏览器自动化和搜索 API 混在一起判断了

所以这里的顺序应该固定成：

1. 先看 `openclaw gateway status`
2. 再看飞书日志有没有 `bot open_id resolved` / `ws client ready`
3. 再看 Search Bridge 日志里有没有 `POST /search 200` 或 `POST /fetch 200`
4. 最后再判断是飞书链路、搜索链路，还是某次具体任务卡住

### 一句话版排法
> **先确认 Gateway 没死，再分层排飞书、代理、搜索桥，不要一上来就喊“又断了”。**

---

## 14. 把 Brave Search API 和 Brave 浏览器分开看

### 常见误区
前面这次排障里，有一段时间其实把两件事混了：
- Brave Search API
- Brave 浏览器自动化

但它们不是一回事。

### 正确理解
- **Brave Search API**：给 OpenClaw 提供联网搜索能力
- **Brave 浏览器**：给 OpenClaw 提供网页自动化能力

如果你当前目标只是：
- 搜索网页
- 抓正文
- 把结果回到飞书

那你优先排的是：
- Search Bridge
- Brave Search API
- 代理

而不是先去折腾 `browser start` 那条链。

### 一句话版
> **你要的是搜索能力，不一定要先把浏览器自动化也一起搞定。**

---

## 15. `plugin id mismatch` 不一定会直接搞挂，但最好及时收敛

### 典型 warning
```text
plugin id mismatch
(manifest uses "search-bridge", entry hints "openclaw-search-bridge-plugin")
```

### 根因
不是配置内容一定错了，而是：
- 插件 manifest 里 id 叫 `search-bridge`
- 插件目录名还叫 `openclaw-search-bridge-plugin`

OpenClaw 会结合路径和 manifest 去判断插件身份，所以这里容易冒 warning。

### 建议做法
把插件目录名也改成：

```text
search-bridge
```

让下面这三样尽量一致：
- manifest id
- 插件目录名
- 配置里引用的插件名

### 这一条为什么要收进去
它未必是“飞书断联”的第一根因，但会严重干扰排障判断。
如果 warning 一直飘着，你很容易分不清：
- 是链路真挂了
- 还是插件装载本身就有歧义
