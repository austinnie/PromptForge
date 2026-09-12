"""
打开微信公众平台草稿箱（半自动）

用法：
  首次登录：
      python skills/wechat_formatter/scripts/wechat_open_draft.py --login
      （打开浏览器，扫码登录，登录态保存到项目根目录 .wechat_state.json）

  之后每次：
      python skills/wechat_formatter/scripts/wechat_open_draft.py
      （自动加载登录态，打开公众号首页，你手动点【草稿箱】→【群发】）

特点：
  - 不用每次扫码（登录态复用）
  - 不做任何"自动点击"动作，规避风控
  - 登录态过期时提示你重新登录
"""
import argparse
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("❌ 请先安装: pip install playwright")
    print("   然后运行: python -m playwright install chromium")
    sys.exit(1)

# ============ 路径 ============
# scripts → wechat_formatter → skills → PromptForge
PROJECT_ROOT = Path(__file__).resolve().parents[3]
STATE_FILE   = PROJECT_ROOT / ".wechat_state.json"
MP_URL       = "https://mp.weixin.qq.com/"
# ==============================


def login_and_save():
    """首次登录：手动扫码，保存登录态"""
    print("🌐 打开浏览器，请扫码登录公众号后台...")
    print(f"   登录态将保存到: {STATE_FILE}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.goto(MP_URL, wait_until="domcontentloaded")

        print("\n📌 请在浏览器里扫码登录")
        print("📌 登录成功后（能看到后台首页），回到终端按【回车】继续")
        input()

        context.storage_state(path=str(STATE_FILE))
        print(f"\n✅ 登录态已保存: {STATE_FILE}")
        print(f"   ⚠️ 这个文件包含 cookie，绝不能提交到 git")
        browser.close()


def open_drafts():
    """加载登录态，打开公众号首页，停在草稿箱前"""
    if not STATE_FILE.exists():
        print(f"❌ 未找到登录态文件: {STATE_FILE}")
        print(f"   请先运行: python {Path(__file__).name} --login")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            storage_state=str(STATE_FILE),
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()

        print("🌐 打开公众号后台...")
        page.goto(MP_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # 检测登录状态
        need_login = False
        for keyword in ("扫码登录", "请使用微信扫描", "二维码登录"):
            try:
                if page.locator(f"text={keyword}").count() > 0:
                    need_login = True
                    break
            except Exception:
                pass

        if need_login:
            print("\n⚠️ 登录态已失效，请重新登录：")
            print(f"   python {Path(__file__).name} --login")
            browser.close()
            return

        print("\n✅ 已登录公众号后台")
        print("\n📌 接下来请手动操作：")
        print("   1. 左侧菜单点【草稿箱】")
        print("   2. 找到要发布的文章，点【编辑】")
        print("   3. 确认无误后点右上角【群发】")
        print("\n⌨️  完成后按【回车】关闭浏览器")

        try:
            input()
        except KeyboardInterrupt:
            pass

        # 退出前刷新登录态（cookie 可能已刷新）
        try:
            context.storage_state(path=str(STATE_FILE))
            print(f"💾 登录态已更新: {STATE_FILE}")
        except Exception as e:
            print(f"⚠️ 更新登录态失败: {e}")

        browser.close()


def main():
    parser = argparse.ArgumentParser(description="打开微信公众平台草稿箱（半自动）")
    parser.add_argument("--login", action="store_true",
                        help="首次登录（打开浏览器让你扫码）")
    args = parser.parse_args()

    if args.login:
        login_and_save()
    else:
        open_drafts()


if __name__ == "__main__":
    main()