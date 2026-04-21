from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
from datetime import datetime
import time
import schedule

# ====================== 【配置区】======================
DEVICE_ID = "20:6E:F1:B5:3F:6C"
API_KEY   = "zt_68e5c0e02a9fb328d5f3faf75abbbd46"
PAGE_ID   = 5
PER_PAGE  = 8          # 一屏最多8条
INTERVAL_MINUTES = 5  # 5分钟翻一页
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

# ---------------------- 获取热榜数据 ----------------------
def get_hot_data(source):
    try:
        resp = requests.get(source["url"], timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("success") and isinstance(data.get("data"), list):
            return [f"{item['index']}. {item['title']}" for item in data["data"]]
    except Exception as e:
        print(f"获取 {source['name']} 失败:", e)
    return [f"{source['name']} 加载失败"]

# ---------------------- 生成图片（标题反显） ----------------------
def create_image(lines, title):
    W, H = 400, 300
    img = Image.new('1', (W, H), 1)
    draw = ImageDraw.Draw(img)
    padding = 14

    # 字体
    try:
        font_title = ImageFont.truetype("simhei.ttf", 26)
        font_date  = ImageFont.truetype("simhei.ttf", 18)
        font_text  = ImageFont.truetype("simhei.ttf", 18)
    except:
        font_title = ImageFont.load_default(size=26)
        font_date  = ImageFont.load_default(size=18)
        font_text  = ImageFont.load_default(size=18)

    # ========== 标题反显：黑底白字 ==========
    title_bar_h = 48
    draw.rectangle([0, 0, W, title_bar_h], fill=0)
    date_str = datetime.now().strftime("%Y-%m-%d")

    draw.text((padding, 8), title, font=font_title, fill=1)  # 标题白字
    w_date = draw.textbbox((0,0), date_str, font=font_date)[2]
    draw.text((W - w_date - padding, 12), date_str, font=font_date, fill=1) # 日期白字

    # 边框
    border = 6
    draw.rectangle([border, border, W-border, H-border], outline=0, width=2)

    # 内容左对齐 + 下划线
    y = 60
    line_h = 26
    for line in lines:
        draw.text((padding, y), line, font=font_text, fill=0)
        w_line = draw.textbbox((0,0), line, font=font_text)[2]
        draw.line([(padding, y+20), (padding + w_line, y+20)], fill=0, width=1)
        y += line_h

    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf

# ---------------------- 推送图片 ----------------------
def push_image(buf):
    url = f"https://cloud.zectrix.com/open/v1/devices/{DEVICE_ID}/display/image"
    headers = {"X-API-Key": API_KEY}
    files = {"images": ("hot.png", buf, "image/png")}
    data = {"dither": True, "pageId": str(PAGE_ID)}
    try:
        res = requests.post(url, headers=headers, files=files, data=data, timeout=20)
        print(f"推送状态：{res.status_code}")
        return res.status_code == 200
    except Exception as e:
        print("推送异常：", e)
        return False

# ---------------------- 核心任务：自动轮播三榜 ----------------------
def job():
    global current_source_idx, current_page, current_data

    total_sources = len(SOURCES)

    # 1. 当前榜单无数据 → 加载
    if not current_data:
        source = SOURCES[current_source_idx]
        current_data = get_hot_data(source)
        current_page = 0
        print(f"\n=== 加载: {source['name']}，共 {len(current_data)} 条 ===")

    # 2. 分页
    total_page = (len(current_data) + PER_PAGE - 1) // PER_PAGE
    if current_page >= total_page:
        # 当前榜单播完 → 切下一个榜单
        current_source_idx = (current_source_idx + 1) % total_sources
        current_data = []
        current_page = 0
        print("▶ 切换到下一个榜单")
        return

    # 3. 取当前页
    start = current_page * PER_PAGE
    end = start + PER_PAGE
    page_lines = current_data[start:end]
    title = SOURCES[current_source_idx]["name"]
    print(f"→ {title} 第{current_page+1}/{total_page}页")

    # 4. 生成推送
    img_buf = create_image(page_lines, title)
    push_image(img_buf)

    # 5. 下一页
    current_page += 1

# ---------------------- 主程序 ----------------------
if __name__ == "__main__":
    print("三榜轮播推送服务已启动：抖音 → 头条 → 百度，循环播放")
    job()
    schedule.every(INTERVAL_MINUTES).minutes.do(job)
    while True:
        schedule.run_pending()
        time.sleep(1)
