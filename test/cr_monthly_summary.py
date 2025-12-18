import requests
import datetime
import pandas as pd
from collections import Counter
import os
from typing import Dict, List, Tuple
import json
import traceback
import re

# ======== 固定配置 ========
APP_ID = "cli_a7eb86f47eb8902f"  # app_id
APP_SECRET = "p68XxhhEJMvpga1yUo9qDcLoNYHukU2q"  # app_secret
SPREADSHEET_TOKEN = "OfqJsyVV3hxdlHtJEidlE3R3g5e"  # spreadsheet token
SHEET_ID = "g5b5fO"  # sheet ID
LARK_WEBHOOK_URL = "https://open.larksuite.com/open-apis/bot/v2/hook/bf852fca-df94-40ea-a055-8430b4e78ffd"  # webhook URL

def get_previous_week_range() -> Tuple[str, str]:
    """
    獲取前七天的時間
    返回格式：YYYY-MM-DD
    例如：如果今天是 2024-03-15（週五），則返回 2024-03-08 和 2024-03-14
    """
    today = datetime.datetime.now()
    
    # 計算本週四的日期（今天往前推一天）
    this_thursday = today - datetime.timedelta(days=1)
    
    # 計算上週五的日期（本週四往前推 6 天）
    last_friday = this_thursday - datetime.timedelta(days=6)
    
    return last_friday.strftime("%Y-%m-%d"), this_thursday.strftime("%Y-%m-%d")

def get_lark_access_token(app_id: str, app_secret: str) -> str:
    """
    根據 app_id / app_secret 取得 Lark tenant access token
    """
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {"app_id": app_id, "app_secret": app_secret}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        token = data.get("tenant_access_token")
        if not token:
            raise RuntimeError("未能成功取得 Lark access token")
        return token
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"獲取 access token 失敗：{str(e)}")

def fetch_sheet_data(access_token: str) -> List[List[str]]:
    """
    讀取 Lark Sheet 上的資料
    """
    url = f"https://open.larksuite.com/open-apis/sheets/v2/spreadsheets/{SPREADSHEET_TOKEN}/values/{SHEET_ID}!A:I"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        values = data.get("data", {}).get("valueRange", {}).get("values", [])
        if not values:
            raise RuntimeError("Sheet 中沒有數據")
            
        # # 打印原始數據
        # print("\n=== 原始 Sheet 數據 ===")
        # print("數據行數：", len(values))
        # print("第一行（標題）：", values[0] if values else "無數據")
        # print("第二行（數據）：", values[1] if len(values) > 1 else "無數據")
        # print("所有數據：")
        # for i, row in enumerate(values):
        #     print(f"第 {i+1} 行：{row}")
            
        return values
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"讀取 Sheet 數據失敗：{str(e)}")

def analyze_cr_data(rows: List[List[str]], start_date: str, end_date: str) -> Dict:
    """
    分析 CR 表單資料並回傳報告摘要
    """
    try:
        # 檢查並添加標籤列
        headers = ["date", "mr_link", "score", "critical", "major", "minor", "reasons", "dimensions", "tags"]
        if len(rows[1]) < len(headers):
            # 如果列數不足，添加空列
            for row in rows[1:]:
                while len(row) < len(headers):
                    row.append("")
        
        df = pd.DataFrame(rows[1:], columns=headers)
        
        # 轉換日期格式
        def parse_date(date_str: str) -> datetime.datetime:
            try:
                # 處理 Excel 數字日期格式
                if isinstance(date_str, (int, float)):
                    # Excel 的日期是從 1900-01-01 開始的天數
                    excel_epoch = datetime.datetime(1899, 12, 30)
                    return excel_epoch + datetime.timedelta(days=float(date_str))
                
                # 嘗試多種日期格式
                date_formats = [
                    "%Y-%m-%d %H:%M:%S",  # 2025-06-12 12:29:11
                    "%Y-%m-%d %H:%M",     # 2025-06-12 12:29
                    "%m/%d/%Y %H:%M",     # 5/12/2025 12:29
                    "%m/%d/%Y",           # 5/12/2025
                    "%Y-%m-%d",           # 2025-06-12
                    "%Y/%m/%d"            # 2025/06/12
                ]
                
                for fmt in date_formats:
                    try:
                        return datetime.datetime.strptime(str(date_str), fmt)
                    except ValueError:
                        continue
                
                raise ValueError(f"無法解析日期格式：{date_str}")
            except Exception as e:
                print(f"警告：日期解析錯誤 {date_str}: {str(e)}")
                return None

        # 轉換日期列
        df["date"] = df["date"].apply(parse_date)
        
        # 過濾無效日期
        df = df.dropna(subset=["date"])
        
        # 轉換日期範圍為 datetime 對象（使用當天的開始和結束時間）
        start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
        
        # 過濾日期範圍
        df = df[(df["date"] >= start_dt) & (df["date"] <= end_dt)]

        if df.empty:
            return {
                "error": True,
                "message": f"🔍 {start_date} 至 {end_date} 期間內無 CR 記錄。"
            }

        # 基本統計
        total_cr = len(df)
        avg_score = round(df["score"].astype(float).mean(), 1)
        total_critical = df["critical"].astype(int).sum()
        total_major = df["major"].astype(int).sum()
        total_minor = df["minor"].astype(int).sum()
        total_errors = total_critical + total_major + total_minor

        # 計算維度統計
        all_dimensions = []
        for items in df["dimensions"].dropna():
            # 將所有分隔符統一替換成英文逗號
            items = re.sub(r"[，、,；;]", ",", str(items))
            dimensions = [d.strip() for d in items.split(",") if d.strip()]
            all_dimensions.extend(dimensions)
        
        # 統計每個維度的出現次數
        dimension_count = Counter(all_dimensions)
        total_dimension = sum(dimension_count.values())
        
        # 計算每個維度的統計數據
        dimensions_stats = [
            {
                "name": dimension,
                "count": count,
                "percentage": round(count * 100 / total_dimension, 1)
            }
            for dimension, count in sorted(dimension_count.items(), key=lambda x: (-x[1], x[0]))
        ] if total_dimension > 0 else []

        # 計算標籤統計
        all_tags = []
        for items in df["tags"].dropna():
            # 將所有分隔符統一替換成英文逗號
            items = re.sub(r"[，、,；;]", ",", str(items))
            tags = [t.strip() for t in items.split(",") if t.strip()]
            all_tags.extend(tags)
        
        # 統計每個標籤的出現次數
        tag_count = Counter(all_tags)
        total_tags = sum(tag_count.values())
        
        # 計算每個標籤的統計數據
        tags_stats = [
            {
                "name": tag,
                "count": count,
                "percentage": round(count * 100 / total_tags, 1)
            }
            for tag, count in sorted(tag_count.items(), key=lambda x: (-x[1], x[0]))
        ] if total_tags > 0 else []

        return {
            "error": False,
            "data": {
                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "total_cr": total_cr,
                "avg_score": avg_score,
                "total_errors": total_errors,
                "critical_errors": {
                    "count": total_critical,
                    "percentage": round(total_critical * 100 / total_errors, 1) if total_errors > 0 else 0
                },
                "major_errors": total_major,
                "minor_errors": total_minor,
                "dimensions": dimensions_stats,
                "tags": tags_stats
            }
        }
    except Exception as e:
        print(f"錯誤詳情：{str(e)}")
        print(f"錯誤追蹤：{traceback.format_exc()}")
        return {
            "error": True,
            "message": f"分析數據時發生錯誤：{str(e)}"
        }

def format_summary_text(analysis_result: Dict) -> str:
    """
    格式化摘要文字
    """
    if analysis_result["error"]:
        return analysis_result["message"]

    data = analysis_result["data"]
    
    # 打印調試信息
    # print("\n=== 格式化摘要 ===")
    # print("維度數據：", data["dimensions"])
    # print("標籤數據：", data["tags"])
    
    # 格式化維度統計
    dimensions_text = "\n".join([
        f"- {item['name']} {item['count']} 次（{item['percentage']}%）"
        for item in data["dimensions"]
    ]) or "- 无"
    

    # 格式化標籤統計
    tags_text = "\n".join([
        f"- {item['name']} {item['count']} 次（{item['percentage']}%）"
        for item in data["tags"]
    ]) or "- 无"
    

    # 獲取前七天的時間範圍
    start_date, end_date = get_previous_week_range()
    date_range = f"{start_date} 至 {end_date}"

    # 構建摘要文本
    summary_parts = [
        f"📝 {datetime.datetime.now().strftime('%Y年%m月%d日')} CR 审查总结",
        "表单链接：https://v4e63qkkti7.sg.larksuite.com/sheets/OfqJsyVV3hxdlHtJEidlE3R3g5e?sheet=g5b5fO",
        f"日期范围：{date_range}",
        f"总 CR 次数：{data['total_cr']} 次",
        f"平均 CR 分数：{data['avg_score']} 分",
        f"错误总数量：{data['total_errors']} 次",
        f"严重错误数量：{data['critical_errors']['count']} 次（{data['critical_errors']['percentage']}%）",
        f"中等错误数量：{data['major_errors']} 次",
        f"低等错误数量：{data['minor_errors']} 次",
        "",
        "📊 维度分布：",
        dimensions_text,
        "",
        "🏷️ 标签分布：",
        tags_text
    ]

    summary = "\n".join(summary_parts)
    
    print("\n最終摘要文本：")
    print(summary)
    
    return summary

def send_message_to_lark_group(summary_text: str) -> bool:
    """
    傳送 Lark 表格格式卡片訊息到群組
    """
    headers = {"Content-Type": "application/json"}

    # 解析摘要文字
    lines = summary_text.split('\n')
    title = lines[0]
    date_range = lines[2].split('：')[1]
    total_cr = lines[3].split('：')[1]
    avg_score = lines[4].split('：')[1]
    total_errors = lines[5].split('：')[1]
    critical_errors = lines[6].split('：')[1]
    major_errors = lines[7].split('：')[1]
    minor_errors = lines[8].split('：')[1]

    # 構建卡片消息
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**日期范围：**{date_range}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "**链接：**[查看原始数据](https://v4e63qkkti7.sg.larksuite.com/sheets/OfqJsyVV3hxdlHtJEidlE3R3g5e?sheet=g5b5fO)"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**总 CR 次数：**{total_cr}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**平均 CR 分数：**{avg_score}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**错误总数量：**{total_errors}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**严重错误数量：**{critical_errors}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**中等错误数量：**{major_errors}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**低等错误数量：**{minor_errors}"
                    }
                },
                {
                    "tag": "hr"
                }
            ]
        }
    }

    # 添加維度分布
    dimension_lines = []
    tag_lines = []
    current_section = None
    
    # 找到維度部分的起始位置
    dimension_start = -1
    tag_start = -1
    for i, line in enumerate(lines):
        if line.startswith('📊'):
            dimension_start = i
        elif line.startswith('🏷️'):
            tag_start = i
            break
    
    # 提取維度行
    if dimension_start != -1 and tag_start != -1:
        dimension_lines = [line for line in lines[dimension_start+1:tag_start] if line.strip()]
    
    # 提取標籤行
    if tag_start != -1:
        tag_lines = [line for line in lines[tag_start+1:] if line.strip()]

    # 添加維度分布標題
    payload["card"]["elements"].append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": "**维度分布：**"
        }
    })

    # 添加維度分布
    for line in dimension_lines:
        payload["card"]["elements"].append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": line
            }
        })

    # 添加分隔線
    payload["card"]["elements"].append({
        "tag": "hr"
    })

    # 添加標籤分布標題
    payload["card"]["elements"].append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": "**标签分布：**"
        }
    })

    # 添加標籤分布
    for line in tag_lines:
        payload["card"]["elements"].append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": line
            }
        })

    try:
        print("\n=== 最終消息 ===")
        print(summary_text)
        print("\n=== Payload ===")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        
        response = requests.post(LARK_WEBHOOK_URL, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
        
        if result.get("StatusCode", 0) == 0:
            print("✅ 成功推送審查摘要到 Lark 群組")
            return True
        else:
            error_msg = f"消息推送失敗: {result.get('msg', '未知錯誤')}"
            print(f"❗ {error_msg}")
            return False
    except Exception as e:
        error_msg = f"發送訊息時發生錯誤：{str(e)}"
        print(f"❗ {error_msg}")
        return False

def send_error_notification(error_message: str) -> bool:
    """
    發送錯誤通知到 Lark 群組
    """
    headers = {"Content-Type": "application/json"}
    current_month = datetime.datetime.now().strftime("%Y年%m月")

    payload = {
        "msg_type": "text",
        "content": {
            "text": f"⚠️ {current_month} CR 稽核月報執行異常\n\n執行時間：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n錯誤信息：\n{error_message}"
        }
    }

    try:
        print(f"正在發送錯誤通知到 Lark 群組...")
        print(f"Webhook URL: {LARK_WEBHOOK_URL}")
        print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        
        response = requests.post(LARK_WEBHOOK_URL, json=payload, headers=headers)
        print(f"Response status code: {response.status_code}")
        print(f"Response content: {response.text}")
        
        response.raise_for_status()
        result = response.json()
        
        if result.get("StatusCode", 0) == 0:
            print("✅ 成功推送錯誤通知到 Lark 群組")
            return True
        else:
            error_msg = f"錯誤通知推送失敗: {result.get('msg', '未知錯誤')}"
            print(f"❗ {error_msg}")
            return False
    except Exception as e:
        error_msg = f"發送錯誤通知時發生錯誤：{str(e)}"
        print(f"❗ {error_msg}")
        return False

def main():
    try:
        # 獲取上週五到本週四的日期範圍
        try:
            start_date, end_date = get_previous_week_range()
            print(f"分析時間範圍：{start_date} 至 {end_date}")
        except Exception as e:
            error_msg = f"獲取日期範圍失敗：{str(e)}"
            print(f"❗ {error_msg}")
            send_error_notification(error_msg)
            return

        # 獲取 access token
        try:
            access_token = get_lark_access_token(APP_ID, APP_SECRET)
            print("✅ 成功獲取 access token")
        except Exception as e:
            error_msg = f"獲取 access token 失敗：{str(e)}"
            print(f"❗ {error_msg}")
            send_error_notification(error_msg)
            return

        # 讀取 sheet 數據
        try:
            data = fetch_sheet_data(access_token)
            print(f"✅ 成功讀取 {len(data)} 行數據")
        except Exception as e:
            error_msg = f"讀取 Sheet 數據失敗：{str(e)}"
            print(f"❗ {error_msg}")
            send_error_notification(error_msg)
            return

        # 分析數據
        analysis_result = analyze_cr_data(data, start_date, end_date)
        if analysis_result["error"]:
            error_msg = analysis_result["message"]
            print(f"❗ {error_msg}")
            send_error_notification(error_msg)
            return

        # 格式化摘要
        summary_text = format_summary_text(analysis_result)
        # print("\n=== 摘要內容 ===")
        # print(summary_text)

        # 發送到 Lark 群組
        if not send_message_to_lark_group(summary_text):
            error_msg = "發送摘要到 Lark 群組失敗"
            print(f"❗ {error_msg}")
            send_error_notification(error_msg)
            return

    except Exception as e:
        error_msg = f"執行過程中發生未預期的錯誤：{str(e)}\n\n錯誤詳情：\n{traceback.format_exc()}"
        print(f"❗ {error_msg}")
        send_error_notification(error_msg)
        return

if __name__ == "__main__":
    main()
