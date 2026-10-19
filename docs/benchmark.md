# SearchBench 本地实时评测

## 启动

在仓库根目录运行：

```bash
python3 benchmark_server.py
```

然后在浏览器打开 <http://127.0.0.1:8765/>。服务只绑定本机回环地址；默认端口是 `8765`，可用 `--port` 修改。

页面每轮临时接收所选供应商的密钥，开始执行时立即清空输入框，本轮执行所需密钥只在闭包内存中使用。服务端仅在当前请求处理期间使用单个密钥，随后释放引用。不会读取环境变量、keyring 或配置文件，也不会主动写入磁盘、浏览器存储、URL、导出文件或请求日志。页面刷新、取消和完成后清除密钥输入与引用；这不能承诺浏览器、操作系统或物理内存立即归零。

## 支持的供应商

- DeepSeek：[`/v1/tools/search`](https://api-docs.deepseek.com/zh-cn/guides/search)
- Metaso：[`/api/v1/search`](https://metaso.cn/search-api)
- Bocha：[`/v1/web-search`](https://github.com/bocha-ai/dsh-web-search-bocha)
- Tavily：[`/search`](https://docs.tavily.com/documentation/api-reference/endpoint/search)
- Exa：[`/search`](https://exa.ai/docs/reference/search)

秘塔的请求参数已根据官方公开 playground 核对；响应字段采用 [RikkaHub 的社区适配器](https://github.com/rikkahub/rikkahub/blob/34d755e5/search/src/main/java/me/rerere/search/MetasoSearchService.kt) 中的 `webpages` 列表及 `title/link/snippet/summary/date`，其公开官方资料未提供响应样例，仍需首次真实响应核验。若返回结构不匹配，服务会明确报响应格式异常，不会将它当成零条结果或成功测评。

服务固定官方 HTTPS 地址、禁用重定向和代理环境变量、验证 TLS 证书、请求超时 30 秒。请求体最多 64 KiB，上游响应最多 8 MiB。五个适配器使用固定可重现参数，页面不能提交自定义 URL 或模式。每次响应保留 `provider_mode` 和实际请求 `params`；标准化结果截取前 `top_k` 条，原始响应仍保留完整列表。

DeepSeek、Tavily 和 Exa 的 `content_kind` 为 `body`；Bocha 和秘塔为 `summary`。摘要和正文不能当作同一种内容覆盖率，页面使用“可用文本率”并提供类型区分。

## 结果与边界

失败、业务错误、未知响应结构和真正的空结果分别显示；失败不会伪装成“没有结果”。结果按上游顺序保留且不去重，网址只接受 HTTP(S) 且拒绝 userinfo。`http_status` 记录上游状态，未获得响应时为 `null`，不应将桥接接口的 HTTP 200 当成上游成功。响应中会递归清理提交的密钥、Bearer 形式、常见 JSON 认证字段及其常见编码，也会移除认证、token、secret、cookie 等敏感字段；有限编码清理不能识别任意刻意变换。

页面结果与人工标注在主动导出前保留在浏览器内存中，导出前请自行检查是否含有不应分享的网页内容。当前版本不会在缺少人工判断时生成质量分数：抗污染判断、证据覆盖和相关率需要人工审核。当前自动化验证使用合成测试密钥和模拟上游传输，没有消费真实账号额度；真实 API 的端到端验证仍需用户一次性输入密钥。内存引用会释放，但无法承诺物理 RAM 立即归零。

HTTP 接口使用运行时一次性 CSRF token：先读取 `GET /api/health`，再以同源 `Origin` 和 `X-Benchmark-Token` 调用 `POST /api/search`。跨源、`null` Origin、未知 Host、重定向和代理请求均被拒绝。
