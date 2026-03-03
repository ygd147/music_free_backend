"""通用工具函数"""
import base64
import hashlib
import os
from datetime import datetime
from uuid import uuid4
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

# ========== 加密工具 ==========
def _get_aes_key(key: str) -> bytes:
    """生成AES密钥（32位）"""
    return hashlib.sha256(key.encode()).digest()[:32]

def encrypt_aes(data: str, key: str = "music_free_default_key") -> str:
    """AES加密"""
    try:
        # 填充数据
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data.encode()) + padder.finalize()
        
        # 生成随机IV
        iv = os.urandom(16)
        
        # 加密
        cipher = Cipher(algorithms.AES(_get_aes_key(key)), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(padded_data) + encryptor.finalize()
        
        # 返回IV+密文的base64编码
        return base64.b64encode(iv + encrypted).decode()
    except Exception as e:
        raise ValueError(f"AES加密失败：{e}")

def decrypt_aes(encrypted_data: str, key: str = "music_free_default_key") -> str:
    """AES解密"""
    try:
        # 解码base64
        data = base64.b64decode(encrypted_data)
        
        # 分离IV和密文
        iv = data[:16]
        encrypted = data[16:]
        
        # 解密
        cipher = Cipher(algorithms.AES(_get_aes_key(key)), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(encrypted) + decryptor.finalize()
        
        # 去除填充
        unpadder = padding.PKCS7(128).unpadder()
        unpadded = unpadder.update(decrypted) + unpadder.finalize()
        
        return unpadded.decode()
    except Exception as e:
        raise ValueError(f"AES解密失败：{e}")

# ========== 时间/时长工具 ==========
def format_duration(seconds: int) -> str:
    """将秒数格式化为 MM:SS 或 HH:MM:SS"""
    if seconds < 0:
        return "00:00"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"

def parse_duration(duration_str: str) -> int:
    """将 MM:SS 或 HH:MM:SS 转换为秒数"""
    parts = duration_str.split(":")
    parts = [int(p) for p in parts if p.isdigit()]
    
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    elif len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    else:
        return 0

# ========== 字符串工具 ==========
def camel_to_snake(s: str) -> str:
    """驼峰转下划线"""
    return ''.join(['_' + c.lower() if c.isupper() else c for c in s]).lstrip('_')

def snake_to_camel(s: str) -> str:
    """下划线转驼峰"""
    parts = s.split('_')
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])

# ========== ID生成工具 ==========
def generate_unique_id(prefix: str = "") -> str:
    """生成唯一ID"""
    uid = uuid4().hex[:12]
    return f"{prefix}_{uid}" if prefix else uid

# ========== 其他工具 ==========
def get_file_md5(file_path: str) -> str:
    """获取文件MD5"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def format_datetime(dt: datetime = None, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化时间"""
    if not dt:
        dt = datetime.now()
    return dt.strftime(format_str)