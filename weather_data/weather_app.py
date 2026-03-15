#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时天气获取程序
功能：根据城市名称获取实时天气，支持定时任务和多种输出方式
作者：AI Assistant
日期：2026-03-15
"""

import requests
import json
import time
import os
import schedule
from datetime import datetime
from urllib.parse import quote


# ==================== 配置区域 ====================
class Config:
    """程序配置类，集中管理所有可配置参数"""
    
    # 目标城市（支持中文，如"北京"、"上海"）
    CITY = "北京"
    
    # 定时规则设置
    # 可选模式：
    # 1. "daily_at" - 每天固定时间，如 "08:00" 表示每天早上8点
    # 2. "interval_hours" - 每隔N小时执行一次
    # 3. "interval_minutes" - 每隔N分钟执行一次
    SCHEDULE_MODE = "daily_at"  # 默认每天早上执行
    SCHEDULE_TIME = "08:00"     # 当模式为daily_at时生效
    INTERVAL_HOURS = 2          # 当模式为interval_hours时生效
    INTERVAL_MINUTES = 30       # 当模式为interval_minutes时生效
    
    # 输出设置
    PRINT_TO_CONSOLE = True     # 是否打印到控制台
    SAVE_TO_FILE = True         # 是否保存到文件
    OUTPUT_DIR = "weather_data" # 文件保存目录
    
    # 网络设置
    MAX_RETRIES = 3             # 最大重试次数
    RETRY_DELAY = 2             # 重试间隔（秒）
    REQUEST_TIMEOUT = 10        # 请求超时时间（秒）


# ==================== 天气代码映射 ====================
# WMO Weather interpretation codes (WW)
WEATHER_CODES = {
    0: "晴",
    1: "多云", 2: "多云",
    3: "阴天",
    45: "雾", 48: "雾凇",
    51: "毛毛雨", 53: "中度毛毛雨", 55: "密集毛毛雨",
    56: "冻毛毛雨", 57: "密集冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "大冻雨",
    71: "小雪", 73: "中雪", 75: "大雪",
    77: "雪粒",
    80: "小阵雨", 81: "中阵雨", 82: "大阵雨",
    85: "小阵雪", 86: "大阵雪",
    95: "雷雨", 96: "雷雨伴小冰雹", 99: "雷雨伴大冰雹"
}


def get_weather_description(code):
    """
    根据天气代码获取中文描述
    
    参数:
        code: WMO天气代码
    返回:
        中文天气描述
    """
    return WEATHER_CODES.get(code, "未知天气")


def get_city_coordinates(city_name):
    """
    获取城市的经纬度坐标
    
    使用Open-Meteo的地理编码API，将中文城市名转换为经纬度
    
    参数:
        city_name: 城市中文名（如"北京"）
    返回:
        tuple: (纬度, 经度, 城市名) 或 None（如果城市不存在）
    """
    try:
        # 对城市名进行URL编码，支持中文
        encoded_city = quote(city_name)
        
        # Open-Meteo地理编码API
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_city}&count=1&language=zh&format=json"
        
        response = requests.get(url, timeout=Config.REQUEST_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        
        # 检查是否找到城市
        if "results" not in data or len(data["results"]) == 0:
            print(f"❌ 错误：未找到城市'{city_name}'，请检查城市名称是否正确")
            return None
        
        result = data["results"][0]
        latitude = result["latitude"]
        longitude = result["longitude"]
        display_name = result.get("name", city_name)
        
        return (latitude, longitude, display_name)
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络错误：获取城市坐标失败 - {e}")
        return None
    except Exception as e:
        print(f"❌ 错误：{e}")
        return None


def fetch_weather_data(latitude, longitude, city_name):
    """
    获取指定坐标的天气数据
    
    使用Open-Meteo天气API，支持自动重试机制
    
    参数:
        latitude: 纬度
        longitude: 经度
        city_name: 城市名称（用于错误提示）
    返回:
        dict: 天气数据字典 或 None（获取失败）
    """
    # Open-Meteo天气API（免费，无需注册）
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={latitude}&longitude={longitude}"
        f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"
        f"&timezone=auto"
    )
    
    # 重试机制
    for attempt in range(1, Config.MAX_RETRIES + 1):
        try:
            print(f"🌐 正在获取天气数据...（第{attempt}次尝试）")
            response = requests.get(url, timeout=Config.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            current = data["current"]
            
            # 构建天气数据字典
            weather_data = {
                "city": city_name,
                "temperature": current["temperature_2m"],           # 温度
                "humidity": current["relative_humidity_2m"],        # 湿度
                "apparent_temp": current["apparent_temperature"],   # 体感温度
                "weather_code": current["weather_code"],            # 天气代码
                "weather_desc": get_weather_description(current["weather_code"]),
                "wind_speed": current["wind_speed_10m"],            # 风速
                "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            return weather_data
            
        except requests.exceptions.Timeout:
            print(f"⏱️ 请求超时，{Config.RETRY_DELAY}秒后重试...")
            if attempt < Config.MAX_RETRIES:
                time.sleep(Config.RETRY_DELAY)
            
        except requests.exceptions.ConnectionError:
            print(f"🔌 网络连接错误，{Config.RETRY_DELAY}秒后重试...")
            if attempt < Config.MAX_RETRIES:
                time.sleep(Config.RETRY_DELAY)
            
        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP错误：{e}")
            return None
            
        except Exception as e:
            print(f"❌ 获取天气数据时出错：{e}")
            return None
    
    print(f"❌ 获取天气数据失败，已重试{Config.MAX_RETRIES}次")
    return None


def format_weather_output(weather_data):
    """
    格式化天气信息为易读的字符串
    
    参数:
        weather_data: 天气数据字典
    返回:
        格式化后的字符串
    """
    output = []
    output.append("=" * 50)
    output.append(f"🌍 城市：{weather_data['city']}")
    output.append(f"🕐 获取时间：{weather_data['fetch_time']}")
    output.append("-" * 50)
    output.append(f"🌡️ 温度：{weather_data['temperature']}°C")
    output.append(f"🌤️ 天气：{weather_data['weather_desc']}")
    output.append(f"💨 风速：{weather_data['wind_speed']} km/h")
    output.append(f"💧 湿度：{weather_data['humidity']}%")
    output.append(f"🌡️ 体感温度：{weather_data['apparent_temp']}°C")
    output.append("=" * 50)
    
    return "\n".join(output)


def save_weather_to_file(weather_data):
    """
    将天气数据保存到本地文件
    
    文件名格式：YYYYMMDD_城市名天气.txt
    
    参数:
        weather_data: 天气数据字典
    返回:
        bool: 保存是否成功
    """
    try:
        # 创建输出目录（如果不存在）
        if not os.path.exists(Config.OUTPUT_DIR):
            os.makedirs(Config.OUTPUT_DIR)
            print(f"📁 创建目录：{Config.OUTPUT_DIR}")
        
        # 生成文件名：20260315_北京天气.txt
        date_str = datetime.now().strftime("%Y%m%d")
        city = weather_data['city']
        filename = f"{date_str}_{city}天气.txt"
        filepath = os.path.join(Config.OUTPUT_DIR, filename)
        
        # 写入文件（追加模式，同一天的数据会追加到同一文件）
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(format_weather_output(weather_data))
            f.write("\n\n")
        
        print(f"💾 天气数据已保存到：{filepath}")
        return True
        
    except Exception as e:
        print(f"❌ 保存文件时出错：{e}")
        return False


def get_weather(city_name=None):
    """
    获取天气的主函数（支持单次获取）
    
    参数:
        city_name: 城市名，如果为None则使用配置中的城市
    返回:
        dict: 天气数据 或 None
    """
    if city_name is None:
        city_name = Config.CITY
    
    print(f"\n🔍 正在查询城市：{city_name}")
    
    # 获取城市坐标
    coords = get_city_coordinates(city_name)
    if coords is None:
        return None
    
    latitude, longitude, display_name = coords
    print(f"📍 找到城市：{display_name}（坐标：{latitude:.2f}, {longitude:.2f}）")
    
    # 获取天气数据
    weather_data = fetch_weather_data(latitude, longitude, display_name)
    if weather_data is None:
        return None
    
    # 输出到控制台
    if Config.PRINT_TO_CONSOLE:
        print("\n" + format_weather_output(weather_data))
    
    # 保存到文件
    if Config.SAVE_TO_FILE:
        save_weather_to_file(weather_data)
    
    return weather_data


def scheduled_job():
    """
    定时任务执行的函数
    
    这是schedule库调用的入口函数
    """
    print(f"\n⏰ 定时任务触发时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    get_weather()


def setup_schedule():
    """
    设置定时任务
    
    根据Config中的配置设置不同的定时规则
    """
    mode = Config.SCHEDULE_MODE
    
    if mode == "daily_at":
        # 每天固定时间执行
        schedule.every().day.at(Config.SCHEDULE_TIME).do(scheduled_job)
        print(f"✅ 已设置定时任务：每天 {Config.SCHEDULE_TIME} 执行")
        
    elif mode == "interval_hours":
        # 每隔N小时执行
        schedule.every(Config.INTERVAL_HOURS).hours.do(scheduled_job)
        print(f"✅ 已设置定时任务：每隔 {Config.INTERVAL_HOURS} 小时执行")
        
    elif mode == "interval_minutes":
        # 每隔N分钟执行
        schedule.every(Config.INTERVAL_MINUTES).minutes.do(scheduled_job)
        print(f"✅ 已设置定时任务：每隔 {Config.INTERVAL_MINUTES} 分钟执行")
        
    else:
        print(f"❌ 未知的定时模式：{mode}")


def run_scheduler():
    """
    运行定时调度器
    
    主循环，持续检查并执行定时任务
    """
    print("\n" + "=" * 50)
    print("🌤️ 定时天气获取程序已启动")
    print(f"📍 目标城市：{Config.CITY}")
    print(f"⏰ 定时模式：{Config.SCHEDULE_MODE}")
    print("=" * 50)
    print("\n按 Ctrl+C 停止程序\n")
    
    # 设置定时任务
    setup_schedule()
    
    # 主循环
    while True:
        try:
            # 检查是否有待执行的任务
            schedule.run_pending()
            # 等待1秒后再检查
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\n\n👋 程序已停止")
            break
        except Exception as e:
            print(f"\n❌ 运行出错：{e}")
            time.sleep(5)  # 出错后等待5秒再重试


def main():
    """
    程序主入口
    
    提供交互式菜单，让用户选择运行模式
    """
    print("\n" + "=" * 50)
    print("🌤️ 欢迎使用定时天气获取程序")
    print("=" * 50)
    print("\n请选择运行模式：")
    print("1. 立即获取一次天气（单次运行）")
    print("2. 启动定时任务（持续运行）")
    print("3. 自定义城市查询")
    print("0. 退出程序")
    print("-" * 50)
    
    choice = input("请输入选项（0-3）：").strip()
    
    if choice == "1":
        # 单次获取天气
        get_weather()
        
    elif choice == "2":
        # 启动定时任务
        run_scheduler()
        
    elif choice == "3":
        # 自定义城市查询
        city = input("请输入城市名称（如：上海）：").strip()
        if city:
            get_weather(city)
        else:
            print("❌ 城市名称不能为空")
            
    elif choice == "0":
        print("👋 再见！")
        
    else:
        print("❌ 无效的选项")


# ==================== 程序入口 ====================
if __name__ == "__main__":
    main()
