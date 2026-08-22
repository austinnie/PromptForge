# main.py
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
智能生图 - 独立版
AI 对话式图片生成
"""

from gui.app import ChatApp


def main():
    app = ChatApp()
    app.run()


if __name__ == "__main__":
    main()