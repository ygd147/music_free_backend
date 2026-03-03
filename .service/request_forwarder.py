"""请求转发服务：模拟原有RequestForwarder"""
import sys
import logging
import requests
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - RequestForwarder - %(levelname)s - %(message)s"
)
logger = logging.getLogger("RequestForwarder")

def forward_request(url: str, method: str = "GET", headers: dict = None, data: dict = None):
    """
    转发HTTP请求
    :param url: 目标URL
    :param method: 请求方法
    :param headers: 请求头
    :param data: 请求体
    :return: 响应结果
    """
    try:
        headers = headers or {}
        data = data or {}

        # 添加跨域相关头
        headers["Access-Control-Allow-Origin"] = "*"
        headers["Access-Control-Allow-Credentials"] = "true"

        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=data, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=10)
        elif method.upper() == "PUT":
            response = requests.put(url, headers=headers, json=data, timeout=10)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers, json=data, timeout=10)
        else:
            return {"error": f"不支持的请求方法：{method}"}

        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content": response.text,
            "encoding": response.encoding
        }
    except Exception as e:
        logger.error(f"请求转发失败：{str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    logger.info("RequestForwarder服务已启动")
    # 示例：测试转发
    try:
        test_result = forward_request("https://httpbin.org/get")
        logger.info(f"测试转发结果：{test_result}")
    except Exception as e:
        logger.error(f"测试转发失败：{str(e)}")

    # 阻塞服务运行
    try:
        while True:
            pass
    except KeyboardInterrupt:
        logger.info("RequestForwarder服务已退出")
        sys.exit(0)