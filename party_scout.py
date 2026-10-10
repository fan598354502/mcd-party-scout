#!/usr/bin/env python3
"""
mcd-party-scout —— 麦麦派对侦察兵

通过麦当劳官方 MCP Server 查询生日派对 / 主题派对 / 品鉴会的
「可办城市 → 可办门店 → 可约日期 → 具体场次」，并按距离与余位排序。

本脚本只做只读查询，绝不调用下单接口。

用法：
  python party_scout.py parties                    # 列出所有在售派对主题
  python party_scout.py cities   --spu 5224       # 查某主题可办城市
  python party_scout.py stores   --spu 5224 --city 深圳市   # 查可办门店（含距离）
  python party_scout.py slots    --spu 5224 --store 1421131 # 查近期可约日期+场次

环境变量：
  MCD_MCP_TOKEN   麦当劳 MCP Token（必填，从 open.mcd.cn/mcp 申请）
  MCD_MCP_URL     默认 https://mcp.mcd.cn
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "https://mcp.mcd.cn"

# 派对类目规则：生日派对 / 主题派对 / 品鉴会 / 麦麦体验营 / 读书会
PARTY_CATEGORIES = "1>6>20,1>6>21,1>6>25,1>6>22,1>6>34"

# 状态码含义（来自 mall-points-products 字段说明）
STATUS_MAP = {
    1: "仓库中",
    2: "在售",
    3: "已售罄",
    4: "已下架",
    5: "预热中",
}


# --------------------------------------------------------------------------
# MCP 通信
# --------------------------------------------------------------------------
class McdMcpError(RuntimeError):
    """麦当劳 MCP 返回了业务错误。"""


class McdClient:
    """麦当劳 MCP Server 的极简客户端（仅用标准库，无需安装依赖）。"""

    def __init__(self, token=None, url=None):
        self.token = token or os.environ.get("MCD_MCP_TOKEN")
        if not self.token:
            raise McdMcpError(
                "未找到 MCD_MCP_TOKEN。请先到 open.mcd.cn/mcp 申请 Token，\n"
                "然后设置环境变量：export MCD_MCP_TOKEN=你的Token"
            )
        self.url = url or os.environ.get("MCD_MCP_URL", DEFAULT_URL)
        self._id = 0

    def _rpc(self, payload):
        self._id += 1
        payload["id"] = self._id
        payload["jsonrpc"] = "2.0"
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 401:
                raise McdMcpError("Token 无效或已过期（401），请重新申请。") from e
            if e.code == 429:
                raise McdMcpError("触发限流（429），每分钟最多 600 次请求，请稍候。") from e
            raise McdMcpError(f"HTTP {e.code}: {body[:200]}") from e
        except urllib.error.URLError as e:
            raise McdMcpError(f"网络错误：{e}") from e
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise McdMcpError(f"返回内容不是合法 JSON：{raw[:200]}") from e

    @staticmethod
    def _unwrap(resp):
        """MCP 把业务 JSON 包在 markdown 说明里，这里抠出原始对象。"""
        text = resp["result"]["content"][0]["text"]
        m = re.search(r"##\s*Original\s*Response\s*\n+(.*)", text, re.S | re.I)
        body = (m.group(1) if m else text).replace("`", "").strip()
        depth, end = 0, 0
        for i, ch in enumerate(body):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end == 0:
            raise McdMcpError(f"无法解析返回内容：{text[:300]}")
        return json.loads(body[:end])

    def call(self, tool, **arguments):
        """调用一个 MCP 工具，返回业务 data 字段。"""
        resp = self._rpc({
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        })
        if "error" in resp:
            raise McdMcpError(f"{tool} 调用失败：{resp['error']}")
        obj = self._unwrap(resp)
        if not obj.get("success", False):
            raise McdMcpError(f"{tool} 返回错误：{obj.get('message') or obj}")
        return obj.get("data")


# --------------------------------------------------------------------------
# 业务封装
# --------------------------------------------------------------------------
def list_parties(client, categories=PARTY_CATEGORIES):
    """列出在售的派对主题，附带 spuId。"""
    rows = client.call("mall-points-products", catRuleIds=categories) or []
    out = []
    for it in rows:
        price = it.get("price", "")
        try:
            price_txt = f"¥{int(float(price))}/人"
        except (TypeError, ValueError):
            price_txt = price or "—"
        out.append({
            "spuId": it.get("spuId"),
            "name": it.get("spuName", ""),
            "category": it.get("catName", ""),
            "price": price_txt,
            "sell": it.get("selling", ""),
            "window": f"{it.get('upTime','')[:10]} ~ {it.get('downTime','')[:10]}",
            "status": STATUS_MAP.get(it.get("status"), "未知"),
            "image": it.get("spuImage", ""),
        })
    return out


def list_cities(client, spu_id):
    """查询某派对主题可办的城市列表。"""
    return client.call("query-party-city", spuId=spu_id) or []


def find_city(cities, name):
    """按名称在城市列表里找城市，支持去掉'市'后缀的模糊匹配。"""
    target = name.strip()
    for c in cities:
        if c.get("name") == target:
            return c
    short = target[:-1] if target.endswith("市") else target
    for c in cities:
        if c.get("name", "").startswith(short):
            return c
    return None


def list_stores(client, spu_id, city, max_distance_km=None):
    """查询某城市下可办该派对的门店，接口自带距离升序。"""
    args = {
        "code": str(city["code"]),
        "spuId": spu_id,
        "latitude": city.get("latitude"),
        "longitude": city.get("longitude"),
    }
    stores = client.call("query-party-store", **args) or []
    out = []
    for s in stores:
        dist = s.get("distance")
        if max_distance_km and dist and dist > max_distance_km * 1000:
            continue
        out.append({
            "code": s.get("code"),
            "name": s.get("name") or s.get("shortName", ""),
            "address": s.get("address", ""),
            "distanceText": s.get("distanceText", ""),
            "open": bool(s.get("onlineBusinessStatus")),
        })
    return out


def list_dates(client, spu_id, store_code):
    """查询某门店可预约的日期。"""
    return client.call(
        "query-party-store-date", spuId=spu_id, storeCode=store_code
    ) or []


def list_sessions(client, spu_id, store_code, date_str):
    """查询某门店某天的具体场次与余位。"""
    rows = client.call(
        "query-party-store-session",
        spuId=spu_id,
        storeCode=store_code,
        dateStr=date_str,
    ) or []
    out = []
    for s in rows:
        price = s.get("price")
        try:
            price = f"¥{int(price) / 100:.0f}/人"
        except (TypeError, ValueError):
            price = "—"
        out.append({
            "id": s.get("id"),
            "time": f"{s.get('timeStart')}-{s.get('timeEnd')}",
            "min": s.get("partyMin"),
            "max": s.get("partyMax"),
            "left": s.get("leftNum"),
            "price": price,
        })
    return out


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------
def show_parties(rows):
    if not rows:
        print("没有查到在售的派对主题。")
        return
    print(f"\n共 {len(rows)} 个在售派对主题：\n")
    for i, p in enumerate(rows, 1):
        if p["status"] != "在售":
            continue
        print(f"[{i}] {p['name']}  ({p['spuId']})")
        print(f"     类别：{p['category']}   价格：{p['price']}   状态：{p['status']}")
        print(f"     可约：{p['window']}")
        if p["sell"]:
            print(f"     卖点：{p['sell'][:80]}")
        print()


def show_cities(rows, limit=20):
    if not rows:
        print("该主题暂无可办城市。")
        return
    total = len(rows)
    print(f"\n{total} 个城市可办。{'（显示前 %d 个）' % limit if total > limit else ''}\n")
    for c in rows[:limit]:
        print(f"  {c.get('name'):<12} code={c.get('code')}")


def show_stores(rows, limit=15):
    if not rows:
        print("该城市暂无可办门店。")
        return
    total = len(rows)
    print(f"\n共 {total} 家门店可办。{'（显示最近 %d 家）' % limit if total > limit else ''}\n")
    for i, s in enumerate(rows[:limit], 1):
        flag = "" if s["open"] else "  [暂不可约]"
        print(f"[{i}] {s['name']}  {s['distanceText']}{flag}")
        print(f"    {s['address']}")
        print(f"    门店编码：{s['code']}")
        print()


def show_slots(dates_rows, sessions_by_date):
    if not dates_rows:
        print("该门店近期暂无可约日期。")
        return
    print(f"\n共 {len(dates_rows)} 天可约：\n")
    for d in dates_rows:
        date_str = d.get("date")
        sessions = sessions_by_date.get(date_str) or []
        print(f"【{date_str}】")
        if not sessions:
            print("    当日暂无可选场次")
        for s in sessions:
            left = s["left"]
            tight = "  ← 紧张" if isinstance(left, int) and left <= 3 else ""
            print(
                f"    {s['time']}  {s['price']}  "
                f"{s['min']}-{s['max']}人  剩{left}位{tight}"
            )
        print()


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def parse_args(argv):
    cmd = argv[0] if argv else "parties"
    opts = {}
    for i in range(1, len(argv)):
        if argv[i].startswith("--"):
            key = argv[i][2:]
            val = argv[i + 1] if i + 1 < len(argv) else ""
            opts[key] = val
            i += 1
    return cmd, opts


def main():
    cmd, opts = parse_args(sys.argv[1:])
    try:
        client = McdClient()
    except McdMcpError as e:
        print(f"配置错误：{e}", file=sys.stderr)
        return 1

    try:
        if cmd == "parties":
            show_parties(list_parties(client))

        elif cmd == "cities":
            if "spu" not in opts:
                print("请指定 --spu，例如：python party_scout.py cities --spu 5224",
                      file=sys.stderr)
                return 1
            show_cities(list_cities(client, int(opts["spu"])))

        elif cmd == "stores":
            if "spu" not in opts or "city" not in opts:
                print("请指定 --spu 和 --city，例如：\n"
                      "  python party_scout.py stores --spu 5224 --city 深圳市",
                      file=sys.stderr)
                return 1
            spu = int(opts["spu"])
            cities = list_cities(client, spu)
            city = find_city(cities, opts["city"])
            if not city:
                print(f"没找到城市「{opts['city']}」。该主题可办城市共 {len(cities)} 个，"
                      f"先用 cities 子命令看看。", file=sys.stderr)
                return 1
            print(f"\n城市：{city['name']}（code={city['code']}）")
            dist = float(opts["radius"]) if opts.get("radius") else None
            show_stores(list_stores(client, spu, city, dist))

        elif cmd == "slots":
            if "spu" not in opts or "store" not in opts:
                print("请指定 --spu 和 --store，例如：\n"
                      "  python party_scout.py slots --spu 5224 --store 1421131",
                      file=sys.stderr)
                return 1
            spu, store = int(opts["spu"]), opts["store"]
            dates_rows = list_dates(client, spu, store)
            sessions_by_date = {}
            for d in dates_rows:
                try:
                    sessions_by_date[d["date"]] = list_sessions(client, spu, store, d["date"])
                except McdMcpError as e:
                    sessions_by_date[d["date"]] = []
                    print(f"  （{d['date']} 场次获取失败：{e}）", file=sys.stderr)
            show_slots(dates_rows, sessions_by_date)

        else:
            print(f"未知命令：{cmd}\n"
                  "可用命令：parties / cities / stores / slots", file=sys.stderr)
            return 1
    except McdMcpError as e:
        print(f"\n查询失败：{e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
