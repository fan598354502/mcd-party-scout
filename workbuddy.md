# WorkBuddy 开发上下文

本项目使用腾讯 WorkBuddy 开发，用于申请 WorkBuddy 专项积分奖励。

## 开发过程

1. **读规则**：抓取活动官方仓库 `M-China/mcd-developer-innovation-challenge`，读完 `README.md`、`activityGuidelines.md`、`CONTEST_DECLARATION.md`，以及 MCP 接入指南 `M-China/mcd-mcp-server`。
2. **读榜单**：抓取实时 `RANKING.md`（100 个项目），逐条分析赛道分布，定位空白方向。
3. **配 MCP**：拿到麦当劳 MCP Token 后，在 WorkBuddy 中配置 `mcd-mcp` 连接器（Streamable HTTP，`https://mcp.mcd.cn`）。
4. **实测接口**：不依赖官方文档猜测，直接用 curl 逐个试。关键发现是 `spuId` 的获取方式官方未说明，实测通过 `mall-points-products` 传入类目规则 `1>6>20,1>6>21,1>6>25` 拿到派对主题与 `spuId`。
5. **跑通全链路**：五步查询全部实测成功——26 个在售主题、全国城市列表（含深圳 440300）、深圳 64 家可办门店（自带距离升序）、可约日期、场次余位。
6. **写代码**：基于实测结果编写 `party_scout.py`，纯标准库实现 MCP 通信与参数解析。
7. **本地验证**：在 WorkBuddy 中实际运行脚本的 4 个子命令，输出均正确。

## 关键发现

- 26 个派对主题的 `point` 字段全部为 0，价格 ¥45–198/人——**麦当劳派对不能用积分兑换**。市面上的「积分换派对」说法不成立，这是本项目选题的核心依据。
- `query-party-store` 返回的门店自带距离升序，对家长决策价值高。
- 官方 README 未说明 `spuId` 来源，只能通过 `mall-points-products` 的类目规则反查，这是整个项目能否跑通的关键。

## 工具使用

- 网页抓取：读取活动规则、榜单、MCP 接入指南
- MCP 调用：配置并调用麦当劳 MCP Server 完成全部实测
- 代码执行：编写并运行 `party_scout.py`，验证 4 个子命令
- 文件写入：生成 SKILL.md、README.md、MCP_INTEGRATION.md 等参赛文件
