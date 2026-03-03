import pymysql
from pymysql.err import OperationalError, ProgrammingError

# 数据库配置（对应你提供的参数）
config = {
    'host': '192.168.0.155',
    'port': 3306,
    'user': 'music_free',
    'password': 'ygd147',
    'database': 'music_free',
    'charset': 'utf8mb4',
    # 额外配置：避免中文乱码、优化连接稳定性
    'cursorclass': pymysql.cursors.DictCursor,  # 游标返回字典格式，更易读
    'connect_timeout': 10  # 连接超时时间（秒）
}

def connect_mysql():
    """远程连接 MySQL 数据库的 demo 函数"""
    conn = None
    cursor = None
    try:
        # 1. 建立数据库连接
        conn = pymysql.connect(**config)
        print("✅ 成功连接到远程 MySQL 数据库！")

        # 2. 创建游标对象（用于执行SQL）
        cursor = conn.cursor()

        # 3. 执行测试查询（示例：查询数据库版本）
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        print(f"📌 MySQL 服务器版本: {version['VERSION()']}")

        # 4. 示例：查询数据库中的表（可选）
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        if tables:
            print("📋 数据库中存在的表：")
            for table in tables:
                # 适配字典游标，表名的key格式为 'Tables_in_数据库名'
                table_name = list(table.values())[0]
                print(f"  - {table_name}")
        else:
            print("📋 该数据库中暂无表")

        # 5. 提交事务（如果是增删改操作需要这一步）
        conn.commit()

    except OperationalError as e:
        # 处理连接相关错误（如地址错误、密码错误、端口不通等）
        print(f"❌ 数据库连接失败：{e}")
        print("🔍 排查方向：")
        print("  1. 检查 MySQL 服务器地址/端口是否正确")
        print("  2. 检查用户名/密码是否正确")
        print("  3. 确认远程服务器是否开放 3306 端口")
        print("  4. 确认 MySQL 用户是否有远程访问权限（需授权：GRANT ALL ON music_free.* TO 'music_free'@'%' IDENTIFIED BY 'ygd147';）")
    except ProgrammingError as e:
        # 处理 SQL 语法错误、数据库不存在等
        print(f"❌ SQL 执行失败：{e}")
    except Exception as e:
        # 其他异常
        print(f"❌ 未知错误：{e}")
        # 出错时回滚事务
        if conn:
            conn.rollback()
    finally:
        # 6. 关闭游标和连接（必须执行，释放资源）
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            print("🔌 数据库连接已关闭")

if __name__ == "__main__":
    # 执行连接测试
    connect_mysql()