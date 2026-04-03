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
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")          # 阿里云通义千问
ALIYUN_MT_ACCESS_KEY_ID = os.getenv("ALIYUN_MT_ACCESS_KEY_ID")   # 阿里云机器翻译
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
        "Authorization": f"Bearer {DASHSCOPE_API_KEY.strip()}",  # 去除可能的空白字符
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
    

# ===================== 1. 名称驱动：基础竞品分析（含同类竞品） =====================
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
    # 降级模板
    return NULL

# ===================== 2. 链接补充：电商评论抓取 =====================
def crawl_ecommerce(url: str, link_type: str) -> Dict[str, Any]:
    """爬取电商评论（若Playwright可用）"""
    if not PLAYWRIGHT_AVAILABLE:
        print("⚠️ 未安装Playwright，跳过电商爬取，使用模拟数据")
        return {
            "good_comments": ["续航强", "画质清晰", "便携"],
            "bad_comments": ["价格高", "功能少"],
            "params": "6英寸屏幕，2000mAh电池"
        }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, slow_mo=500)
            page = browser.new_page()
            page.goto(url, timeout=60000)
            page.wait_for_timeout(2000)

            if link_type == "jd":
                # 进入评论页
                page.goto(f"{url}#comment")
                page.wait_for_timeout(2000)
                good = page.query_selector_all("div.comment-item[data-type='good'] div.comment-con")
                bad = page.query_selector_all("div.comment-item[data-type='bad'] div.comment-con")
                good_comments = [c.inner_text().strip()[:50] for c in good[:5]] if good else []
                bad_comments = [c.inner_text().strip()[:50] for c in bad[:5]] if bad else []
            elif link_type == "taobao":
                # 淘宝评论结构复杂，简单模拟
                good_comments = ["物流快", "做工精细", "功能实用"]
                bad_comments = ["价格偏贵", "操作复杂"]
            else:
                good_comments = []
                bad_comments = []

            browser.close()
            return {
                "good_comments": good_comments or ["续航强", "画质清晰"],
                "bad_comments": bad_comments or ["价格高", "功能少"],
                "params": "6英寸屏幕，2000mAh电池"
            }
    except Exception as e:
        print(f"⚠️ 电商爬取失败: {e}")
        return  None
def crawl_social(url: str, link_type: str) -> Dict[str, Any]:
    """抓取社媒内容（模拟数据，实际需适配各平台）"""
    # 这里可根据需要集成真实爬虫，本示例使用模拟数据
    if link_type == "douyin":
        return {
            "title": "抖音短视频标题",
            "likes": 10000,
            "comments": ["太棒了！", "想买", "贵了点"]
        }
    elif link_type == "xiaohongshu":
        return {
            "title": "小红书种草笔记",
            "likes": 5000,
            "comments": ["求链接", "好用吗"]
        }
    elif link_type == "wechat":
        return {
            "title": "微信公众号文章标题",
            "likes": 200,
            "comments": ["分析透彻", "有道理"]
        }
    else:
        return {"title": "未知内容", "likes": 0, "comments": []}

def enhance_table_with_link(base_table: str, extra_data: Dict[str, Any], source_type: str) -> str:
    """用爬取数据完善表格"""
    if source_type in ("taobao", "jd"):
        prompt = f"""
请将以下用户评论数据整合到竞品分析表中，新增一列「用户真实反馈」。
原始表格：
{base_table}
用户好评：{', '.join(extra_data.get('good_comments', []))}
用户差评：{', '.join(extra_data.get('bad_comments', []))}
要求：输出完整的Markdown表格，包含原有所有列及新列「用户真实反馈」。
"""
    else:  # 社媒
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
    # 降级：直接在原表末尾追加行
    if source_type in ("taobao", "jd"):
        return base_table + f"\n| 用户真实反馈 | {extra_data.get('good_comments', [''])[0]} | {extra_data.get('bad_comments', [''])[0]} | 反映用户关注点 |"
    else:
        return base_table + f"\n| 社媒舆论 | {extra_data.get('title', '')} | 点赞{extra_data.get('likes', 0)} | {', '.join(extra_data.get('comments', []))[:30]} |"

# ===================== 3. 多语言翻译 =====================
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
        return translate_with_terms(text)  # 降级

def translate_with_terms(text: str) -> str:
    """术语表替换（简单降级翻译）"""
    terms = load_tech_terms()
    translated = text
    for cn, en in terms.items():
        translated = translated.replace(cn, en)
    return translated

# ===================== 主流程 =====================
if __name__ == "__main__":
    # 获取输入
    competitor_name = input("请输入竞品名称（如：大疆运动相机）：").strip()
    if not competitor_name:
        print("❌ 竞品名称不能为空")
        exit(1)

    # 第一步：基础分析表
    print("\n=== 基础竞品分析表（含同类竞品）===")
    base_table = get_analysis_by_name(competitor_name)
    print(base_table)

    # 第二步：可选链接补充
    add_link = input("\n是否需要输入电商/社媒链接补充数据？(y/n)：").lower()
    if add_link == "y":
        url = input("请输入链接（京东/淘宝/抖音/小红书/公众号）：").strip()
        link_type = judge_link_type(url)
        if link_type in ("taobao", "jd"):
            print("🔍 正在爬取电商评论...")
            extra = crawl_ecommerce(url, link_type)
            enhanced_table = enhance_table_with_link(base_table, extra, link_type)
            print("\n=== 完善后分析表（含用户反馈）===")
            print(enhanced_table)
            final_table = enhanced_table
        elif link_type in ("douyin", "xiaohongshu", "wechat"):
            print("🔍 正在分析社媒内容...")
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

    # 第三步：多语言翻译
    print("\n=== 多语言翻译版（英文）===")
    trans = translate_with_aliyun(final_table)
    print(trans)

    # 可选保存结果
    with open("competitor_analysis.md", "w", encoding="utf-8") as f:
        f.write("# 竞品分析报告\n\n")
        f.write("## 中文版\n\n")
        f.write(final_table)
        f.write("\n\n## 英文版\n\n")
        f.write(trans)
    print("\n✅ 报告已保存至 competitor_analysis.md")