"""
Dayflow Release Script - 一键打包并发布到 GitHub

使用方法:
    python release.py              # 打包 + 发布
    python release.py --build-only # 仅打包不发布
    python release.py --notes "修复了xxx" # 自定义发布说明

首次使用需要设置 GitHub Token:
    set GITHUB_TOKEN=ghp_xxxxxxxxxxxx
    
获取 Token: https://github.com/settings/tokens (需要 repo 权限)
"""
import os
import sys
import json
import shutil
import zipfile
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

import httpx

# 从 config 导入版本信息
sys.path.insert(0, str(Path(__file__).parent))
import config

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
REPO = config.GITHUB_REPO
VERSION = config.VERSION


def print_header(text: str):
    """打印标题"""
    print("\n" + "=" * 50)
    print(f"  {text}")
    print("=" * 50)


def run_build() -> bool:
    """运行打包"""
    print_header("🔨 开始打包")
    
    # 使用 dayflow 环境的 Python
    python_exe = r"C:\Users\L\anaconda3\envs\dayflow\python.exe"
    if not Path(python_exe).exists():
        # 尝试当前 Python
        python_exe = sys.executable
    
    result = subprocess.run(
        [python_exe, "build.py"],
        cwd=Path(__file__).parent
    )
    
    return result.returncode == 0


def create_zip() -> Path:
    """创建 ZIP 压缩包"""
    print_header("📦 创建 ZIP 压缩包")
    
    dist_dir = Path(__file__).parent / "dist" / "Dayflow"
    if not dist_dir.exists():
        raise FileNotFoundError(f"打包目录不存在: {dist_dir}")
    
    # ZIP 文件名
    zip_name = f"Dayflow_v{VERSION}.zip"
    zip_path = Path(__file__).parent / "dist" / zip_name
    
    # 删除旧的 ZIP
    if zip_path.exists():
        zip_path.unlink()
    
    # 创建 ZIP
    print(f"  压缩目录: {dist_dir}")
    print(f"  输出文件: {zip_path}")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in dist_dir.rglob('*'):
            if file.is_file():
                arcname = f"Dayflow/{file.relative_to(dist_dir)}"
                zf.write(file, arcname)
    
    size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"  文件大小: {size_mb:.1f} MB")
    
    return zip_path


def create_release(zip_path: Path, notes: str = "") -> bool:
    """创建 GitHub Release"""
    print_header("🚀 创建 GitHub Release")
    
    if not GITHUB_TOKEN:
        print("❌ 错误: 未设置 GITHUB_TOKEN 环境变量")
        print("   请运行: set GITHUB_TOKEN=ghp_xxxxxxxxxxxx")
        print("   获取 Token: https://github.com/settings/tokens")
        return False
    
    tag = f"v{VERSION}"
    
    # 默认发布说明
    if not notes:
        notes = f"""## Dayflow v{VERSION}

### ✨ 更新内容

- 支持 OpenAI 兼容 API（可自定义 API 地址、密钥、模型）
- 自动更新支持 ZIP 压缩包下载
- 修复若干问题

### 📦 安装说明

1. 下载 `Dayflow_v{VERSION}.zip`
2. 解压到任意目录
3. 运行 `Dayflow/Dayflow.exe`

### 💡 API 配置

支持任意 OpenAI 兼容接口：
- OpenAI: `https://api.openai.com/v1`
- DeepSeek: `https://api.deepseek.com/v1`
- 心流 API: `https://apis.iflow.cn/v1`
- Ollama: `http://localhost:11434/v1`
"""
    
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    # 1. 创建 Release
    print(f"  创建 Release: {tag}")
    
    release_data = {
        "tag_name": tag,
        "name": f"Dayflow {tag}",
        "body": notes,
        "draft": False,
        "prerelease": False
    }
    
    try:
        with httpx.Client(timeout=30) as client:
            # 检查 Release 是否已存在
            resp = client.get(
                f"https://api.github.com/repos/{REPO}/releases/tags/{tag}",
                headers=headers
            )
            
            if resp.status_code == 200:
                # Release 已存在，获取 ID
                release = resp.json()
                release_id = release["id"]
                print(f"  Release 已存在，更新中...")
                
                # 更新 Release
                resp = client.patch(
                    f"https://api.github.com/repos/{REPO}/releases/{release_id}",
                    headers=headers,
                    json={"body": notes}
                )
                resp.raise_for_status()
                
                # 删除旧的资产
                for asset in release.get("assets", []):
                    print(f"  删除旧资产: {asset['name']}")
                    client.delete(
                        f"https://api.github.com/repos/{REPO}/releases/assets/{asset['id']}",
                        headers=headers
                    )
            else:
                # 创建新 Release
                resp = client.post(
                    f"https://api.github.com/repos/{REPO}/releases",
                    headers=headers,
                    json=release_data
                )
                resp.raise_for_status()
                release = resp.json()
                release_id = release["id"]
                print(f"  Release 创建成功")
            
            # 2. 上传 ZIP 文件
            print(f"  上传文件: {zip_path.name}")
            
            upload_url = f"https://uploads.github.com/repos/{REPO}/releases/{release_id}/assets"
            
            with open(zip_path, 'rb') as f:
                resp = client.post(
                    upload_url,
                    params={"name": zip_path.name},
                    headers={
                        **headers,
                        "Content-Type": "application/zip"
                    },
                    content=f.read()
                )
                resp.raise_for_status()
            
            print(f"\n✅ 发布成功!")
            print(f"   https://github.com/{REPO}/releases/tag/{tag}")
            return True
            
    except httpx.HTTPStatusError as e:
        print(f"❌ GitHub API 错误: {e.response.status_code}")
        print(f"   {e.response.text}")
        return False
    except Exception as e:
        print(f"❌ 发布失败: {e}")
        return False


def main():
    global GITHUB_TOKEN
    
    parser = argparse.ArgumentParser(description="Dayflow 发布工具")
    parser.add_argument("--build-only", action="store_true", help="仅打包，不发布")
    parser.add_argument("--skip-build", action="store_true", help="跳过打包，直接发布")
    parser.add_argument("--notes", type=str, default="", help="自定义发布说明")
    parser.add_argument("--token", type=str, default="", help="GitHub Token (或设置 GITHUB_TOKEN 环境变量)")
    args = parser.parse_args()
    
    # 支持命令行传入 Token
    if args.token:
        GITHUB_TOKEN = args.token
    
    print_header(f"Dayflow Release v{VERSION}")
    
    # 打包
    if not args.skip_build:
        if not run_build():
            print("❌ 打包失败")
            sys.exit(1)
    
    # 创建 ZIP
    try:
        zip_path = create_zip()
    except Exception as e:
        print(f"❌ 创建 ZIP 失败: {e}")
        sys.exit(1)
    
    if args.build_only:
        print(f"\n✅ 打包完成: {zip_path}")
        return
    
    # 发布
    if not create_release(zip_path, args.notes):
        sys.exit(1)


if __name__ == "__main__":
    main()
