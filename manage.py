#!/usr/bin/env python3
"""
Django 管理脚本
"""
import os
import sys


def main():
    """Django 入口"""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project_base.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and available on your PYTHONPATH environment variable?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()


