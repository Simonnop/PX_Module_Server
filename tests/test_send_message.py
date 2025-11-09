#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
功能：测试调用后端接口 `POST /module/send_message` 并打印返回结果。

使用方式：
  python tests/test_send_message.py \
    --base-url http://127.0.0.1:10080 \
    --module-hash xxx \
    --message "test message" \
    --timeout 5 \
    --fail-on-non-2000

说明：
- 默认基础地址可通过环境变量 `API_BASE_URL` 设置，默认 `http://127.0.0.1:10080`。
- 不依赖第三方库，使用标准库 `urllib` 发起请求。
"""

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
import urllib.parse


def build_url(base_url: str) -> str:
    """拼接接口完整 URL。"""
    return base_url.rstrip("/") + "/module/send_message"


def fetch(url: str, module_hash: str, message: str, timeout_seconds: float) -> bytes:
    """发送 POST 请求并返回二进制响应体。"""
    data = urllib.parse.urlencode({
        "module_hash": module_hash,
        "message": message
    }).encode()
    
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "ForecastClient/1.0 (+send_message)",
        },
    )
    context = None
    if url.startswith("https://"):
        context = ssl.create_default_context()
    with urllib.request.urlopen(req, context=context, timeout=timeout_seconds) as resp:
        return resp.read()


def main() -> None:
    """解析参数，调用接口，打印结果并根据 code 返回退出码。"""
    parser = argparse.ArgumentParser(description="调用 /module/send_message 接口并打印结果")
    parser.add_argument(
        "--base-url",
        default=os.getenv("API_BASE_URL", "http://127.0.0.1:10080"),
        help="服务基础地址，默认读取环境变量 API_BASE_URL 或 http://127.0.0.1:10080",
    )
    parser.add_argument(
        "--module-hash",
        default="7117023912067415399",
        help="模块哈希值",
    )
    parser.add_argument(
        "--message",
        default="test message",
        help="要发送的消息",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="请求超时时间（秒），默认 5 秒",
    )
    parser.add_argument(
        "--fail-on-non-2000",
        action="store_true",
        help="当响应 code 不为 2000 时以非零退出码退出",
    )
    args = parser.parse_args()

    url = build_url(args.base_url)
    print(f"请求地址: {url}")
    print(f"模块哈希: {args.module_hash}")
    print(f"发送消息: {args.message}")
    print(f"超时时间: {args.timeout} 秒")
    print("正在发送请求...")

    args.message = {
        "type": "multiple_test",
        "data": [1,2,3,4,5,6,7,8,9,10]
    }

    try:
        start = time.time()
        resp = fetch(url, args.module_hash, json.dumps(args.message, ensure_ascii=False), args.timeout)
        elapsed = time.time() - start
    except Exception as e:
        print(f"请求失败: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"请求成功，耗时 {elapsed:.3f} 秒")
    print("响应内容:")
    resp_obj = json.loads(resp.decode())
    print(json.dumps(resp_obj, indent=2, ensure_ascii=False))

    if args.fail_on_non_2000 and resp_obj.get("code") != "2000":
        sys.exit(1)


if __name__ == "__main__":
    main()

