import re
import os
import json
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from aliyunsdkcore.client import AcsClient
from aliyunsdkalimt.request.v20181012 import TranslateGeneralRequest

# 可选依赖（用于更稳定的网页抓取）
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

load_dotenv()

# ===================== 配置项 =====================
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
ALIYUN_MT_ACCESS_KEY_ID = os.getenv("ALIYUN_MT_ACCESS_KEY_ID")
ALIYUN_MT_ACCESS_KEY_SECRET = os.getenv("ALIYUN_MT_ACCESS_KEY_SECRET")
TERM_LIB_PATH = "tech_terms.json"

# ===================== 工具函数 =====================
def judge_link_type(url: str) -> str:
    """判断链接类型（电商/社媒）"""
    if re.search(r"taobao|tmall", url, re.I):
        return "taobao"
    elif re.search(r"jd\.com", url, re.I):
        return "jd"
    elif re.search(r"douyin\.com", url, re.I):
        return "douyin"
    elif re.search(r"xiaohongshu\.com", url, re.I):
        return "xiaohongshu"
    elif re.search(r"mp\.weixin\.qq\.com", url, re.I):
        return "wechat"
    else:
        return "unknown"

def load_tech_terms() -> dict:
    """加载中英术语库（降级翻译用）"""
    if not os.path.exists(TERM_LIB_PATH):
        default_terms = {
            "电子墨水屏": "E-ink Screen",
            "眼动追踪": "Eye Tracking",
            "续航时间": "Battery Life",
            "分辨率": "Resolution",
            "护眼": "Eye Protection",
            "便携": "Portable"
        }
        with open(TERM_LIB_PATH, "w", encoding="utf-8") as f:
            json.dump(default_terms, f, ensure_ascii=False, indent=2)
        return default_terms
    with open(TERM_LIB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def call_dashscope(prompt: str, temperature: float = 0.2) -> Optional[str]:
    if not DASHSCOPE_API_KEY:
        print("⚠️ DASHSCOPE_API_KEY 未配置")
        return None
    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY.strip()}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "qwen-turbo",
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "parameters": {"temperature": temperature, "result_format": "text"}
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        print(f"🔍 响应状态码: {response.status_code}")
        if response.status_code != 200:
            print(f"🔍 响应内容: {response.text[:500]}")
        response.raise_for_status()
        return response.json()["output"]["text"]
    except Exception as e:
        print(f"⚠️ 通义千问调用失败: {e}")
        return None

# ===================== 1. 名称驱动：基础竞品分析 =====================
def get_analysis_by_name(competitor_name: str, our_product: str = "智能电子墨水屏阅读器") -> str:
    """仅输入竞品名称，生成包含优劣、参数、同类竞品的分析表"""
    prompt = f"""
你是专业的智能硬件竞品分析师，请对比我方产品【{our_product}】和竞品【{competitor_name}】，输出标准Markdown表格。
表格列要求（适配市场/产品/研发多部门）：
| 对比维度 | 我方产品 | 竞品{competitor_name} | 优劣分析 |
|----------|----------|-----------------------|----------|
| 核心硬件参数 | 支持眼动追踪+7.5英寸E-ink墨水屏+2000mAh电池 | 竞品核心硬件参数 | 从硬件配置对比优劣 |
| 核心功能 | 眼动翻页+多格式电子书支持+云端同步 | 竞品核心功能 | 功能差异与用户体验对比 |
| 产品优势 | 护眼、便携、AI智能交互 | 竞品已知优势 | 我方优势是否具备差异化 |
| 产品劣势 | 暂无公开差评 | 竞品已知劣势 | 如何规避竞品的劣势 |
| 用户痛点匹配 | 解决长时间阅读护眼需求 | 竞品未解决的用户痛点 | 我方产品的市场机会 |
| 同类竞品 | （列出2-3个同价位/同类型竞品） | 竞品对比 | 与同类竞品相比，我方差异点 |

要求：
1. 只输出Markdown表格，无任何多余文字
2. 基于公开行业数据填写，参数真实可信
3. 同类竞品至少列出两个，并简要说明与我方产品的差异
"""
    result = call_dashscope(prompt)
    if result:
        return result
    # 降级：返回错误提示（原代码中的NULL已修复）
    return "❌ AI分析失败，请检查API配置或网络。"

# ===================== 2. 真实电商评论抓取（无模拟数据） =====================
def crawl_jd_comments(url: str) -> Optional[Dict[str, Any]]:
    """抓取京东真实好评和差评"""
    if not PLAYWRIGHT_AVAILABLE:
        print("⚠️ 未安装Playwright，无法抓取京东评论")
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=60000)
            page.wait_for_load_state("networkidle")
            
            # 方法1：尝试点击“商品评价”标签（新版京东可能为 #comment）
            try:
                page.click("#comment", timeout=5000)
                page.wait_for_timeout(2000)
            except:
                pass
            
            # 等待评论加载
            try:
                page.wait_for_selector(".comment-item", timeout=10000)
            except:
                # 降级：等待包含评价内容的通用容器
                page.wait_for_selector(".J-comment-item", timeout=10000)
            
            # 提取好评 (data-type="good" 或 class包含 good)
            good_items = page.query_selector_all(".comment-item[data-type='good'] .comment-con")
            if not good_items:
                good_items = page.query_selector_all(".J-comment-item.good .comment-con")
            good_comments = [item.inner_text().strip()[:100] for item in good_items[:5]] if good_items else []
            
            # 提取差评 (data-type="bad" 或 class包含 bad)
            bad_items = page.query_selector_all(".comment-item[data-type='bad'] .comment-con")
            if not bad_items:
                bad_items = page.query_selector_all(".J-comment-item.bad .comment-con")
            bad_comments = [item.inner_text().strip()[:100] for item in bad_items[:5]] if bad_items else []
            
            browser.close()
            
            if not good_comments and not bad_comments:
                print("⚠️ 京东页面未提取到任何评论")
                return None
                
            return {
                "good_comments": good_comments,
                "bad_comments": bad_comments,
            }
    except Exception as e:
        print(f"⚠️ 京东评论抓取失败: {e}")
        return None

def crawl_taobao_comments(url: str) -> Optional[Dict[str, Any]]:
    """抓取淘宝真实好评和差评（通过接口）"""
    # 提取商品ID
    item_id_match = re.search(r"id=(\d+)", url) or re.search(r"item\.htm\?id=(\d+)", url)
    if not item_id_match:
        print("⚠️ 无法从淘宝链接中提取商品ID")
        return None
    
    item_id = item_id_match.group(1)
    # 使用 tmall 评价接口（兼容淘宝和天猫）
    api_url = f"https://rate.tmall.com/list_detail_rate.htm?itemId={item_id}&currentPage=1&pageSize=10"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": url
    }
    try:
        resp = requests.get(api_url, headers=headers, timeout=15)
        text = resp.text
        # 提取 JSON 数据（兼容 JSONP 格式）
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if not json_match:
            print("⚠️ 淘宝评论接口返回格式异常")
            return None
        data = json.loads(json_match.group())
        
        rates = data.get("rates", {}).get("rateList", [])
        good_comments = []
        bad_comments = []
        for rate in rates:
            content = rate.get("rateContent", "").strip()
            if not content:
                continue
            rate_type = rate.get("rateType")  # 1:好评, 0:中评, -1:差评
            if rate_type == 1:
                good_comments.append(content[:100])
            elif rate_type == -1:
                bad_comments.append(content[:100])
        
        if not good_comments and not bad_comments:
            print("⚠️ 该淘宝商品暂无评论")
            return None
        
        return {
            "good_comments": good_comments[:5],
            "bad_comments": bad_comments[:5],
        }
    except Exception as e:
        print(f"⚠️ 淘宝评论抓取失败: {e}")
        return None

def crawl_ecommerce(url: str, link_type: str) -> Optional[Dict[str, Any]]:
    """统一入口：根据链接类型调用对应抓取函数，只返回真实数据"""
    if link_type == "jd":
        return crawl_jd_comments(url)
    elif link_type == "taobao":
        return crawl_taobao_comments(url)
    else:
        print(f"⚠️ 不支持的电商类型: {link_type}")
        return None

def crawl_social(url: str, link_type: str) -> Dict[str, Any]:
    """抓取社媒内容（当前仍为模拟，因为真实抓取需登录或API）"""
    # 注意：社媒真实抓取非常复杂，这里保留模拟数据，但你可以后续接入第三方API
    print("⚠️ 社媒真实评论抓取暂未实现，返回占位数据（非用户评价）")
    if link_type == "douyin":
        return {
            "title": "抖音短视频标题（示例）",
            "likes": 0,
            "comments": ["真实评论需接入抖音API"]
        }
    elif link_type == "xiaohongshu":
        return {
            "title": "小红书笔记标题（示例）",
            "likes": 0,
            "comments": ["需登录后爬取"]
        }
    elif link_type == "wechat":
        return {
            "title": "公众号文章标题（示例）",
            "likes": 0,
            "comments": ["需通过搜狗微信或其它方式"]
        }
    else:
        return {"title": "未知内容", "likes": 0, "comments": []}

def enhance_table_with_link(base_table: str, extra_data: Optional[Dict[str, Any]], source_type: str) -> str:
    if extra_data is None:
        print("⚠️ 没有获取到真实评论数据，跳过增强步骤")
        return base_table
    
    if source_type in ("taobao", "jd"):
        # 将好评和差评分别拼接，更易读
        good_str = "；".join(extra_data.get('good_comments', [])) if extra_data.get('good_comments') else "无好评"
        bad_str = "；".join(extra_data.get('bad_comments', [])) if extra_data.get('bad_comments') else "无差评"
        feedback_text = f"👍 好评：{good_str}\n👎 差评：{bad_str}"
        
        prompt = f"""
请将以下用户真实反馈整合到竞品分析表中，新增一列「用户真实反馈」。
原始表格：
{base_table}
用户反馈详情：
{feedback_text}
要求：输出完整的Markdown表格，包含原有所有列及新列「用户真实反馈」，反馈内容需包含好、差评摘要。
"""
        result = call_dashscope(prompt)
        if result:
            return result
        # 降级：直接追加一行
        return base_table + f"\n| 用户真实反馈 | {feedback_text.replace(chr(10), ' ')} | - | 来自真实用户评价 |"
    
    else:  # 社媒（保持原有模拟逻辑）
        prompt = f"""
请将以下社媒舆论数据整合到竞品分析表中，新增一列「社媒舆论」。
原始表格：
{base_table}
社媒标题：{extra_data.get('title', '')}
点赞数：{extra_data.get('likes', 0)}
热门评论：{', '.join(extra_data.get('comments', []))}
要求：输出完整的Markdown表格，包含原有所有列及新列「社媒舆论」。
"""
        result = call_dashscope(prompt)
        if result:
            return result
        return base_table + f"\n| 社媒舆论 | {extra_data.get('title', '')} | 点赞{extra_data.get('likes', 0)} | {', '.join(extra_data.get('comments', []))[:30]} |"

# ===================== 3. 多语言翻译（同前，已包含阿里云SDK） =====================
def translate_with_aliyun(text: str, source_lang: str = "zh", target_lang: str = "en") -> str:
    if not (ALIYUN_MT_ACCESS_KEY_ID and ALIYUN_MT_ACCESS_KEY_SECRET):
        print("⚠️ 未配置阿里云翻译密钥，使用术语表降级翻译")
        return translate_with_terms(text)
    
    client = AcsClient(ALIYUN_MT_ACCESS_KEY_ID, ALIYUN_MT_ACCESS_KEY_SECRET, "cn-hangzhou")
    request = TranslateGeneralRequest.TranslateGeneralRequest()
    request.set_FormatType("text")
    request.set_SourceLanguage(source_lang)
    request.set_TargetLanguage(target_lang)
    request.set_SourceText(text)
    
    try:
        response = client.do_action_with_exception(request)
        result = json.loads(response)
        return result["Data"]["Translated"]
    except Exception as e:
        print(f"⚠️ 翻译API调用失败: {e}")
        return translate_with_terms(text)

def translate_with_terms(text: str) -> str:
    terms = load_tech_terms()
    translated = text
    for cn, en in terms.items():
        translated = translated.replace(cn, en)
    return translated

# ===================== 主流程 =====================
if __name__ == "__main__":
    competitor_name = input("请输入竞品名称（如：大疆运动相机）：").strip()
    if not competitor_name:
        print("❌ 竞品名称不能为空")
        exit(1)

    print("\n=== 基础竞品分析表（含同类竞品）===")
    base_table = get_analysis_by_name(competitor_name)
    print(base_table)

    add_link = input("\n是否需要输入电商/社媒链接补充真实用户数据？(y/n)：").lower()
    if add_link == "y":
        url = input("请输入链接（京东/淘宝/抖音/小红书/公众号）：").strip()
        link_type = judge_link_type(url)
        if link_type in ("taobao", "jd"):
            print("🔍 正在抓取真实电商评论...")
            extra = crawl_ecommerce(url, link_type)
            if extra is None:
                print("❌ 未能获取到真实评论，将仅使用基础分析表")
                final_table = base_table
            else:
                enhanced_table = enhance_table_with_link(base_table, extra, link_type)
                print("\n=== 完善后分析表（含真实用户反馈）===")
                print(enhanced_table)
                final_table = enhanced_table
        elif link_type in ("douyin", "xiaohongshu", "wechat"):
            print("🔍 正在尝试获取社媒内容（当前为示例，非真实评价）...")
            extra = crawl_social(url, link_type)
            enhanced_table = enhance_table_with_link(base_table, extra, link_type)
            print("\n=== 完善后分析表（含社媒舆论）===")
            print(enhanced_table)
            final_table = enhanced_table
        else:
            print("⚠️ 链接类型暂不支持，使用基础表")
            final_table = base_table
    else:
        final_table = base_table

    print("\n=== 多语言翻译版（英文）===")
    trans = translate_with_aliyun(final_table)
    print(trans)

    with open("competitor_analysis.md", "w", encoding="utf-8") as f:
        f.write("# 竞品分析报告\n\n")
        f.write("## 中文版\n\n")
        f.write(final_table)
        f.write("\n\n## 英文版\n\n")
        f.write(trans)
    print("\n✅ 报告已保存至 competitor_analysis.md")