"""
RentalScraper - 租房信息爬虫核心模块

使用 Playwright (sync API) 抓取房源列表页数据。
目标网站：链家租房（北京望京），可修改 .env 中的 TARGET_URL 适配其他网站。
"""
from __future__ import annotations
import re
import os
import sys
import time
import random
from typing import Optional
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from dotenv import load_dotenv

# 加载 .env（从项目根目录）
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

TARGET_URL = os.getenv("TARGET_URL", "https://bj.lianjia.com/zufang/wangjing/")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
TIMEOUT = int(os.getenv("TIMEOUT", "30000"))


def clean_price(text: str) -> int:
    """
    从价格文本中提取纯数字（取第一个匹配的连续数字）。
    例如 "4500 元/月" -> 4500
         "2906-3048元/月" -> 2906 （取首个数字，避免串联）
    """
    if not text:
        return 0
    # 替换中文/英文分隔符为空格，避免 "2906-3048" 被合并为 29063048
    normalized = re.sub(r"[-—~～至到]\s*", " ", str(text))
    match = re.search(r"\d+", normalized)
    return int(match.group()) if match else 0


def clean_size(text: str) -> float:
    """
    从面积文本中提取数字。
    例如 "89.5㎡" -> 89.5
    """
    if not text:
        return 0.0
    match = re.search(r"[\d.]+", str(text))
    return float(match.group()) if match else 0.0


def parse_bedrooms(title: str) -> str:
    """
    从标题中提取几室几厅。
    例如 "望京新城 2室1厅 89㎡" -> "2室1厅"
    也尝试从专门的结构字段提取。
    """
    if not title:
        return ""
    match = re.search(r"(\d+室\d+厅)", str(title))
    return match.group(1) if match else ""


def parse_location(title: str) -> str:
    """
    从标题中提取小区/区域名称（粗略提取：取第一个空格前的部分）。
    实际使用中建议根据目标网站的 HTML 结构调整。
    """
    if not title:
        return ""
    # 取标题开头的区域名或小区名
    parts = str(title).strip().split()
    return parts[0] if parts else ""


def _try_click_next_page(page) -> bool:
    """
    在当前页面查找「下一页」按钮并点击翻页。

    优先使用真实点击（携带 session/cookie，更像人类），
    点击失败时 fallback 到 href 直接导航。

    Returns:
        bool: 是否成功翻到下一页
    """
    next_selectors = [
        'a:has-text("下一页")',
        'span:has-text("下一页")',
        ".page-box .next",
        '.page-box a[class*="next"]',
        '[class*="page"] a:has-text("下一页")',
        "li.next a",
        'a[class*="next"]',
    ]

    for sel in next_selectors:
        el = page.query_selector(sel)
        if not el:
            continue

        # 检查是否置灰（末页）
        el_class = (el.get_attribute("class") or "").lower()
        parent_class = page.evaluate(
            """(el) => {
                const p = el.parentElement;
                return p ? (p.className || '') : '';
            }""",
            el,
        ).lower()

        if "disable" in el_class or "end" in el_class or "active" in parent_class:
            print(f"[Spider] 「下一页」已置灰 ({sel})，已到末页")
            continue

        print(f"[Spider] 找到下一页: {sel}")

        # 记录点击前状态，用于后续判断是否真正翻页
        url_before = page.url

        # --- 模拟人类：先滚到底部，停顿一下 ---
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(random.uniform(800, 1500))
        except Exception:
            pass

        # --- 方式 1: 点击「下一页」并等待内容刷新 ---
        try:
            el.scroll_into_view_if_needed()
            page.wait_for_timeout(300)

            # 记录点击前的列表项数量，用于判断内容是否刷新
            old_count = len(page.query_selector_all(".content__list--item"))
            old_first_title = ""
            first_el = page.query_selector(".content__list--item--title a")
            if first_el:
                old_first_title = first_el.inner_text().strip()

            el.click(force=True)

            # AJAX 翻页不会触发页面导航，轮询等待列表内容变化
            page.wait_for_timeout(2000)
            for _ in range(10):  # 最多等 10 秒
                new_first_el = page.query_selector(".content__list--item--title a")
                new_first_title = new_first_el.inner_text().strip() if new_first_el else ""
                new_count = len(page.query_selector_all(".content__list--item"))

                if new_first_title and new_first_title != old_first_title:
                    print(f"[Spider] 内容已刷新 (旧: {old_first_title[:20]}... → 新: {new_first_title[:20]}...)")
                    return True
                if new_count != old_count:
                    print(f"[Spider] 列表数量变化 ({old_count} → {new_count})")
                    return True

                page.wait_for_timeout(1000)

            # 轮询结束仍未变化，检查 URL 是否变了（有些站点的确是跳转翻页）
            if page.url != url_before:
                print(f"[Spider] URL 已变化: {page.url}")
                return True

            print(f"[Spider] 点击后内容未刷新，可能点击了错误的元素，尝试下一种方式")
            continue

        except Exception as e:
            print(f"[Spider] 点击翻页异常: {e}，尝试 href 跳转...")

        # --- 方式 2: href 直接导航（fallback）---
        href = el.get_attribute("href")
        if href:
            full_url = urljoin(page.url, href)
            if "#" in full_url:
                full_url = full_url.split("#")[0]
            print(f"[Spider] goto: {full_url}")
            try:
                page.goto(full_url, wait_until="domcontentloaded", timeout=TIMEOUT)
                if "login" in page.url.lower():
                    print(f"[Spider] ⚠ goto 也被重定向到登录页")
                    return False
                return True
            except Exception as goto_err:
                print(f"[Spider] goto 也失败: {goto_err}")
                continue

    print("[Spider] 未找到可点击的下一页，翻页结束")
    return False


def _scrape_single_page(page, page_num: int) -> list[dict]:
    """
    抓取当前页面中的房源列表数据。

    Args:
        page: Playwright Page 对象（已导航到目标页面）
        page_num: 当前页码（仅用于日志）

    Returns:
        list[dict]: 当前页提取到的房源数据
    """
    properties: list[dict] = []

    # 等待房源列表加载
    try:
        page.wait_for_selector(".content__list--item", timeout=TIMEOUT)
    except PlaywrightTimeout:
        print(f"[Spider] 第{page_num}页 主选择器超时，尝试备用选择器...")
        try:
            page.wait_for_selector(".content__list", timeout=10000)
        except PlaywrightTimeout:
            print(f"[Spider] 第{page_num}页 备用选择器也超时，跳过本页")

    # 给 JS 渲染留一点缓冲时间
    page.wait_for_timeout(2000)

    # 获取列表项
    items = page.query_selector_all(".content__list--item")
    if len(items) == 0:
        items = page.query_selector_all("[class*='list'] > [class*='item']")

    print(f"[Spider] 第{page_num}页 找到 {len(items)} 个房源列表项")

    # 遍历提取
    for idx, item in enumerate(items):
        try:
            prop = _extract_property(item, idx)
            if prop:
                properties.append(prop)
        except Exception as e:
            print(f"[Spider] 第{page_num}页 提取第 {idx + 1} 项时出错: {e}")
            continue

    return properties


def scrape(url: str = TARGET_URL, max_pages: int = 5) -> list[dict]:
    """
    核心爬虫函数：打开目标页面，逐页抓取房源列表数据。

    翻页策略 (click-based):
        1. 第 1 页: 直接访问 base_url
        2. 第 2 页起: 点击页面底部的「下一页」按钮（a:has-text("下一页") 等）
        3. 每页抓取完毕后随机停顿 3~8 秒，模拟人类浏览行为
        4. 直到达到 max_pages 上限、或下一页按钮不可点击、或某页无数据为止

    Args:
        url: 目标房源列表页基础 URL（例如 https://hz.zu.ke.com/zufang/binjiang/）
        max_pages: 最大翻页数，默认 5 页

    Returns:
        list[dict]: 所有页面汇总的房源信息字典列表
    """
    all_properties: list[dict] = []

    print(f"[Spider] 正在启动浏览器...")
    print(f"[Spider] 基础 URL: {url}")
    print(f"[Spider] 最大翻页数: {max_pages}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        page = context.new_page()

        # 隐藏 webdriver 特征
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            window.chrome = { runtime: {} };
        """)

        try:
            # ---- 第 1 页：直接访问 ----
            print(f"\n{'='*60}")
            print(f"[Spider] ▸ 正在抓取第 1/{max_pages} 页")
            print(f"[Spider] ▸ URL: {url}")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT)
            except PlaywrightTimeout:
                print(f"[Spider] 第1页 页面加载超时，终止")
                return all_properties
            except Exception as e:
                print(f"[Spider] 第1页 导航出错: {e}，终止")
                return all_properties

            page_properties = _scrape_single_page(page, 1)
            all_properties.extend(page_properties)
            print(f"[Spider] 第1页 提取完成: {len(page_properties)} 条 (累计 {len(all_properties)} 条)")

            if len(page_properties) == 0:
                print("[Spider] 首页无数据，终止")
                return all_properties

            # ---- 第 2 ~ max_pages 页：点击「下一页」翻页 ----
            for page_num in range(2, max_pages + 1):
                # 防封禁：翻页前随机停顿
                delay = random.uniform(3, 8)
                print(f"[Spider] 防封禁停顿 {delay:.1f} 秒...")
                time.sleep(delay)

                print(f"\n{'='*60}")
                print(f"[Spider] ▸ 正在抓取第 {page_num}/{max_pages} 页（点击下一页）")

                # 翻到下一页
                if not _try_click_next_page(page):
                    print(f"[Spider] 无法翻到第{page_num}页，翻页结束")
                    break

                # 确认列表已加载（_try_click_next_page 内部已做内容刷新检测，这里是兜底）
                try:
                    page.wait_for_selector(".content__list--item", timeout=10000)
                except PlaywrightTimeout:
                    print(f"[Spider] 第{page_num}页 列表加载超时，终止翻页")
                    break

                page.wait_for_timeout(2000)

                # 去重：用已收集的 title 集合避免重复（同一房源可能跨页出现）
                existing_titles = {p["title"] for p in all_properties}

                page_properties = _scrape_single_page(page, page_num)
                # 过滤重复
                new_count = 0
                for prop in page_properties:
                    if prop["title"] not in existing_titles:
                        all_properties.append(prop)
                        existing_titles.add(prop["title"])
                        new_count += 1

                print(f"[Spider] 第{page_num}页 提取完成: {len(page_properties)} 条 (新增 {new_count} 条, 累计 {len(all_properties)} 条)")

                # 如果本页没有新增数据，可能已到末页
                if new_count == 0:
                    print(f"[Spider] 第{page_num}页 无新数据，已爬取完所有页，提前终止")
                    break

        except Exception as e:
            print(f"[Spider] 爬取过程出错: {e}")
        finally:
            browser.close()

    print(f"\n[Spider] ========== 爬取完成 ==========")
    print(f"[Spider] 共抓取 {len(all_properties)} 条房源数据")
    return all_properties


def _extract_property(item, index: int) -> Optional[dict]:
    """
    从单个列表项 DOM 元素中提取房源字段。

    Args:
        item: Playwright ElementHandle
        index: 列表索引（用于日志）

    Returns:
        dict or None: 提取到的房源信息
    """

    # --- 标题 ---
    title_el = item.query_selector(".content__list--item--title a")
    # 备用选择器
    if not title_el:
        title_el = item.query_selector("a[class*='title']")
    if not title_el:
        title_el = item.query_selector("p[class*='title'] a")

    title = title_el.inner_text().strip() if title_el else ""
    # 去除 HTML 中常见的空白
    title = re.sub(r"\s+", " ", title)

    if not title:
        print(f"[Spider] 第 {index + 1} 项无标题，跳过")
        return None

    # --- 价格 ---
    price_el = item.query_selector(".content__list--item-price em")
    if not price_el:
        price_el = item.query_selector("[class*='price']")
    price_text = price_el.inner_text().strip() if price_el else "0"
    price = clean_price(price_text)

    # --- 描述区域（通常包含面积、户型等）---
    desc_el = item.query_selector(".content__list--item--des")
    desc_text = desc_el.inner_text().strip() if desc_el else ""

    # --- 面积 ---
    size = 0.0
    size_match = re.search(r"([\d.]+)\s*㎡", desc_text)
    if not size_match:
        size_match = re.search(r"([\d.]+)\s*平米", desc_text)
    if size_match:
        size = float(size_match.group(1))
    else:
        # 尝试从 title 提取
        size = clean_size(title) if "㎡" in title or "平米" in title else 0.0

    # --- 户型（几室几厅）---
    bedrooms = ""
    bd_match = re.search(r"(\d+室\d+厅)", desc_text)
    if bd_match:
        bedrooms = bd_match.group(1)
    if not bedrooms:
        bedrooms = parse_bedrooms(title)

    # --- 区域/位置 ---
    location = ""
    location_el = item.query_selector("[class*='position']")
    if not location_el:
        location_el = item.query_selector("[class*='location']")
    if not location_el:
        location_el = item.query_selector("[class*='address']")
    if location_el:
        location = location_el.inner_text().strip()
    if not location:
        location = parse_location(title)

    # --- 标签 ---
    tags: list[str] = []
    tag_elements = item.query_selector_all("[class*='tag'] i")
    if not tag_elements:
        tag_elements = item.query_selector_all("[class*='label']")
    if not tag_elements:
        # 链家特色标签
        tag_elements = item.query_selector_all(".content__list--item--label")

    for tag_el in tag_elements:
        tag_text = tag_el.inner_text().strip()
        if tag_text and tag_text not in tags:
            tags.append(tag_text)

    # 如果通过上述选择器没拿到标签，尝试从描述中提取关键词
    if not tags and desc_text:
        keywords = ["近地铁", "精装", "拎包入住", "随时看房", "新上", "独立阳台",
                     "独立卫生间", "南北通透", "押一付一", "月付"]
        for kw in keywords:
            if kw in desc_text:
                tags.append(kw)

    prop = {
        "title": title,
        "location": location,
        "price": price,
        "size": size,
        "bedrooms": bedrooms,
        "tags": tags,
    }

    print(f"[Spider] [{index + 1}] {title[:40]}... | ¥{price}/月 | {size}㎡ | {bedrooms}")
    return prop


# ============================================================
# 独立运行入口
# ============================================================
if __name__ == "__main__":
    MAX_PAGES = int(os.getenv("MAX_PAGES", "5"))
    data = scrape(max_pages=MAX_PAGES)
    print(f"\n共爬取 {len(data)} 条数据")

    # 简单预览
    for i, d in enumerate(data[:5]):
        print(f"  {i + 1}. {d['title'][:50]} | ¥{d['price']} | {d['size']}㎡ | {d['bedrooms']} | 标签: {d['tags']}")
    if len(data) > 5:
        print(f"  ... 还有 {len(data) - 5} 条")
