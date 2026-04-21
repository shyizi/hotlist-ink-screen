# 抖音 / 头条 / 百度 热榜自动推送墨水屏
自动获取三大平台热榜，分页推送到电子墨水屏（Zectrix）

## 功能
- 抖音热榜
- 头条热榜
- 百度热搜
- 自动分页（8条/页）
- 每10分钟自动翻页
- 标题反显、日期右对齐、内容带下划线
- 400×300 黑白图

## 使用方法
1. 安装依赖
   pip install pillow requests schedule
2. 运行
   python dyhot.py

## 配置
可在代码内修改：
- 设备ID
- API Key
- 推送页码
- 每页条数
- 推送间隔

进入你的仓库 → Settings →
Secrets and variables → 
Actions → 
New repository secret
添加三个：
- DEVICE_ID  你的设备MAC码
- API_KEY  AI便贴贴网上申请的API
- PAGE_ID  推送到第几页
