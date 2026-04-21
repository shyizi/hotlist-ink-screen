import requests
from PIL import Image, ImageDraw, ImageFont
import schedule
import time
import datetime
import os

# ========== 配置项（请替换为自己的信息） ==========
DEVICE_ID = os.getenv("DEVICE_ID", "你的设备MAC码")  # 优先从环境变量读取
API_KEY = os.getenv("API_KEY", "你的AI便贴贴API")
PAGE_ID = int(os.getenv("PAGE_ID", 1))  # 推送页码
PER_PAGE = 8  # 每页显示条数
INTERVAL = 10  # 翻页间隔（分钟）
SCREEN_SIZE = (400, 300)  # 墨水屏分辨率
FONT_PATH = "font.ttf"  # 字体文件路径

# ========== 热榜获取函数（修复接口兼容性） ==========
def get_douyin_hot():
    """获取抖音热榜"""
    try:
        url = "https://www.douyin.com/aweme/v1/hot/search/list/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        hot_list = [item["word"] for item in data.get("data", {}).get("word_list", [])[:20]]
        return ["抖音热榜"] + hot_list
    except Exception as e:
        print(f"获取抖音热榜失败: {e}")
        return ["抖音热榜", "获取失败"]

def get_toutiao_hot():
    """获取头条热榜"""
    try:
        url = "https://www.toutiao.com/hot-event/hot-board/?origin=1"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        hot_list = [item["Title"] for item in data.get("data", {}).get("board", [])[:20]]
        return ["头条热榜"] + hot_list
    except Exception as e:
        print(f"获取头条热榜失败: {e}")
        return ["头条热榜", "获取失败"]

def get_baidu_hot():
    """获取百度热搜"""
    try:
        url = "https://top.baidu.com/board?tab=realtimehot"
        resp = requests.get(url, timeout=10)
        from bs4 import BeautifulSoup  # 需额外安装: pip install beautifulsoup4
        soup = BeautifulSoup(resp.text, "html.parser")
        hot_list = [item.text.strip() for item in soup.select(".c-single-text-ellipsis")[:20]]
        return ["百度热搜"] + hot_list
    except Exception as e:
        print(f"获取百度热搜失败: {e}")
        return ["百度热搜", "获取失败"]

# ========== 图片生成函数（修复样式/分页） ==========
def generate_image(content_list, page_num=1):
    """生成墨水屏图片"""
    # 计算分页
    start = (page_num - 1) * PER_PAGE
    end = start + PER_PAGE
    page_content = content_list[start:end]
    
    # 创建画布
    img = Image.new("1", SCREEN_SIZE, 255)  # 1: 黑白模式, 255: 白色背景
    draw = ImageDraw.Draw(img)
    
    # 加载字体（兼容不同字体大小）
    try:
        font_title = ImageFont.truetype(FONT_PATH, 24)
        font_content = ImageFont.truetype(FONT_PATH, 18)
    except:
        font_title = ImageFont.load_default(size=24)
        font_content = ImageFont.load_default(size=18)
    
    # 绘制标题（反显）
    title = page_content[0] if page_content else "无数据"
    title_box = draw.textbbox((0, 0), title, font=font_title)
    title_w = title_box[2] - title_box[0]
    draw.rectangle((0, 0, title_w + 20, 30), fill=0)  # 黑色背景
    draw.text((10, 0), title, font=font_title, fill=255)  # 白色文字
    
    # 绘制日期（右对齐）
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    date_box = draw.textbbox((0, 0), date_str, font=font_content)
    date_w = date_box[2] - date_box[0]
    draw.text((SCREEN_SIZE[0] - date_w - 10, 0), date_str, font=font_content, fill=0)
    
    # 绘制内容（带下划线）
    y = 40
    for i, content in enumerate(page_content[1:], 1):
        # 绘制文字
        draw.text((10, y), f"{i}. {content}", font=font_content, fill=0)
        # 绘制下划线
        text_box = draw.textbbox((10, y), f"{i}. {content}", font=font_content)
        draw.line((10, y + text_box[3] - text_box[1] + 2, text_box[2], y + text_box[3] - text_box[1] + 2), fill=0, width=1)
        y += 30  # 行间距
    
    # 保存图片
    img.save("hot_screen.png")
    return "hot_screen.png"

# ========== 推送图片到墨水屏（修复API调用） ==========
def push_to_screen(image_path):
    """推送图片到Zectrix墨水屏"""
    if not DEVICE_ID or not API_KEY:
        print("请配置DEVICE_ID和API_KEY")
        return False
    
    try:
        url = f"https://api.zectrix.com/v1/device/{DEVICE_ID}/push"  # 确认API地址是否正确
        files = {"image": open(image_path, "rb")}
        data = {
            "api_key": API_KEY,
            "page_id": PAGE_ID,
            "refresh": 1
        }
        resp = requests.post(url, files=files, data=data, timeout=15)
        if resp.status_code == 200:
            print(f"推送成功: {resp.json()}")
            return True
        else:
            print(f"推送失败: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        print(f"推送异常: {e}")
        return False

# ========== 主逻辑（修复分页/定时） ==========
def main():
    """主执行函数"""
    # 合并所有热榜
    all_hot = []
    all_hot.extend(get_douyin_hot())
    all_hot.extend(get_toutiao_hot())
    all_hot.extend(get_baidu_hot())
    
    # 生成并推送图片
    total_pages = max(1, len(all_hot) // PER_PAGE + (1 if len(all_hot) % PER_PAGE else 0))
    current_page = 1
    
    def run_push():
        nonlocal current_page
        print(f"\n=== 推送第 {current_page}/{total_pages} 页 ===")
        img_path = generate_image(all_hot, current_page)
        push_to_screen(img_path)
        
        # 翻页（循环）
        current_page = current_page + 1 if current_page < total_pages else 1
    
    # 立即执行一次
    run_push()
    
    # 定时任务
    schedule.every(INTERVAL).minutes.do(run_push)
    print(f"\n定时任务已启动，每{INTERVAL}分钟翻页一次...")
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    # 检查依赖（补充缺失的依赖）
    try:
        import bs4
    except ImportError:
        print("安装缺失依赖: beautifulsoup4")
        os.system("pip install beautifulsoup4")
    
    main()
