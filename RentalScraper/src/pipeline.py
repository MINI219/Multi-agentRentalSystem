"""
RentalScraper - 数据清洗与导出模块

将爬虫原始数据清洗后，转换为下游 AI 租房系统所需的标准 CSV 格式。
输出字段: id, title, location, price, size, bedrooms, pet_friendly, description
"""
from __future__ import annotations
import uuid
import os
import sys
from typing import Optional

import pandas as pd
from dotenv import load_dotenv

# 确保可以导入同目录的 spider 模块
sys.path.insert(0, os.path.dirname(__file__))
from spider import scrape

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
OUTPUT_CSV = os.getenv("OUTPUT_CSV", "properties.csv")
MAX_PAGES = int(os.getenv("MAX_PAGES", "5"))


def is_pet_friendly(tags: list[str]) -> bool:
    """
    根据标签判断是否可养宠物。
    规则：tags 中是否包含"宠物"、"猫"、"狗"等关键词。
    保守策略：默认返回 False。
    """
    if not tags:
        return False
    pet_keywords = ["宠物", "养宠", "猫", "狗", "可宠", "宠物友好"]
    for tag in tags:
        if any(kw in tag for kw in pet_keywords):
            return True
    return False


def build_description(title: str, tags: list[str]) -> str:
    """
    拼接 title 和 tags 生成房源描述。
    """
    parts = [title] if title else []
    if tags:
        parts.append(" | ".join(tags))
    return "; ".join(parts)


def clean_dataframe(raw_data: list[dict]) -> pd.DataFrame:
    """
    清洗原始爬虫数据，转换为标准 DataFrame。

    清洗步骤:
        1. 过滤掉 title 为空的数据
        2. 确保 price > 0，否则标记为缺失
        3. 确保 size > 0，否则标记为缺失
        4. 移除缺失关键字段的行
        5. 生成 id、pet_friendly、description 列

    Args:
        raw_data: spider.scrape() 返回的原始数据列表

    Returns:
        pd.DataFrame: 清洗后的 DataFrame
    """
    if not raw_data:
        print("[Pipeline] 无原始数据，返回空 DataFrame")
        return pd.DataFrame()

    df = pd.DataFrame(raw_data)
    print(f"[Pipeline] 原始数据: {len(df)} 条")
    print(f"[Pipeline] 原始列: {list(df.columns)}")

    # --- 清洗 title ---
    initial = len(df)
    df["title"] = df["title"].astype(str).str.strip()
    df = df[df["title"] != ""].copy()
    print(f"[Pipeline] 过滤空标题: {initial} -> {len(df)} (移除 {initial - len(df)} 条)")

    # --- 清洗 price ---
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0).astype(int)
    low_price = (df["price"] <= 0).sum()
    df = df[df["price"] > 0].copy()
    if low_price > 0:
        print(f"[Pipeline] 过滤无效价格: 移除 {low_price} 条")

    # --- 清洗 size ---
    df["size"] = pd.to_numeric(df["size"], errors="coerce").fillna(0.0)
    no_size = (df["size"] <= 0).sum()
    # size 为 0 的不一定要删除，下游可能仍需要
    if no_size > 0:
        print(f"[Pipeline] 注意: {no_size} 条数据缺少面积信息")

    # --- 清洗 bedrooms ---
    df["bedrooms"] = df["bedrooms"].fillna("").astype(str)

    # --- 清洗 location ---
    df["location"] = df["location"].fillna("").astype(str).str.strip()

    # --- 生成新列 ---

    # id: UUID
    df["id"] = [str(uuid.uuid4()) for _ in range(len(df))]

    # pet_friendly: 根据 tags 判断
    df["pet_friendly"] = df["tags"].apply(is_pet_friendly)

    # description: 拼接 title + tags
    df["description"] = df.apply(
        lambda row: build_description(row["title"], row["tags"]), axis=1
    )

    # --- 转换 tags 列表为逗号分隔字符串（CSV 友好）---
    df["tags"] = df["tags"].apply(
        lambda t: ", ".join(t) if isinstance(t, list) else str(t)
    )

    # --- 选择输出列 ---
    output_columns = [
        "id", "title", "location", "price", "size",
        "bedrooms", "pet_friendly", "description"
    ]
    df_out = df[output_columns].copy()

    print(f"[Pipeline] 清洗完成，最终数据: {len(df_out)} 条")
    return df_out


def export_csv(df: pd.DataFrame, output_path: Optional[str] = None) -> str:
    """
    将 DataFrame 导出为 CSV 文件。

    Args:
        df: 清洗后的 DataFrame
        output_path: 输出路径，默认为项目根目录下的 properties.csv

    Returns:
        str: 实际导出的文件路径
    """
    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(__file__), "..", OUTPUT_CSV
        )

    # 确保路径为绝对路径
    output_path = os.path.abspath(output_path)

    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[Pipeline] 数据已导出到: {output_path}")
    print(f"[Pipeline] 共 {len(df)} 行, {len(df.columns)} 列")
    print(f"[Pipeline] 列名: {list(df.columns)}")
    return output_path


def run(max_pages: int = MAX_PAGES):
    """
    运行完整流水线: 爬取 -> 清洗 -> 导出

    Args:
        max_pages: 最大翻页数，默认从 .env 读取 (默认 5)
    """
    # Step 1: 爬取
    raw_data = scrape(max_pages=max_pages)

    # Step 2: 清洗
    df = clean_dataframe(raw_data)

    if df.empty:
        print("[Pipeline] 无有效数据可导出，流程终止")
        return

    # Step 3: 导出
    export_csv(df)

    # 预览
    print("\n[Pipeline] ========== 导出预览 (前3条) ==========")
    for _, row in df.head(3).iterrows():
        print(f"  ID: {row['id'][:8]}... | {row['title'][:40]} | "
              f"¥{row['price']}/月 | {row['bedrooms']} | "
              f"宠物: {row['pet_friendly']}")


if __name__ == "__main__":
    run()
