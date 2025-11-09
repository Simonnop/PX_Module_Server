#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
功能：测试调用后端接口 `GET /scheduler/jobs` 并打印返回结果。

使用方式：
  python tests/test_list_scheduled_jobs.py \
    --base-url http://127.0.0.1:10080 \
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


def build_url(base_url: str) -> str:
    """拼接接口完整 URL。"""
    return base_url.rstrip("/") + "/scheduler/jobs"


def fetch(url: str, timeout_seconds: float) -> bytes:
    """发送 GET 请求并返回二进制响应体。"""
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json",
            "User-Agent": "ForecastClient/1.0 (+list_scheduled_jobs)",
        },
    )
    context = None
    if url.startswith("https://"):
        context = ssl.create_default_context()
    with urllib.request.urlopen(req, context=context, timeout=timeout_seconds) as resp:
        return resp.read()


def main() -> None:
    """解析参数，调用接口，打印结果并根据 code 返回退出码。"""
    parser = argparse.ArgumentParser(description="调用 /scheduler/jobs 接口并打印结果")
    parser.add_argument(
        "--base-url",
        default=os.getenv("API_BASE_URL", "http://127.0.0.1:10080"),
        help="服务基础地址，默认读取环境变量 API_BASE_URL 或 http://127.0.0.1:10080",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("API_TIMEOUT", "5")),
        help="请求超时时间（秒），默认 5 秒",
    )
    parser.add_argument(
        "--fail-on-non-2000",
        action="store_true",
        help="当响应 code 不为 2000 时以非零退出码退出",
    )
    args = parser.parse_args()

    url = build_url(args.base_url)
    print(f"GET {url}")
    print(f"超时时间: {args.timeout} 秒")
    print("正在发送请求...")

    try:
        start_time = time.time()
        raw_body = fetch(url, args.timeout)
        elapsed_ms = (time.time() - start_time) * 1000.0
    except urllib.error.HTTPError as http_err:
        print(f"HTTPError: {http_err.code} {http_err.reason}", file=sys.stderr)
        if http_err.fp:
            body = http_err.fp.read()
            if body:
                try:
                    print(body.decode("utf-8", errors="ignore"), file=sys.stderr)
                except Exception:
                    pass
        sys.exit(1)
    except urllib.error.URLError as url_err:
        print(f"URLError: {url_err.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        print("响应不是合法 JSON:", file=sys.stderr)
        print(raw_body[:500], file=sys.stderr)
        sys.exit(1)

    code = payload.get("code")
    message = payload.get("message")
    result = payload.get("result")

    print("请求成功")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"耗时: {elapsed_ms:.1f} ms")

    if args.fail_on_non_2000 and code != "2000":
        sys.exit(2)

    # 简单结构断言：成功时 result 应为列表
    if code == "2000" and not isinstance(result, list):
        print("期望 result 为列表", file=sys.stderr)
        sys.exit(3)

    sys.exit(0)


if __name__ == "__main__":
    main()

