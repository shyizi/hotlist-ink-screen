from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
from datetime import datetime
import time
import schedule
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ====================== 【配置区-从环境变量读取】======================
DEVICE_ID = os.getenv("DEVICE_ID")
API_KEY = os.getenv("API_KEY")
PAGE_ID = int(os.getenv("PAGE_ID", 5))
PER_PAGE = int(os.getenv("PER_PAGE", 8))          # 一屏最多8条
INTERVAL_MINUTES = int(os.getenv("INTERVAL_MINUTES", 10))  # 每页停留10分钟
FONT_PATH = os.getenv("FONT_PATH", "font.ttf")    # 自定义字体路径
# 三大热榜接口
SOURCES = [
    {"name": "抖音热榜",    "url": "https://dabenshi.cn/other/api/hot.php?type=douyinhot"},
    {"name": "头条热榜",    "url": "https://dabenshi.cn/other/api/hot.php?type=toutiaoHot"},
    {"name": "百度热搜",    "url": "https://dabenshi.cn/other/api/hot.php?type=baidu"}
]
# ======================================================

# 全局状态
current_source_idx = 0
current_page = 0
current_data = []

# 校验环境变量
def check_env():
    """校验必要环境变量是否配置"""
    required = ["DEVICE_ID", "API_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise ValueError(f"缺少必要环境变量：{', '.join(missing)}")
    print("✅ 环境变量校验通过")

# ---------------------- 获取热榜数据 ----------------------
def get_hot_data(source):
    """获取指定数据源的热榜数据，异常时返回友好提示"""
    try:
        resp = requests.get(
            source["url"], 
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("success") and isinstance(data.get("data"), list):
            return [f"{item['index']}. {item['title']}" for item in data["data"]]
        else:
            return [f"{source['name']} 数据格式异常"]
    except requests.exceptions.Timeout:
        return [f"{source['name']} 请求超时"]
    except requests.exceptions.HTTPError as e:
        return [f"{source['name']} HTTP错误: {e.response.status_code}"]
    except Exception as e:
        print(f"❌ 获取 {source['name']} 失败: {str(e)}")
        return [f"{source['name']} 加载失败"]

# ---------------------- 生成图片（适配400*300墨水屏） ----------------------
def create_image(lines, title):
    """生成指定内容的图片，适配400*300分辨率"""
    W, H = 400, 300  # 固定墨水屏分辨率
    img = Image.new('1', (W, H), 1)  # 1位黑白图像
    draw = ImageDraw.Draw(img)
    padding = 14

    # 加载字体（优先自定义字体，失败则用默认）
    try:
        font_title = ImageFont.truetype(FONT_PATH, 26)
        font_date = ImageFont.truetype(FONT_PATH, 18)
        font_text = ImageFont.truetype(FONT_PATH, 18)
    except Exception as e:
        print(f"⚠️ 自定义字体加载失败({e})，使用默认字体")
        font_title = ImageFont.load_default(size=26)
        font_date = ImageFont.load_default(size=18)
        font_text = ImageFont.load_default(size=18)

    # 标题栏：黑底白字反显
    title_bar_h = 48
    draw.rectangle([0, 0, W, title_bar_h], fill=0)
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 绘制标题（左对齐）
    draw.text((padding, 8), title, font=font_title, fill=1)
    # 绘制日期（右对齐）
    w_date = draw.textbbox((0,0), date_str, font=font_date)[2]
    draw.text((W - w_date - padding, 12), date_str, font=font_date, fill=1)

    # 绘制边框
    border = 6
    draw.rectangle([border, border, W-border, H-border], outline=0, width=2)

    # 绘制内容（左对齐 + 下划线）
    y = 60
    line_h = 26  # 行高
    for line in lines:
        # 防止文字超出屏幕宽度
        line_display = line[:28] + "..." if len(line) > 28 else line
        draw.text((padding, y), line_display, font=font_text, fill=0)
        # 绘制下划线
        w_line = draw.textbbox((0,0), line_display, font_text)[2]
        draw.line([(padding, y+20), (padding + w_line, y+20)], fill=0, width=1)
        y += line_h
        # 防止内容超出屏幕高度
        if y + line_h > H - padding:
            break

    # 保存到字节流
    buf = BytesIO()
    img.save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf

# ---------------------- 推送图片到墨水屏 ----------------------
def push_image(buf):
    """推送图片到指定墨水屏设备"""
    if not DEVICE_ID or not API_KEY:
        print("❌ 设备ID/API Key未配置，推送失败")
        return False
    
    url = f"https://cloud.zectrix.com/open/v1/devices/{DEVICE_ID}/display/image"
    headers = {"X-API-Key": API_KEY}
    files = {"images": ("hot.png", buf, "image/png")}
    data = {"dither": True, "pageId": str(PAGE_ID)}
    
    try:
        res = requests.post(
            url, 
            headers=headers, 
            files=files, 
            data=data, 
            timeout=20
        )
        res.raise_for_status()
        print(f"✅ 推送成功，状态码：{res.status_code}")
        return True
    except requests.exceptions.HTTPError as e:
        print(f"❌ 推送失败：HTTP错误 {e.response.status_code}，响应：{e.response.text}")
    except Exception as e:
        print(f"❌ 推送异常：{str(e)}")
    return False

# ---------------------- 重置当前数据源（用于刷新最新数据） ----------------------
def reset_source_data():
    """重置全局状态，强制重新获取所有数据源的最新数据"""
    global current_source_idx, current_page, current_data
    current_source_idx = 0
    current_page = 0
    current_data = []
    print("🔄 已重置数据源状态，即将重新获取最新热榜数据")

# ---------------------- 核心任务：自动轮播三榜 ----------------------
def job():
    """核心轮播任务：分页展示 → 切换数据源 → 刷新数据"""
    global current_source_idx, current_page, current_data
    total_sources = len(SOURCES)

    # 1. 当前榜单无数据 → 加载最新数据
    if not current_data:
        source = SOURCES[current_source_idx]
        current_data = get_hot_data(source)
        current_page = 0
        print(f"\n=== 🔍 加载数据源: {source['name']}，共 {len(current_data)} 条 ===")

    # 2. 计算总分页数，判断是否需要切换数据源
    total_page = (len(current_data) + PER_PAGE - 1) // PER_PAGE
    if current_page >= total_page:
        # 当前数据源播放完毕 → 切换下一个
        current_source_idx = (current_source_idx + 1) % total_sources
        # 所有数据源轮播完毕 → 重置（强制刷新最新数据）
        if current_source_idx == 0:
            reset_source_data()
            return
        # 切换到下一个数据源，加载数据
        current_data = []
        current_page = 0
        print(f"\n▶ 切换到下一个数据源：{SOURCES[current_source_idx]['name']}")
        return

    # 3. 截取当前页数据
    start = current_page * PER_PAGE
    end = start + PER_PAGE
    page_lines = current_data[start:end]
    title = SOURCES[current_source_idx]["name"]
    print(f"📄 {title} 第 {current_page+1}/{total_page} 页")

    # 4. 生成并推送图片
    img_buf = create_image(page_lines, title)
    push_image(img_buf)

    # 5. 准备下一页
    current_page += 1

# ---------------------- 主程序入口 ----------------------
if __name__ == "__main__":
    try:
        # 前置校验
        check_env()
        print("🚀 三榜轮播推送服务已启动")
        print(f"🔧 配置：每页{PER_PAGE}条 | 停留{INTERVAL_MINUTES}分钟 | 数据源：{[s['name'] for s in SOURCES]}")
        
        # 立即执行一次任务
        job()
        
        # 定时任务（每X分钟执行）
        schedule.every(INTERVAL_MINUTES).minutes.do(job)
        
        # 持续运行
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 服务已手动停止")
    except Exception as e:
        print(f"\n💥 服务启动失败：{str(e)}")
        exit(1)
