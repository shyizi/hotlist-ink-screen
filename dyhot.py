# dyhot.py
import os
import sys
import logging
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
from datetime import datetime
import time
import schedule
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ====================== 配置区（优先使用环境变量）======================
DEVICE_ID = os.getenv('DEVICE_ID', '默认设备ID')
API_KEY = os.getenv('API_KEY', '默认API密钥')
PAGE_ID = int(os.getenv('PAGE_ID', '5'))
PER_PAGE = int(os.getenv("PER_PAGE", "8"))
INTERVAL_MINUTES = int(os.getenv("INTERVAL_MINUTES", "5"))

# 三大热榜接口
SOURCES = [
    {"name": "抖音热榜", "url": "https://dabenshi.cn/other/api/hot.php?type=douyinhot"},
    {"name": "头条热榜", "url": "https://dabenshi.cn/other/api/hot.php?type=toutiaoHot"},
    {"name": "百度热搜", "url": "https://dabenshi.cn/other/api/hot.php?type=baidu"}
]

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hotboard.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 全局状态
current_source_idx = 0
current_page = 0
current_data = []

# ---------------------- 获取热榜数据 ----------------------
def get_hot_data(source):
    """获取热榜数据，带重试机制"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"正在获取 {source['name']}... (尝试 {attempt+1}/{max_retries})")
            resp = requests.get(source["url"], timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("success") and isinstance(data.get("data"), list):
                items = data["data"]
                # 限制数据量，避免过多
                items = items[:50]
                result = []
                for item in items:
                    title = item.get('title', '无标题')
                    index = item.get('index', '')
                    if index:
                        result.append(f"{index}. {title}")
                    else:
                        result.append(f"• {title}")
                logger.info(f"成功获取 {source['name']}，共 {len(result)} 条")
                return result
            else:
                logger.warning(f"{source['name']} 返回数据格式异常")
                
        except requests.RequestException as e:
            logger.error(f"获取 {source['name']} 失败 (尝试 {attempt+1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                
    logger.error(f"{source['name']} 所有重试均失败")
    return [f"{source['name']} 加载失败"]

# ---------------------- 生成图片 ----------------------
def create_image(lines, title):
    """生成图片，带字体回退机制"""
    W, H = 400, 300
    img = Image.new('1', (W, H), 1)
    draw = ImageDraw.Draw(img)
    padding = 14

    # 字体加载（支持多种字体路径）
    font_paths = [
        "font.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "C:\\Windows\\Fonts\\simhei.ttf"
    ]
    
    font_title = None
    font_date = None
    font_text = None
    
    for font_path in font_paths:
      try:
    font = ImageFont.truetype("font.ttf", 26)
    except:
       font = ImageFont.load_default()
    


    # 标题栏（反显）
    title_bar_h = 48
    draw.rectangle([0, 0, W, title_bar_h], fill=0)
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 标题（最多12个字符）
    if len(title) > 12:
        title = title[:10] + ".."
    draw.text((padding, 8), title, font=font_title, fill=1)
    
    # 日期
    try:
        w_date = draw.textbbox((0, 0), date_str, font=font_date)[2]
    except:
        w_date = len(date_str) * 12
    draw.text((W - w_date - padding, 12), date_str, font=font_date, fill=1)

    # 边框
    border = 6
    draw.rectangle([border, border, W-border, H-border], outline=0, width=2)

    # 内容（限制显示条数）
    max_lines = (H - 70) // 26
    lines = lines[:max_lines]
    
    y = 60
    line_h = 26
    for line in lines:
        # 每行最多20个字符
        if len(line) > 20:
            line = line[:18] + ".."
        draw.text((padding, y), line, font=font_text, fill=0)
        try:
            w_line = draw.textbbox((0, 0), line, font=font_text)[2]
        except:
            w_line = len(line) * 12
        draw.line([(padding, y+20), (padding + w_line, y+20)], fill=0, width=1)
        y += line_h

    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf

# ---------------------- 推送图片 ----------------------
def push_image(buf):
    """推送图片到设备"""
    url = f"https://cloud.zectrix.com/open/v1/devices/{DEVICE_ID}/display/image"
    headers = {"X-API-Key": API_KEY}
    files = {"images": ("hot.png", buf, "image/png")}
    data = {"dither": True, "pageId": str(PAGE_ID)}
    
    try:
        res = requests.post(url, headers=headers, files=files, data=data, timeout=20)
        if res.status_code == 200:
            logger.info("推送成功")
            return True
        else:
            logger.error(f"推送失败，状态码: {res.status_code}, 响应: {res.text}")
            return False
    except Exception as e:
        logger.error(f"推送异常: {e}")
        return False

# ---------------------- 核心任务 ----------------------
def job():
    """定时任务主函数"""
    global current_source_idx, current_page, current_data

    total_sources = len(SOURCES)

    # 加载数据
    if not current_data:
        source = SOURCES[current_source_idx]
        current_data = get_hot_data(source)
        current_page = 0
        if not current_data:
            logger.error(f"无法加载 {source['name']} 数据")
            return

    # 分页
    total_page = (len(current_data) + PER_PAGE - 1) // PER_PAGE
    if total_page == 0:
        total_page = 1
        
    if current_page >= total_page:
        # 切换到下一个榜单
        current_source_idx = (current_source_idx + 1) % total_sources
        current_data = []
        current_page = 0
        logger.info(f"切换到下一个榜单: {SOURCES[current_source_idx]['name']}")
        return

    # 生成当前页
    start = current_page * PER_PAGE
    end = start + PER_PAGE
    page_lines = current_data[start:end]
    title = SOURCES[current_source_idx]["name"]
    
    logger.info(f"处理: {title} 第 {current_page+1}/{total_page} 页，显示 {len(page_lines)} 条")
    
    # 生成并推送
    img_buf = create_image(page_lines, title)
    push_image(img_buf)

    # 下一页
    current_page += 1

# ---------------------- 健康检查 ----------------------
def health_check():
    """健康检查端点（用于Docker/监控）"""
    return {
        "status": "running",
        "current_source": SOURCES[current_source_idx]["name"],
        "current_page": current_page,
        "data_count": len(current_data),
        "timestamp": datetime.now().isoformat()
    }

# ---------------------- 主程序 ----------------------
def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("三榜轮播推送服务启动")
    logger.info(f"设备ID: {DEVICE_ID}")
    logger.info(f"页面ID: {PAGE_ID}")
    logger.info(f"每页显示: {PER_PAGE} 条")
    logger.info(f"轮播间隔: {INTERVAL_MINUTES} 分钟")
    logger.info("榜单来源: 抖音 → 头条 → 百度")
    logger.info("=" * 50)
    
    # 立即执行一次
    job()
    
    # 定时任务
    schedule.every(INTERVAL_MINUTES).minutes.do(job)
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("服务已停止")

if __name__ == "__main__":
    main()
