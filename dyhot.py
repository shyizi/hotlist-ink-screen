from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
from datetime import datetime
import time
import schedule
import os

# ====================== 【配置区：从环境变量读取，不上传GitHub】 ======================
DEVICE_ID = os.getenv("DEVICE_ID", "")
API_KEY = os.getenv("API_KEY", "")
PAGE_ID = os.getenv("PAGE_ID", "5")

PER_PAGE = 7
INTERVAL_MINUTES = 10

SOURCES = [
    {"name": "抖音热榜", "url": "https://dabenshi.cn/other/api/hot.php?type=douyinhot"},
    {"name": "头条热榜", "url": "https://dabenshi.cn/other/api/hot.php?type=toutiaoHot"},
    {"name": "百度热搜", "url": "https://dabenshi.cn/other/api/hot.php?type=baidu"}
]
# ====================================================================================

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

    try:
        font_title = ImageFont.truetype("simhei.ttf", 26)
        font_date = ImageFont.truetype("simhei.ttf", 18)
        font_text = ImageFont.truetype("simhei.ttf", 18)
    except:
        font_title = ImageFont.load_default(size=26)
        font_date = ImageFont.load_default(size=18)
        font_text = ImageFont.load_default(size=18)

    title_bar_h = 48
    draw.rectangle([0, 0, W, title_bar_h], fill=0)
    date_str = datetime.now().strftime("%Y-%m-%d")

    draw.text((padding, 8), title, font=font_title, fill=1)
    w_date = draw.textbbox((0, 0), date_str, font=font_date)[2]
    draw.text((W - w_date - padding, 12), date_str, font=font_date, fill=1)

    border = 6
    draw.rectangle([border, border, W-border, H-border], outline=0, width=2)

    y = 60
    line_h = 26
    for line in lines:
        draw.text((padding, y), line, font=font_text, fill=0)
        w_line = draw.textbbox((0, 0), line, font=font_text)[2]
        draw.line([(padding, y + 20), (padding + w_line, y + 20)], fill=0, width=1)
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

# ---------------------- 核心任务 ----------------------
def job():
    global current_source_idx, current_page, current_data

    if not DEVICE_ID or not API_KEY:
        print("错误：请设置 DEVICE_ID 和 API_KEY 环境变量！")
        return

    total_sources = len(SOURCES)
    if not current_data:
        source = SOURCES[current_source_idx]
        current_data = get_hot_data(source)
        current_page = 0
        print(f"\n=== 加载: {source['name']}，共 {len(current_data)} 条 ===")

    total_page = (len(current_data) + PER_PAGE - 1) // PER_PAGE
    if current_page >= total_page:
        current_source_idx = (current_source_idx + 1) % total_sources
        current_data = []
        current_page = 0
        print("▶ 切换到下一个榜单")
        return

    start = current_page * PER_PAGE
    end = start + PER_PAGE
    page_lines = current_data[start:end]
    title = SOURCES[current_source_idx]["name"]
    print(f"→ {title} 第{current_page+1}/{total_page}页")

    img_buf = create_image(page_lines, title)
    push_image(img_buf)
    current_page += 1

# ---------------------- 主程序 ----------------------
if __name__ == "__main__":
    print("三榜轮播推送服务已启动")
    job()
    schedule.every(INTERVAL_MINUTES).minutes.do(job)
    while True:
        schedule.run_pending()
        time.sleep(1)
