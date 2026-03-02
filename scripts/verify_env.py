#!/usr/bin/env python3
"""
环境验证脚本 - 替代verify_system.py
检查所有API密钥格式、依赖版本和系统配置
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(msg: str):
    print(f"\n{BLUE}=== {msg} ==={RESET}")


def print_success(msg: str):
    print(f"{GREEN}✅ {msg}{RESET}")


def print_error(msg: str):
    print(f"{RED}❌ {msg}{RESET}")


def print_warning(msg: str):
    print(f"{YELLOW}⚠️  {msg}{RESET}")


def print_info(msg: str):
    print(f"ℹ️  {msg}")


def check_python_version() -> bool:
    """检查Python版本"""
    print_header("Python版本检查")
    version = sys.version_info
    print(f"当前Python版本: {version.major}.{version.minor}.{version.micro}")

    if version.major == 3 and version.minor >= 12:
        print_success("Python版本符合要求 (>=3.12)")
        return True
    else:
        print_error(f"Python版本不符合要求，需要3.12+，当前: {version.major}.{version.minor}")
        return False


def check_dependencies() -> bool:
    """检查核心依赖是否安装"""
    print_header("依赖检查")
    required_packages = {
        "yt-dlp": "视频下载",
        "youtube_transcript_api": "字幕API",
        "langchain_community": "LangChain社区组件",
        "firecrawl": "Firecrawl客户端",
        "openai": "OpenAI SDK",
        "cohere": "Cohere SDK",
        "langchain": "LangChain框架",
        "supabase": "Supabase客户端",
    }

    all_ok = True
    for package, description in required_packages.items():
        try:
            # 修改检查方式：尝试导入模块，如果成功则认为已安装
            # 获取版本号可能会失败（因为有些包的版本号获取方式不同），这里只检查是否可导入
            pkg_name = package.replace("-", "_")
            result = subprocess.run(
                ["uv", "run", "python", "-c", f'import {pkg_name}; print("OK")'],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and "OK" in result.stdout:
                print_success(f"{package} ({description}): 已安装")
            else:
                # 再次尝试不带 uv run
                result = subprocess.run(
                    [sys.executable, "-c", f'import {pkg_name}; print("OK")'],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and "OK" in result.stdout:
                    print_success(f"{package} ({description}): 已安装")
                else:
                    raise ImportError
        except (ImportError, subprocess.TimeoutExpired):
            print_error(f"{package} ({description}): 未安装")
            all_ok = False

    return all_ok


def check_env_file() -> bool:
    """检查.env文件"""
    print_header("环境配置文件检查")
    env_path = Path(".env")

    if not env_path.exists():
        print_error(".env文件不存在，请从.env.example复制")
        print_info("执行: cp .env.example .env")
        return False

    print_success(".env文件存在")

    # 检查关键变量
    env_vars = {
        "FIRECRAWL_API_KEY": "Firecrawl API密钥",
        "DEEPSEEK_API_KEY": "DeepSeek API密钥",
        "SUPABASE_URL": "Supabase URL",
        "SUPABASE_KEY": "Supabase匿名密钥",
        "OPENAI_API_KEY": "OpenAI API密钥",
    }

    all_ok = True
    for var, description in env_vars.items():
        value = os.getenv(var)
        if value:
            # 检查是否是默认值
            if "your_" in value or "here" in value or "fc-330bf918fa8046f397542ce18bba84e6" in value:
                print_warning(f"{var} ({description}): 使用默认/示例值")
                all_ok = False
            else:
                # 验证格式
                is_valid = validate_api_key_format(var, value)
                if is_valid:
                    print_success(f"{var}: 格式正确 ({description[:20]})")
                else:
                    print_warning(f"{var}: 格式可能不正确")
                    all_ok = False
        else:
            print_error(f"{var} ({description}): 未设置")
            all_ok = False

    return all_ok


def validate_api_key_format(var_name: str, value: str) -> bool:
    """验证API密钥格式"""
    if var_name == "DEEPSEEK_API_KEY":
        return value.startswith("sk-") and len(value) > 30
    elif var_name == "FIRECRAWL_API_KEY":
        return len(value) >= 20
    elif var_name == "OPENAI_API_KEY":
        return value.startswith("sk-") and len(value) > 30
    elif var_name == "COHERE_API_KEY":
        return len(value) > 20
    elif "SUPABASE" in var_name:
        return len(value) > 20 and "your_" not in value
    return True


def check_proxy_settings() -> bool:
    """检查代理设置"""
    print_header("网络代理检查")

    proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]
    found_proxy = False

    for var in proxy_vars:
        value = os.getenv(var)
        if value:
            print_info(f"{var}: {value}")
            found_proxy = True

    if found_proxy:
        print_success("检测到代理设置，采集引擎将自动使用")
    else:
        print_info("未检测到代理设置，使用直连")

    return True


def check_project_structure() -> bool:
    """检查项目结构"""
    print_header("项目结构检查")

    required_dirs = ["src", "src/core", "src/deepresearch_flow", "src/ingestion", "src/retrieval", "scripts"]

    required_files = [
        "pyproject.toml",
        ".python-version",
        ".env",
        "src/core/config.py",
        "src/deepresearch_flow/handlers/youtube_handler.py",
    ]

    all_ok = True

    print_info("检查目录结构...")
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print_success(f"目录: {dir_path}")
        else:
            print_error(f"目录缺失: {dir_path}")
            all_ok = False

    print_info("\n检查核心文件...")
    for file_path in required_files:
        if Path(file_path).exists():
            print_success(f"文件: {file_path}")
        else:
            print_error(f"文件缺失: {file_path}")
            all_ok = False

    return all_ok


def check_database_connection() -> bool:
    """检查数据库连接"""
    print_header("数据库连接检查")

    try:
        from supabase import create_client, Client

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")

        if not url or not key or "your_" in url:
            print_warning("Supabase URL/Key未正确配置，跳过连接测试")
            return False

        supabase: Client = create_client(url, key)

        # 尝试查询
        supabase.table("videos").select("id").limit(1).execute()

        print_success("Supabase数据库连接成功")
        return True

    except Exception as e:
        print_warning(f"Supabase连接失败: {str(e)[:100]}")
        return False


def main():
    """主检查流程"""
    print(f"""
{BLUE}
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║      YouTube Agentic RAG - 环境验证工具              ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝
{RESET}
    """)

    checks = [
        ("Python版本", check_python_version),
        ("依赖包", check_dependencies),
        ("环境配置", check_env_file),
        ("代理设置", check_proxy_settings),
        ("项目结构", check_project_structure),
        ("数据库连接", check_database_connection),
    ]

    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print_error(f"{name}检查失败: {str(e)}")
            results.append((name, False))

    # 汇总报告
    print_header("验证汇总")
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        if result:
            print_success(f"{name}: 通过")
        else:
            print_error(f"{name}: 失败")

    print(f"\n{BLUE}总结果: {passed}/{total} 项检查通过{RESET}")

    if passed == total:
        print_success("环境配置完整，可以开始使用！")
        print_info("\n下一步: python scripts/crawl_channel.py --help")
        return 0
    else:
        print_warning("部分检查未通过，请修复后再运行")
        return 1


if __name__ == "__main__":
    sys.exit(main())
