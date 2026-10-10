# 麦麦派对侦察兵 · mcd-party-scout

> 带孩子办麦当劳派对，最难的不是选主题，是找出**附近哪家店能办、哪天还有空位**。
> 这个 Skill 把麦当劳官方的五步查询链路压成一条命令。

```
❌ 之前：翻宣传页 → 百度门店电话 → 逐个问「你们办派对吗、哪天有空」
✅ 现在：python party_scout.py slots --spu 5224 --store 1421131
```

## ⚠️ 先说一个被普遍误解的事

**麦当劳派对不能用积分兑换。**

实测麦当劳官方接口，26 个派对主题的 `point` 字段**全部为 0**，价格区间是 ¥45–198/人。

你在各种攻略里看到的「积分换派对」并不存在。本项目不推销这条不存在的路。

那真实的钱花在哪？答案是**位置和档期**：

- 不是每家麦当劳都承办派对——实测深圳 64 家可查询门店中，具备条件的只是少数
- 派对场次限量，**热门日期会满**

所以本项目解决的核心问题是：**快速定位能办、离你近、还有空位的场次。**

## 实际效果

在深圳实测「迪士尼疯狂动物城主题生日派对」（¥58/人）：

```
$ python party_scout.py stores --spu 5224 --city 深圳市 --radius 5

共 6 家门店可办。
[1] 麦当劳深圳大中华次元小镇餐厅  1.0km
    福田街道福华路1号深圳大中华国际交易广场GF-068
[2] 麦当劳深圳皇岗村餐厅  2.1km
[3] 麦当劳深圳新洲九街餐厅  2.4km
```

```
$ python party_scout.py slots --spu 5224 --store 1421131

共 2 天可约：
【2026-10-18】
    12:00-13:30  ¥58/人  5-12人  剩12位
    18:30-20:00  ¥58/人  5-12人  剩12位
【2026-10-19】
    12:00-13:30  ¥58/人  5-12人  剩12位
    18:30-20:00  ¥58/人  5-12人  剩12位
```

两条命令，从「我想办派对」到「我这周末去哪一家、订哪个时段」。

## 特点

- **零依赖** —— 纯 Python 标准库，不用 `pip install` 任何东西
- **不代下单** —— 只做只读查询，不会产生任何订单或支付
- **距离排序** —— 复用官方接口自带的距离升序，支持 `--radius` 过滤
- **余位预警** —— 剩余位 ≤3 的场次自动标记为「紧张」
- **实测可用** —— 项目中的所有输出均来自对官方接口的真实调用，非模拟数据

## 安装

### 1. 申请 MCP Token

访问 <https://open.mcd.cn/mcp> → 手机号验证码登录 → 右上角「控制台」→「激活」→ 复制 Token。

### 2. 配置 MCP 连接

把下面的配置加入你的 MCP 客户端配置，`<YOUR_TOKEN>` 换成刚才复制的 Token：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer <YOUR_TOKEN>"
      }
    }
  }
}
```

WorkBuddy 用户可在【连接器】→【自定义连接器】→【配置MCP】中粘贴同样内容并启用。

### 3. 设置环境变量

```bash
# macOS / Linux
export MCD_MCP_TOKEN=<YOUR_TOKEN>

# Windows PowerShell
$env:MCD_MCP_TOKEN = "<YOUR_TOKEN>"
```

## 使用

### 列出所有在售派对主题

```bash
python party_scout.py parties
```

输出包含主题名、`spuId`、类别、价格、可约时间区间和卖点。

### 查某主题能办哪些城市

```bash
python party_scout.py cities --spu 5224
```

**这一步不能跳过**——部分派对主题只在部分城市开设。

### 查某城市有哪些门店能办

```bash
python party_scout.py stores --spu 5224 --city 深圳市
```

只看 5 公里内：

```bash
python party_scout.py stores --spu 5224 --city 深圳市 --radius 5
```

### 查某门店的日期与场次余位

```bash
python party_scout.py slots --spu 5224 --store 1421131
```

需要 `store` 参数时，先用 `stores` 命令拿到门店编码。

## 在 AI 客户端中使用

把本 Skill 安装到你的客户端后，可以直接用自然语言提问：

- 「深圳有哪些麦当劳派对可以订？」
- 「帮我看看附近 5 公里内哪家门店能办生日派对」
- 「大中华次元小镇那家，最近哪几天还有位置？」

Skill 会自动按「列主题 → 定城市 → 找门店 → 查余位」的顺序带你走完。

## 完整推荐流程

```
用户：想在深圳办个生日派对
  │
  ① parties          →  26 个主题，按价格档位分组，让用户挑
  │
  ② cities           →  确认该主题在深圳可办（部分主题限城市）
  │
  ③ stores           →  按距离排序，筛出 3–5 公里内的候选门店
  │
  └─ slots           →  查余位，标出紧张场次
                         →  先定日期，再谈主题
```

## 项目结构

```
mcd-party-scout/
├── SKILL.md                      # Skill 定义与使用指引
├── party_scout.py                # 核心查询脚本（纯标准库）
├── mcp-config.example.json       # 脱敏 MCP 配置示例
├── MCP_INTEGRATION.md            # MCP 接入说明与真实调用记录
├── CONTEST_DECLARATION.md        # 参赛声明
└── README.md                     # 本文件
```

## 使用的 MCP Tool

`mall-points-products`、`query-party-city`、`query-party-store`、`query-party-store-date`、`query-party-store-session`

不使用 `party-order-create`（涉及真实支付）。

详见 [MCP_INTEGRATION.md](MCP_INTEGRATION.md)。

## 已知限制

- **本 Skill 不支持下单。** 场次余位是实时数据，可能随时变化，最终请以麦当劳官方渠道为准。
- `spuId` 需要通过 `mall-points-products` 的类目规则获得，请勿随意猜测。
- 部分主题限特定城市开通，查询门店前应先用 `cities` 确认。

## 免责声明

本项目为麦当劳程序员创意开发大赛参赛作品，由参赛者独立开发，非麦当劳官方产品。
项目输出仅供参考，餐品信息、价格及供应状态以麦当劳官方渠道的实时结果为准。

## License

MIT
