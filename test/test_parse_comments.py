import sys
import os
# 添加專案根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from agent.custom.reviewer import Reviewer, MergeRequestInfo
from agent.core.base import AgentConfig
from agent.llm.providers.bedrock import BedrockProvider, BedrockConfig
import json
from mcp_servers.code_review.tools import add_row_to_lark_sheet
import datetime

async def test_add_row_to_lark_sheet():
    """
    單獨測試 add_row_to_lark_sheet 函式
    """
    try:
        # 初始化 Bedrock 配置
        bedrock_config = BedrockConfig(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            region="us-west-2",
            max_tokens=4096,
            temperature=0.7
        )

        # 初始化 Bedrock Provider
        bedrock_provider = BedrockProvider(bedrock_config)

        # 初始化 Agent 配置
        agent_config = AgentConfig(llm=bedrock_provider)

        # 初始化 Reviewer
        reviewer = Reviewer(agent_config)
        
        # 初始化 reviewer
        print("正在初始化 reviewer...")
        await reviewer.initialize()
        print("reviewer 初始化完成")

        # 設置 group_mode 為 app
        success = await reviewer.set_group_mode("app")
        if not success:
            print("設置 group_mode 失敗")
            return


        # 創建測試用的假數據
        test_metrics = {
            'date': datetime.datetime.now().strftime("%Y-%m-%d"),
            'score': 95,
            'critical_issues': 0,
            'medium_issues': 2,
            'minor_issues': 3,
            'critical_reasons': ['安全性問題', '性能問題'],
            'dimensions': ['代碼質量', '安全性'],
            'tags': ['React', 'JavaScript']
        }

        test_mr_info = MergeRequestInfo(
            project_id="2167",
            project_url="",
            merge_request_iid=831,
            commit_sha="abc123",
            diff_refs={}
        )

        print("\n=== 開始測試 add_row_to_lark_sheet ===")
        print("測試數據：")
        print(f"Metrics: {json.dumps(test_metrics, ensure_ascii=False, indent=2)}")
        print(f"MR Info: {test_mr_info}")

        # 執行測試
        result = await reviewer.review_session.call_tool('add_row_to_lark_sheet', {
            "metrics": test_metrics,
            "mr_info": {
                "project_id": test_mr_info.project_id,
                "project_url": test_mr_info.project_url,
                "merge_request_iid": test_mr_info.merge_request_iid,
                "commit_sha": test_mr_info.commit_sha or "",
                "diff_refs": test_mr_info.diff_refs or {}
            }
        })
        
        print("\n=== 測試結果 ===")
        if result.isError:
            print(f"錯誤：{result.content[0].text if result.content else '未知錯誤'}")
        else:
            print(f"結果：{result.content[0].text if result.content else '成功'}")

    except Exception as e:
        print(f"測試過程中發生錯誤：{str(e)}")
        import traceback
        print("錯誤詳情：")
        print(traceback.format_exc())
    finally:
        # 清理資源
        print("\n正在清理資源...")
        await reviewer.cleanup()
        print("資源清理完成")

async def test_parse_comments():
    # 測試用的評論內容
    test_comments = """
    🧾 文件: src/components/GlobalLayout/FooterLayout/index.jsx

审查评分：95/100
共发现 2 处问题


⚠️ 中等问题
【最佳实践】Telegram链接中的前导空格


代码示例：

const isId = router.locale === 'id';
let _href = isId ? 'https://t.me/+rMT4NVtpNEQwMGZl' : ' https://t.me/alphaiglobalchat';
window.open(`${_href}`, '_blank');




主要问题：非印尼语言环境下的Telegram链接中包含了前导空格，可能导致链接无法正确打开（严重程度: 中等 | -4 分）

参考：📚 逻辑正确&最佳实践

建议：✅ 移除链接中的前导空格

let _href = isId ? 'https://t.me/+rMT4NVtpNEQwMGZl' : 'https://t.me/alphaiglobalchat';





✅ 轻微问题
【最佳实践】变量命名不规范


代码示例：

let _href = isId ? 'https://t.me/+rMT4NVtpNEQwMGZl' : ' https://t.me/alphaiglobalchat';




主要问题：使用下划线前缀命名变量不符合JavaScript常规命名约定（严重程度: 轻微 | -1 分）

参考：📚 变量命名规范

建议：✅ 使用符合驼峰命名法的变量名

let telegramUrl = isId ? 'https://t.me/+rMT4NVtpNEQwMGZl' : 'https://t.me/alphaiglobalchat';





🧾 文件: src/constants/layout.js

审查评分：100/100
共发现 0 处问题


✨ 代码审查结果
当前代码符合审查规范要求，暂未发现问题。
🧾 文件: src/constants/socketKeys.js

审查评分：100/100
共发现 0 处问题


✨ 代码审查结果
当前代码符合审查规范要求，暂未发现问题。

🧾 文件: src/store/token.js

审查评分：94/100
共发现 2 处问题


⚠️ 中等问题
【性能】启用了生产环境中的调试日志


代码示例：

// src/store/token.js:
      }
      newHolding.totalProfit = newHolding.unrealizedProfit + newHolding.totalPnl; //总利润=已实现利润+未实现利润







   console.log('newHolding=====>', newHolding);
  this.updateState({
    holding: newHolding,
    tokenInfo: newTokenInfo










主要问题：代码中保留了调试用的 console.log 语句，在生产环境中可能导致性能问题和信息泄露（严重程度: 中等 | -4 分）

相关问题：

【安全性】暴露了内部数据结构，可能泄露敏感信息（严重程度: 轻微 | -2 分）



参考：📚 性能优化最佳实践

建议：✅ 移除或使用条件判断限制生产环境中的调试日志，如：

if (process.env.NODE_ENV !== 'production') {
  console.log('newHolding=====>', newHolding);
}





✅ 轻微问题
【最佳实践】重复使用相同数据源


代码示例：

// src/store/token.js:
        newHolding.totalBuyCost = totalBuyCostMap[this.currentToken] || newHolding.totalBuyCost;









     newHolding.totalBuyCostMain =







       totalBuyCostMap[this.currentToken] || newHolding.totalBuyCostMain; //买入总花费-我的交易数据概览用










主要问题：代码从相同的数据源 totalBuyCostMap[this.currentToken] 给两个不同的属性赋值，可能导致数据一致性问题（严重程度: 轻微 | -2 分）

参考：📚 数据一致性最佳实践

建议：✅ 先将值存储在临时变量中，然后再分别赋值给两个属性，或者确保两个属性的用途确实需要独立赋值：

const currentTokenBuyCost = totalBuyCostMap[this.currentToken];
newHolding.totalBuyCost = currentTokenBuyCost || newHolding.totalBuyCost;
newHolding.totalBuyCostMain = currentTokenBuyCost || newHolding.totalBuyCostMain;





🧾 文件: src/utils/index.js

审查评分：96/100
共发现 2 处问题


⚠️ 中等问题
【安全性】动态脚本执行缺少安全验证


代码示例：

export function importScript(url, key) {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.setAttribute('src', url);
    document.head.appendChild(script);
    
    // ...
  });
}




主要问题：importScript函数缺少对URL参数的安全验证，可能导致跨站脚本攻击（严重程度: 中等 | -4 分）

参考：📚 防止XSS安全规范

建议：✅ 添加URL验证逻辑，确保只加载可信来源的脚本，例如添加白名单检查或URL格式验证


✅ 轻微问题
【最佳实践】缺少内存泄漏防护


代码示例：

script.addEventListener('error', (error) => {
  reject(error);
});




主要问题：脚本加载失败时没有移除script元素，可能导致内存泄漏（严重程度: 轻微 | -2 分）

参考：📚 避免内存泄漏规范

建议：✅ 在error回调中也移除script元素

script.addEventListener('error', (error) => {
  document.head.removeChild(script);
  reject(error);
});





🧾 文件: src/views/token/list/tables/MyTradesTable.jsx

审查评分：93/100
共发现 3 处问题


⚠️ 中等问题
【性能】WebSocket依赖未优化


代码示例：

React.useEffect(() => {
  if (status === 'OPEN') {
    const unsubs = subscribe([{ chain, token, type: 'swap' }], handleSocketMessage);

    unsubscribeFns.current = unsubscribeFns.current.concat(unsubs);
  }
}, [status, handleSocketMessage, chain, token]);




主要问题：WebSocket订阅依赖项包含了handleSocketMessage回调，该回调依赖filters和walletInfo，但这两个依赖未加入effect依赖数组，可能导致WebSocket不会在这些值变化时重新订阅（严重程度: 中等 | -4 分）

参考：📚 React Hooks依赖规则

建议：✅ 将所有依赖项添加到useEffect的依赖数组中，或者考虑重构handleSocketMessage函数以减少依赖

【最佳实践】缺少错误处理机制


代码示例：

const handleSocketMessage = React.useCallback(
  (res) => {
    if (res.e !== 'swap') return;
    const processedData = processSocketData(res);
    const _filters = {
      ...filters,
      maker: walletInfo?.wallet
    };
    const showUpdate = filterWsData(processedData, _filters);
    if (showUpdate) {
      updateDataSource(processedData);
    }
  },
  [filters, processSocketData, updateDataSource, walletInfo]
);




主要问题：WebSocket数据处理缺少错误处理机制，如果收到的数据格式不符合预期或处理过程出错，可能导致组件崩溃（严重程度: 中等 | -4 分）

参考：📚 错误边界处理最佳实践

建议：✅ 添加try-catch块处理潜在的数据解析和处理错误


✅ 轻微问题
【最佳实践】代码中存在潜在重复渲染风险


代码示例：

const _filters = {
  ...filters,
  maker: walletInfo?.wallet
};




主要问题：在handleSocketMessage回调中每次创建新的filters对象，可能导致不必要的重新渲染（严重程度: 轻微 | -3 分）

参考：📚 React性能优化指南

建议：✅ 考虑将这个逻辑移到useCallback之外，或使用useMemo缓存_filters对象


🧾 文件: src/views/token/list/Profits.jsx

审查评分：95/100
共发现 2 处问题


⚠️ 中等问题
【最佳实践】重复的空值检查


代码示例：

const balanceData = useMemo(() => {
  if (!holding || Object.keys(holding).length === 0) {
    return {};
  }
  const {
    amountSol: valueBalance,
    positionPercent,
    totalBuyCostMain: totalAmount,
    avgBuyPrice: avgPrice,
    sellAmount: saleAmount,
    avgSellPrice: avgSale,
    totalPnl: realizedProfit,
    unrealizedProfit,
    totalProfit
  } = holding || {};
  return {
    valueBalance,
    positionPercent,
    totalAmount,
    avgPrice,
    saleAmount,
    avgSale,
    realizedProfit,
    unrealizedProfit,
    totalProfit
  };
}, [holding]);




主要问题：代码中存在重复的空值检查，一次是在 if 条件中，另一次是在解构赋值时（严重程度: 中等 | -4 分）

参考：📚 React 最佳实践 - 逻辑冗余处理

建议：✅ 移除解构赋值中的重复空值检查，因为已经在前面进行了判断

const balanceData = useMemo(() => {
  if (!holding || Object.keys(holding).length === 0) {
    return {};
  }
  const {
    amountSol: valueBalance,
    positionPercent,
    totalBuyCostMain: totalAmount,
    avgBuyPrice: avgPrice,
    sellAmount: saleAmount,
    avgSellPrice: avgSale,
    totalPnl: realizedProfit,
    unrealizedProfit,
    totalProfit
  } = holding;
  return {
    valueBalance,
    positionPercent,
    totalAmount,
    avgPrice,
    saleAmount,
    avgSale,
    realizedProfit,
    unrealizedProfit,
    totalProfit
  };
}, [holding]);





✅ 轻微问题
【性能】未检查钱包地址是否存在


代码示例：

const { walletInfo = {} } = useUserWalletSnapshot();
const { holding = {} } = useTokenInfo({
  token,
  chain,
  walletAddress: walletInfo?.wallet,
  language
});




主要问题：在调用 useTokenInfo 时没有检查 walletInfo?.wallet 是否存在，可能导致不必要的请求（严重程度: 轻微 | -1 分）

参考：📚 React 性能优化 - 条件请求控制

建议：✅ 在确保钱包地址存在时才调用 useTokenInfo

const { walletInfo = {} } = useUserWalletSnapshot();
const { holding = {} } = useTokenInfo(walletInfo?.wallet ? {
  token,
  chain,
  walletAddress: walletInfo.wallet,
  language
} : null);





🧾 文件: src/views/token/list/usePnl.jsx

审查评分：97/100
共发现 1 处问题


✅ 轻微问题
【最佳实践】类型检查逻辑调整


代码示例：

// src/views/token/list/usePnl.jsx:





@@ -14,10 +14,8 @@ const usePnl = () => {
const formatPNL = React.useCallback(
(value, { includeSign = true, decimalPlaces = 3 } = {}) => {



 if (!value) return '--';









 if (typeof value !== 'number' && !value) return '--';
 const convertedValue = multip(value, currentQuote === 'USD' ? price : 1, decimalPlaces);







 return addUnitAndSign(convertedValue, {
   unit: currentQuote === 'USD' ? '$' : currentQuote,
   decimalPlaces,








主要问题：类型检查逻辑可能导致边界情况处理不完善（严重程度: 轻微 | -3 分）

参考：📚 边界情况处理最佳实践

建议：✅ 当 value 为 0 时，原代码会将其视为有效值并继续处理，而新代码会将 0 视为有效数字。这种变更可能导致不同的行为，应确认这是否符合业务需求。考虑使用更明确的条件：

if (value === null || value === undefined || Number.isNaN(value)) return '--'
    """

    # 創建測試用的 MR 信息
    mr_info = MergeRequestInfo(
        project_id="2167",
        project_url="",
        merge_request_iid=831,
        commit_sha="abc123",
        diff_refs={}
    )

    # 初始化 Bedrock 配置
    bedrock_config = BedrockConfig(
        model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        region="us-west-2",
        max_tokens=4096,
        temperature=0.7
    )

    # 初始化 Bedrock Provider
    bedrock_provider = BedrockProvider(bedrock_config)

    # 初始化 Agent 配置
    agent_config = AgentConfig(llm=bedrock_provider)

    # 初始化 Reviewer
    reviewer = Reviewer(agent_config)

    try:
        # 初始化 reviewer
        print("正在初始化 reviewer...")
        await reviewer.initialize()
        print("reviewer 初始化完成")
        
        # 測試新的 summarize_review 功能
        print("開始測試 summarize_review...")
        metrics, summary = await reviewer.summarize_review(test_comments, mr_info)
        
        if metrics and summary:
            print("\n=== 結構化數據 ===")
            print(f"平均分數：{metrics.get('score', 0)}")
            print(f"嚴重錯誤數量：{metrics.get('critical_issues', 0)}")
            print(f"中度錯誤數量：{metrics.get('medium_issues', 0)}")
            print(f"輕微錯誤數量：{metrics.get('minor_issues', 0)}")
            print(f"嚴重錯誤原因：{', '.join(metrics.get('critical_reasons', []))}")
            print(f"維度：{', '.join(metrics.get('dimensions', []))}")
            print(f"標籤：{', '.join(metrics.get('tags', []))}")
            
            print("\n=== 總結文本 ===")
            print(summary)
            
            # 發送到 Lark 群組
            print("\n=== 發送到 Lark 群組 ===")
            lark_res = await reviewer.post_to_lark(summary)
            print(f"Lark 發送結果：{lark_res}")
            
            # 記錄到 Lark sheet
            print("\n=== 記錄到 Lark sheet ===")
            sheet_res = await reviewer.append_data_to_sheet_last_row(metrics, mr_info)
            print(f"Sheet 記錄結果：{sheet_res}")
        else:
            print("生成總結失敗")
            
    except Exception as e:
        print(f"發生錯誤：{str(e)}")
        import traceback
        print("錯誤詳情：")
        print(traceback.format_exc())
        
        # 如果是 JSON 解析錯誤，打印原始輸出
        if isinstance(e, json.JSONDecodeError):
            print("\n=== LLM 原始輸出 ===")
            try:
                # 重新獲取 prompt 和結果
                prompt_response = await reviewer.review_session.get_prompt('get_lark_summary_prompt', {
                    'comments': test_comments
                })
                prompt = reviewer._get_text(prompt_response.messages[0].content)
                print("\n=== Prompt 內容 ===")
                print(prompt)
                
                result = ""
                async for chunk in reviewer.config.llm.generate(prompt):
                    result += chunk.text
                print("\n=== LLM 輸出 ===")
                print(result)
            except Exception as inner_e:
                print(f"獲取調試信息時發生錯誤：{str(inner_e)}")
    finally:
        # 清理資源
        print("\n正在清理資源...")
        await reviewer.cleanup()
        print("資源清理完成")

if __name__ == "__main__":
    # 選擇要運行的測試
    test_choice = input("請選擇要運行的測試 (1: test_parse_comments, 2: test_add_row_to_lark_sheet): ")
    
    if test_choice == "1":
        asyncio.run(test_parse_comments())
    elif test_choice == "2":
        asyncio.run(test_add_row_to_lark_sheet())
    else:
        print("無效的選擇，請輸入 1 或 2") 