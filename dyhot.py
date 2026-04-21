from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
from datetime import datetime
import os

# ====================== 配置区 ======================
DEVICE_ID = os.getenv("DEVICE_ID", "")
API_KEY = os.getenv("API_KEY", "")
PAGE_ID = os.getenv("PAGE_ID", "5")

PER_PAGE = 8  # 已改为 8 条/页
SOURCES = [
    {"name": "抖音热榜", "url": "https://dabenshi.cn/other/api/hot.php?type=douyinhot"},
    {"name": "头条热榜", "url": "https://dabenshi.cn/other/api/hot.php?type=toutiaoHot"},
    {"name": "百度热搜", "url": "https://dabenshi.cn/other/api/hot.php?type=baidu"}
]

STATE_FILE = "state.txt"
# ====================================================

# 读取上一次的进度
def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            src_idx, p_idx = f.read().strip().split(",")
            return int(src_idx), int(p_idx)
    except:
        return 0, 0

# 保存进度
def save_state(src, page):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(f"{src},{page}")

# 获取热榜数据
def get_data(source):
    try:
        r = requests.get(source["url"], timeout=10)
        r.raise_for_status()
        d = r.json()
        if d.get("success") and isinstance(d.get("data"), list):
            return [f"{x['index']}. {x['title']}" for x in d["data"]]
    except:
        return [f"{source['name']} 获取失败"]
    return ["无数据"]

# 生成图片
def make_img(lines, title):
    W, H = 400, 300
    im = Image.new('1', (W, H), 1)
    draw = ImageDraw.Draw(im)
    pad = 14

    try:
        ft_title = ImageFont.truetype("simhei.ttf", 26)
        ft_date = ImageFont.truetype("simhei.ttf", 18)
        ft_text = ImageFont.truetype("simhei.ttf", 18)
    except:
        ft_title = ImageFont.load_default(size=26)
        ft_date = ImageFont.load_default(size=18)
        ft_text = ImageFont.load_default(size=18)

    # 标题反显
    bar_h = 48
    draw.rectangle([0, 0, W, bar_h], fill=0)
    date_str = datetime.now().strftime("%Y-%m-%d")
    draw.text((pad, 8), title, font=ft_title, fill=1)
    wd = draw.textbbox((0,0), date_str, ft_date)[2]
    draw.text((W - wd - pad, 12), date_str, font=ft_date, fill=1)

    # 边框
    draw.rectangle([6,6,W-6,H-6], outline=0, width=2)

    # 内容 + 下划线
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

# 推送
def push(buf):
    url = f"https://cloud.zectrix.com/open/v1/devices/{DEVICE_ID}/display/image"
    h = {"X-API-Key": API_KEY}
    files = {"images": ("hot.png", buf, "image/png")}
    data = {"dither": True, "pageId": str(PAGE_ID)}
    try:
        res = requests.post(url, headers=h, files=files, data=data, timeout=15)
        print(f"推送结果: {res.status_code}")
        return res.status_code == 200
    except Exception as e:
        print("推送失败", e)
        return False

# 主函数（运行一次，推一页）
def main():
    if not DEVICE_ID or not API_KEY:
        print("请设置环境变量")
        return

    src_idx, page_idx = load_state()
    source = SOURCES[src_idx]
    data = get_data(source)
    total_page = (len(data) + PER_PAGE -1) // PER_PAGE

    # 越界 = 切下一个榜单
    if page_idx >= total_page:
        src_idx = (src_idx +1) % len(SOURCES)
        page_idx = 0
        source = SOURCES[src_idx]
        data = get_data(source)
        total_page = (len(data) + PER_PAGE -1) // PER_PAGE

    # 当前页内容
    s = page_idx * PER_PAGE
    e = s + PER_PAGE
    lines = data[s:e]
    print(f"▶ {source['name']} 第{page_idx+1}/{total_page}页")

    # 推送
    img = make_img(lines, source["name"])
    push(img)

    # 下一页
    page_idx +=1
    save_state(src_idx, page_idx)

if __name__ == "__main__":
    main()
