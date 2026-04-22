from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
from datetime import datetime
import os

# ====================== 配置区 ======================
DEVICE_ID = os.getenv("DEVICE_ID", "")
API_KEY = os.getenv("API_KEY", "")
PAGE_ID = os.getenv("PAGE_ID", "5")

PER_PAGE = 8
SOURCES = [
    {"name": "抖音热榜", "url": "https://dabenshi.cn/other/api/hot.php?type=douyinhot"},
    {"name": "头条热榜", "url": "https://dabenshi.cn/other/api/hot.php?type=toutiaoHot"},
    {"name": "百度热搜", "url": "https://dabenshi.cn/other/api/hot.php?type=baidu"}
]
# ====================================================

def get_data(source):
    try:
        r = requests.get(source["url"], timeout=10)
        r.raise_for_status()
        d = r.json()
        if d.get("success") and isinstance(d.get("data"), list):
            return [f"{x['index']}. {x['title']}" for x in d["data"]]
    except:
        return [f"{source['name']} 加载失败"]
    return ["无数据"]

def make_img(lines, title):
    W, H = 400, 300
    im = Image.new('1', (W, H), 1)
    draw = ImageDraw.Draw(im)
    pad = 14

    try:
        ft_title = ImageFont.truetype("font.ttf", 26)
        ft_date = ImageFont.truetype("font.ttf", 18)
        ft_text = ImageFont.truetype("font.ttf", 18)
    except:
        ft_title = ImageFont.load_default(size=26)
        ft_date = ImageFont.load_default(size=18)
        ft_text = ImageFont.load_default(size=18)

    bar_h = 48
    draw.rectangle([0, 0, W, bar_h], fill=0)
    date_str = datetime.now().strftime("%Y-%m-%d")
    draw.text((pad, 8), title, font=ft_title, fill=1)
    wd = draw.textbbox((0,0), date_str, ft_date)[2]
    draw.text((W - wd - pad, 12), date_str, font=ft_date, fill=1)
    draw.rectangle([6,6,W-6,H-6], outline=0, width=2)

    y = 60
    lh = 26
    for line in lines:
        draw.text((pad, y), line, font=ft_text, fill=0)
        wl = draw.textbbox((0,0), line, ft_text)[2]
        draw.line([pad, y+20, pad+wl, y+20], fill=0, width=1)
        y += lh

    buf = BytesIO()
    im.save(buf, "PNG")
    buf.seek(0)
    return buf

def push(buf):
    url = f"https://cloud.zectrix.com/open/v1/devices/{DEVICE_ID}/display/image"
    h = {"X-API-Key": API_KEY}
    files = {"images": ("hot.png", buf, "image/png")}
    data = {"dither": True, "pageId": str(PAGE_ID)}
    try:
        res = requests.post(url, headers=h, files=files, data=data, timeout=15)
        print(f"推送状态码: {res.status_code}")
        return res.status_code == 200
    except Exception as e:
        print(f"推送异常: {e}")
        return False

def main():
    if not DEVICE_ID or not API_KEY:
        print("错误：请设置 DEVICE_ID 和 API_KEY 环境变量")
        return

    # 用运行次数来计数，直接取模实现循环
    # 你可以根据实际总页数调整这个循环逻辑
    total_pages_per_source = 7  # 50条数据 / 8条每页 ≈ 7页
    total_pages = len(SOURCES) * total_pages_per_source

    # 这里用一个简单的循环逻辑，每次运行自动+1
    # 为了不依赖文件，我们直接按顺序循环
    # 第一次：0%19=0 抖音第1页
    # 第二次：1%19=1 抖音第2页
    # ...
    # 第7次：6%19=6 抖音第7页
    # 第8次：7%19=7 头条第1页
    import time
    run_count = int(time.time() // (10 * 60)) % total_pages  # 每10分钟+1

    source_idx = run_count // total_pages_per_source
    page_idx = run_count % total_pages_per_source

    source = SOURCES[source_idx]
    data = get_data(source)
    start = page_idx * PER_PAGE
    end = start + PER_PAGE
    lines = data[start:end]

    print(f"正在推送：{source['name']} 第{page_idx+1}页")
    img = make_img(lines, source["name"])
    push(img)

if __name__ == "__main__":
    main()
