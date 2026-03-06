#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本：调用add_queue API，数据严格适配music表结构
music表字段：id(必填)、name(必填)、artist(必填)、album、duration、url、lyric、cover、source、create_time、update_time
API接口：POST /player/queue/add
"""
import requests
import json
import datetime
import uuid
from typing import Optional, Dict, List, Any

# ==================== 核心配置 ====================
# API基础配置
BASE_API_URL = "http://127.0.0.1:3001"  # 替换为你的实际API地址
API_ADD_QUEUE = f"{BASE_API_URL}/player/queue/add"
HEADERS = {"Content-Type": "application/json"}

# ==================== 工具函数 ====================
def generate_music_id() -> str:
    """生成符合music表要求的id（varchar(32)）"""
    return str(uuid.uuid4()).replace("-", "")[:32]  # 确保长度不超过32位

def validate_music_data(music_item: Dict[str, Any]) -> bool:
    """
    验证单条音乐数据是否符合music表结构约束
    :param music_item: 单条音乐数据
    :return: 验证通过返回True，否则False
    """
    # 1. 检查必填字段（music表中NOT NULL的字段）
    required_fields = ["id", "name", "artist"]
    missing_fields = [f for f in required_fields if f not in music_item or not music_item[f]]
    if missing_fields:
        print(f"❌ 缺少music表必填字段：{missing_fields}")
        return False
    
    # 2. 检查字段类型/长度约束
    # id长度不超过32位
    if len(str(music_item["id"])) > 32:
        print(f"❌ id长度超过32位：{music_item['id']}")
        return False
    # name/artist长度不超过255位
    if len(str(music_item["name"])) > 255:
        print(f"❌ name长度超过255位：{music_item['name']}")
        return False
    if len(str(music_item["artist"])) > 255:
        print(f"❌ artist长度超过255位：{music_item['artist']}")
        return False
    # source长度不超过32位（如果传了）
    if "source" in music_item and len(str(music_item["source"])) > 32:
        print(f"❌ source长度超过32位：{music_item['source']}")
        return False
    # duration必须是整数（如果传了）
    if "duration" in music_item and music_item["duration"] is not None:
        try:
            int(music_item["duration"])
        except (ValueError, TypeError):
            print(f"❌ duration必须是整数：{music_item['duration']}")
            return False
    
    return True

# ==================== 核心API调用方法 ====================
def add_music_queue(music_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    调用add_queue API，添加音乐到播放队列（数据适配music表结构）
    :param music_list: 音乐列表，每个元素严格匹配music表字段
    :return: API响应结果（结构化）
    """
    # 步骤1：预处理并验证数据
    processed_items = []
    for idx, item in enumerate(music_list):
        # 生成默认id（如果未传）
        if "id" not in item or not item["id"]:
            item["id"] = generate_music_id()
            print(f"⚠️  为第{idx+1}条音乐自动生成id：{item['id']}")
        
        # 补全时间字段（可选，后端也可自动生成）
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item.setdefault("create_time", now)
        item.setdefault("update_time", now)
        
        # 验证数据合法性
        if not validate_music_data(item):
            print(f"❌ 第{idx+1}条音乐数据验证失败，跳过该条")
            continue
        
        # 加入处理后的列表
        processed_items.append(item)
    
    if not processed_items:
        return {
            "success": False,
            "status_code": None,
            "error": "没有合法的音乐数据可提交",
            "processed_count": 0
        }
    
    # 步骤2：构造API请求数据
    request_data = {"items": processed_items}
    
    # 步骤3：调用API
    try:
        print(f"\n📤 调用add_queue API，提交{len(processed_items)}条合法音乐数据")
        response = requests.post(
            url=API_ADD_QUEUE,
            headers=HEADERS,
            json=request_data,
            timeout=15  # 超时时间
        )
        
        # 步骤4：解析响应
        result = {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "processed_count": len(processed_items),
            "response_text": response.text,
            "response_json": None
        }
        
        # 尝试解析JSON响应
        try:
            result["response_json"] = response.json()
        except json.JSONDecodeError:
            result["error"] = "响应不是合法JSON格式"
        
        # 打印响应信息
        print(f"\n✅ API调用完成：")
        print(f"   状态码：{result['status_code']}")
        print(f"   提交数量：{len(processed_items)}")
        print(f"   响应内容：{result['response_text']}")
        
        return result
    
    # 异常处理
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "status_code": None,
            "error": "API请求超时",
            "processed_count": len(processed_items)
        }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "status_code": None,
            "error": f"无法连接到API服务器：{BASE_API_URL}",
            "processed_count": len(processed_items)
        }
    except Exception as e:
        return {
            "success": False,
            "status_code": None,
            "error": f"API调用异常：{str(e)}",
            "processed_count": len(processed_items)
        }

# ==================== 测试示例 ====================
if __name__ == "__main__":
    # 示例1：完整的音乐数据（匹配music表所有字段）
    test_music_list = [
        {
            # 必填字段（id/name/artist）
            "id": "",  # 留空会自动生成
            "name": "海阔天空-BEYOND",
            "artist": "BEYOND",
            # 可选字段
            "album": "BEYOND",
            "duration": 243,  # 时长（秒）
            "url": "F:/音乐收藏/download/海阔天空-BEYOND.mp3",
            "lyric": "",
            "cover": "",
            "source": "local",  # 来源（如local/netease/qqmusic）
            # 时间字段（可选，会自动补全）
            "create_time": "",
            "update_time": ""
        }
        # {
        #     "id": generate_music_id(),
        #     "name": "孤勇者",
        #     "artist": "陈奕迅",
        #     "album": "孤勇者",
        #     "duration": 216,
        #     "url": "F:/音乐收藏/download/陈奕迅-孤勇者.mp3",
        #     "source": "local"
        # }
    ]
    
    # 调用add_queue API
    result = add_music_queue(test_music_list)
    
    # 检查结果
    if result["success"]:
        print("\n🎉 音乐队列添加成功！")
    else:
        print(f"\n❌ 音乐队列添加失败：{result['error']}")
