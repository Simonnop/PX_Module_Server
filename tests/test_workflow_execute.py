#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
功能：测试调用后端接口 `POST /workflow/execute` 并打印返回结果。

使用方式：
  python tests/test_workflow_execute.py \
    --base-url http://127.0.0.1:10080 \
    --workflow-id 1 \
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
    return base_url.rstrip("/") + "/workflow/execute"


def fetch(url: str, workflow_id: int, timeout_seconds: float) -> bytes:
    """发送 POST 请求并返回二进制响应体。"""
    data = json.dumps({
        "workflow_id": workflow_id
    }, ensure_ascii=False).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "ForecastClient/1.0 (+workflow_execute)",
        },
    )
    context = None
    if url.startswith("https://"):
        context = ssl.create_default_context()
    with urllib.request.urlopen(req, context=context, timeout=timeout_seconds) as resp:
        return resp.read()


def main() -> None:
    """解析参数，调用接口，打印结果并根据 code 返回退出码。"""
    parser = argparse.ArgumentParser(description="调用 /workflow/execute 接口并打印结果")
    parser.add_argument(
        "--base-url",
        default=os.getenv("API_BASE_URL", "http://127.0.0.1:10080"),
        help="服务基础地址，默认读取环境变量 API_BASE_URL 或 http://127.0.0.1:10080",
    )
    parser.add_argument(
        "--workflow-id",
        type=int,
        required=True,
        help="工作流ID",
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
    print(f"POST {url}")
    print(f"工作流ID: {args.workflow_id}")
    print(f"超时时间: {args.timeout} 秒")
    print("正在发送请求...")

    try:
        start_time = time.time()
        raw_body = fetch(url, args.workflow_id, args.timeout)
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

    # 简单结构断言：成功时 result 应为字典且包含 workflow_id
    if code == "2000" and isinstance(result, dict):
        if "workflow_id" not in result:
            print("期望 result 包含 workflow_id 字段", file=sys.stderr)
            sys.exit(3)

    sys.exit(0)


if __name__ == "__main__":
    main()

