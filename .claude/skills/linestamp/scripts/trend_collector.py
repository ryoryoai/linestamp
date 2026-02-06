"""
LINE STORE トレンド収集モジュール

ランキング・メタデータ・特徴を収集してDBに保存
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

try:
    from .database import (
        get_trend_stats,
        get_products_without_meta,
        get_products_without_features,
        list_products_for_analysis,
        save_ranking_snapshot,
        upsert_product_meta,
        upsert_sticker_features,
        upsert_product_features,
        upsert_embedding,
        init_database,
    )
except ImportError:
    from database import (
        get_trend_stats,
        get_products_without_meta,
        get_products_without_features,
        list_products_for_analysis,
        save_ranking_snapshot,
        upsert_product_meta,
        upsert_sticker_features,
        upsert_product_features,
        upsert_embedding,
        init_database,
    )

# ランキングURL
RANKING_URLS = {
    "top": "https://store.line.me/stickershop/showcase/top/ja",
    "top_creators": "https://store.line.me/stickershop/showcase/top_creators/ja",
}

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; linestamp-trend-collector; +https://example.invalid)",
    "Accept-Language": "ja,en;q=0.8",
}


class RateLimiter:
    """シンプルなレート制限"""

    def __init__(self, min_interval_sec: float = 1.0):
        self.min_interval_sec = float(min_interval_sec)
        self._last_ts = 0.0

    def wait(self) -> None:
        if self.min_interval_sec <= 0:
            return
        now = time.monotonic()
        elapsed = now - self._last_ts
        if elapsed < self.min_interval_sec:
            time.sleep(self.min_interval_sec - elapsed)
        self._last_ts = time.monotonic()


def log(msg: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", file=sys.stderr, flush=True)


def compute_list_hash(product_ids: list[int]) -> str:
    """商品IDリストのハッシュを計算"""
    data = ",".join(str(pid) for pid in product_ids)
    return hashlib.sha256(data.encode()).hexdigest()


# ==================== ランキング収集 ====================

def extract_product_ids_from_showcase(html: str, max_items: int = 100) -> list[int]:
    """ショーケースHTMLから商品IDを抽出"""
    soup = BeautifulSoup(html, "lxml")
    product_ids = []

    for a in soup.select("a[href*='/stickershop/product/']"):
        href = a.get("href", "")
        match = re.search(r"/stickershop/product/(\d+)", href)
        if match:
            pid = int(match.group(1))
            if pid not in product_ids:
                product_ids.append(pid)
                if len(product_ids) >= max_items:
                    break

    return product_ids


def collect_rankings(
    limiter: RateLimiter,
    client: httpx.Client,
    list_types: list[str] | None = None,
    max_items: int = 100,
    timeout_sec: float = 30.0,
) -> tuple[int, list[int]]:
    """ランキングを収集"""
    if list_types is None:
        list_types = ["top", "top_creators"]

    snapshots_created = 0
    all_product_ids: set[int] = set()

    for lt in list_types:
        log(f"  Fetching {lt} ranking...")
        url = RANKING_URLS.get(lt)
        if not url:
            log(f"  [warn] Unknown list type: {lt}")
            continue

        limiter.wait()
        try:
            r = client.get(url, timeout=timeout_sec)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            log(f"  [error] HTTP {e.response.status_code}")
            continue

        product_ids = extract_product_ids_from_showcase(r.text, max_items=max_items)
        all_product_ids.update(product_ids)

        list_hash = compute_list_hash(product_ids)
        snapshot_id, is_new = save_ranking_snapshot(lt, product_ids, list_hash)

        if is_new:
            snapshots_created += 1
            log(f"  NEW snapshot for {lt}: {len(product_ids)} items")
        else:
            log(f"  No change for {lt}")

    return snapshots_created, list(all_product_ids)


# ==================== メタデータ収集 ====================

@dataclass
class ProductMeta:
    """商品メタデータ"""
    product_id: int
    store_url: str
    title: str | None = None
    creator_id: int | None = None
    creator_name: str | None = None
    description: str | None = None
    price_amount: int | None = None
    price_currency: str = "JPY"
    sticker_type: str | None = None
    sticker_count: int | None = None


def extract_product_meta(html: str, url: str) -> ProductMeta:
    """商品ページHTMLからメタデータを抽出"""
    soup = BeautifulSoup(html, "lxml")

    # product_id抽出
    match = re.search(r"/stickershop/product/(\d+)", url)
    product_id = int(match.group(1)) if match else 0

    # タイトル（複数のセレクタを試行）
    title = None
    for selector in ["div.mdCMN38Item0lHead", "h3.mdCMN38Item01Ttl", ".mdCMN38Item01Ttl"]:
        title_el = soup.select_one(selector)
        if title_el:
            title = title_el.get_text(strip=True)
            break

    # 作者情報
    author_el = soup.select_one("a[href*='/stickershop/author/']")
    creator_name = author_el.get_text(strip=True) if author_el else None
    creator_id = None
    if author_el:
        href = author_el.get("href", "")
        match = re.search(r"/author/(\d+)", href)
        if match:
            creator_id = int(match.group(1))

    # 説明
    desc_el = soup.select_one("p.mdCMN38Item01Txt")
    description = desc_el.get_text(strip=True) if desc_el else None

    # 価格
    price_el = soup.select_one("p.mdCMN38Item01Price")
    price_amount = None
    if price_el:
        price_text = price_el.get_text(strip=True)
        match = re.search(r"([\d,]+)", price_text)
        if match:
            price_amount = int(match.group(1).replace(",", ""))

    # スタンプタイプ
    sticker_type = "static"
    if soup.select_one("[data-type='animation']") or "アニメーション" in (description or ""):
        sticker_type = "animation"
    elif soup.select_one("[data-type='popup']") or "ポップアップ" in (description or ""):
        sticker_type = "popup"
    elif soup.select_one("[data-type='sound']") or "サウンド" in (description or ""):
        sticker_type = "sound"

    # スタンプ数
    sticker_count = None
    lis = soup.select(".FnStickerList li[data-preview]")
    if lis:
        sticker_count = len(lis)

    return ProductMeta(
        product_id=product_id,
        store_url=url,
        title=title,
        creator_id=creator_id,
        creator_name=creator_name,
        description=description,
        price_amount=price_amount,
        price_currency="JPY",
        sticker_type=sticker_type,
        sticker_count=sticker_count,
    )


def collect_metadata(
    limiter: RateLimiter,
    client: httpx.Client,
    product_ids: list[int] | None = None,
    limit: int = 50,
    timeout_sec: float = 30.0,
) -> int:
    """メタデータを収集"""
    if product_ids is None:
        product_ids = get_products_without_meta(limit=limit)

    if not product_ids:
        log("  No products need metadata collection")
        return 0

    log(f"  Collecting metadata for {len(product_ids)} products...")
    collected = 0

    for pid in product_ids:
        try:
            url = f"https://store.line.me/stickershop/product/{pid}/ja"
            limiter.wait()
            r = client.get(url, timeout=timeout_sec)
            r.raise_for_status()

            meta = extract_product_meta(r.text, url)
            upsert_product_meta(
                product_id=meta.product_id,
                store_url=meta.store_url,
                title=meta.title,
                creator_id=meta.creator_id,
                creator_name=meta.creator_name,
                description=meta.description,
                price_amount=meta.price_amount,
                price_currency=meta.price_currency,
                sticker_type=meta.sticker_type,
                sticker_count=meta.sticker_count,
            )
            collected += 1
            log(f"    [{collected}/{len(product_ids)}] {meta.title or pid}")
        except Exception as e:
            log(f"  [error] product/{pid}: {e}")

    return collected


# ==================== 特徴抽出 ====================

def extract_sticker_previews(html: str) -> list[dict]:
    """商品ページからスタンププレビュー情報を抽出"""
    soup = BeautifulSoup(html, "lxml")
    lis = soup.select(".FnStickerList li[data-preview]")

    previews = []
    for idx, li in enumerate(lis):
        raw = li.get("data-preview")
        if not raw or not isinstance(raw, str):
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        sticker_id = data.get("id")
        if not sticker_id:
            continue

        previews.append({
            "sticker_id": str(sticker_id),
            "idx": idx,
            "static_url": data.get("staticUrl"),
            "animation_url": data.get("animationUrl"),
            "popup_url": data.get("popupUrl"),
        })

    return previews


def analyze_product_features(
    limiter: RateLimiter,
    client: httpx.Client,
    product_id: int,
    out_dir: Path | None = None,
    timeout_sec: float = 30.0,
    use_gemini: bool = False,
    gemini_limit: int = 5,
    analyzer_type: str | None = None,
    ai_limit: int | None = None,
) -> int:
    """商品の特徴を抽出

    Args:
        use_gemini: Geminiで画像内容を分析するか（後方互換）
        gemini_limit: Gemini分析する最大スタンプ数（後方互換）
        analyzer_type: 使用するAIアナライザ ("claude", "gemini", None)
        ai_limit: AI分析する最大スタンプ数
    """
    from PIL import Image
    import io

    # 後方互換性: use_gemini が True なら analyzer_type を gemini に
    if analyzer_type is None and use_gemini:
        analyzer_type = "gemini"
    if ai_limit is None:
        ai_limit = gemini_limit

    url = f"https://store.line.me/stickershop/product/{product_id}/ja"
    limiter.wait()

    try:
        r = client.get(url, timeout=timeout_sec)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        log(f"  [error] HTTP {e.response.status_code}")
        return 0

    previews = extract_sticker_previews(r.text)
    log(f"  Found {len(previews)} stickers in product/{product_id}")

    # AI分析の準備
    ai_analyzer = None
    if analyzer_type:
        try:
            from .image_analyzer import get_analyzer
        except ImportError:
            from image_analyzer import get_analyzer
        ai_analyzer = get_analyzer(analyzer_type)
        log(f"  AI analysis: {analyzer_type} (limit: {ai_limit})")

    processed = 0
    ai_analyzed = 0
    all_features = []

    for preview in previews:
        img_url = preview.get("static_url") or preview.get("animation_url") or preview.get("popup_url")
        if not img_url:
            continue

        try:
            limiter.wait()
            r = client.get(img_url, timeout=timeout_sec)
            r.raise_for_status()
            img_data = r.content

            # 画像を解析
            img = Image.open(io.BytesIO(img_data))
            width, height = img.size

            # 透明度チェック
            has_transparency = False
            transparency_ratio = 0.0
            if img.mode in ("RGBA", "LA"):
                alpha = img.getchannel("A")
                alpha_data = list(alpha.getdata())
                transparent_pixels = sum(1 for a in alpha_data if a < 128)
                total_pixels = len(alpha_data)
                has_transparency = transparent_pixels > 0
                transparency_ratio = transparent_pixels / total_pixels if total_pixels > 0 else 0.0

            # 色分析
            img_rgb = img.convert("RGB")
            colors = img_rgb.getcolors(maxcolors=10000)
            num_colors = len(colors) if colors else 10000

            features = {
                "sticker_id": preview["sticker_id"],
                "product_id": product_id,
                "numeric": {
                    "width": width,
                    "height": height,
                    "has_transparency": has_transparency,
                    "transparency_ratio": transparency_ratio,
                    "num_colors": num_colors,
                    "file_size_bytes": len(img_data),
                }
            }

            # AI分析（制限内の場合）
            if ai_analyzer and ai_analyzed < ai_limit:
                try:
                    ai_result = ai_analyzer.analyze_image_from_url(img_url, client, timeout_sec)
                    features["ai_analysis"] = ai_result.to_dict()
                    ai_analyzed += 1
                    log(f"    [{analyzer_type}] {preview['sticker_id']}: {ai_result.text_intent or ai_result.expression or 'analyzed'}")
                except Exception as e:
                    log(f"    [{analyzer_type} error] {preview['sticker_id']}: {e}")

            upsert_sticker_features(
                sticker_id=preview["sticker_id"],
                product_id=product_id,
                features_json=features,
            )

            all_features.append(features)
            processed += 1

        except Exception as e:
            log(f"  [error] sticker {preview['sticker_id']}: {e}")

    # 商品全体の特徴を集約
    if all_features:
        pack_features = aggregate_features(all_features, analyzer_type=analyzer_type)
        upsert_product_features(product_id, pack_features)

    return processed


def aggregate_features(features: list[dict], analyzer_type: str | None = None, use_gemini: bool = False) -> dict:
    """スタンプ特徴を商品単位で集約

    Args:
        analyzer_type: 使用したAIアナライザ ("claude", "gemini", None)
        use_gemini: 後方互換用
    """
    if not features:
        return {}

    # 後方互換
    if analyzer_type is None and use_gemini:
        analyzer_type = "gemini"

    transparencies = []
    color_counts = []

    for f in features:
        numeric = f.get("numeric", {})
        if "transparency_ratio" in numeric:
            transparencies.append(numeric["transparency_ratio"])
        if "num_colors" in numeric:
            color_counts.append(numeric["num_colors"])

    result = {
        "sticker_count": len(features),
        "avg_transparency_ratio": sum(transparencies) / len(transparencies) if transparencies else 0,
        "avg_color_count": sum(color_counts) / len(color_counts) if color_counts else 0,
    }

    # AI分析結果を集約
    if analyzer_type:
        from collections import Counter

        expressions = []
        poses = []
        intents = []
        moods = []
        styles = []
        all_tags = []
        texts = []

        for f in features:
            # 新形式 "ai_analysis" または後方互換 "gemini"
            ai_data = f.get("ai_analysis") or f.get("gemini", {})
            if not ai_data:
                continue

            if ai_data.get("expression"):
                expressions.append(ai_data["expression"])
            if ai_data.get("pose"):
                poses.append(ai_data["pose"])
            if ai_data.get("text_intent"):
                intents.append(ai_data["text_intent"])
            if ai_data.get("mood"):
                moods.append(ai_data["mood"])
            if ai_data.get("character_style"):
                styles.append(ai_data["character_style"])
            if ai_data.get("tags"):
                all_tags.extend(ai_data["tags"])
            if ai_data.get("text_content"):
                texts.append(ai_data["text_content"])

        def top_items(items: list, n: int = 3) -> list:
            if not items:
                return []
            counts = Counter(items)
            return [item for item, _ in counts.most_common(n)]

        result["ai_summary"] = {
            "analyzer": analyzer_type,
            "analyzed_count": sum(1 for f in features if f.get("ai_analysis") or f.get("gemini")),
            "top_expressions": top_items(expressions),
            "top_poses": top_items(poses),
            "top_intents": top_items(intents),
            "top_moods": top_items(moods),
            "character_styles": top_items(styles),
            "common_tags": top_items(all_tags, 10),
            "sample_texts": texts[:5],
            "has_text_ratio": sum(1 for f in features if (f.get("ai_analysis") or f.get("gemini", {})).get("has_text")) / len(features) if features else 0,
        }

    return result


# ==================== インタラクティブ選択 ====================

def interactive_select_products() -> list[int]:
    """分析対象の商品をインタラクティブに選択"""
    products = list_products_for_analysis(analyzed=False, limit=100)

    if not products:
        log("No products available for analysis")
        return []

    print("\n=== 分析対象の商品を選択 ===")
    print(f"未分析の商品: {len(products)}件\n")

    for i, p in enumerate(products[:20], 1):
        status = "[analyzed]" if p.get("feature_analyzed_at") else "[pending]"
        title = p.get("title", "N/A")[:30]
        creator = p.get("creator_name", "N/A")[:15]
        print(f"  {i:2d}. {status} {p['product_id']:10d} | {title} | {creator}")

    print("\n選択方法:")
    print("  - 番号をカンマ区切りで入力 (例: 1,3,5)")
    print("  - 'all' で全て選択")
    print("  - 'q' でキャンセル")

    selection = input("\n選択: ").strip()

    if selection.lower() == "q":
        return []
    if selection.lower() == "all":
        return [p["product_id"] for p in products[:20]]

    try:
        indices = [int(x.strip()) - 1 for x in selection.split(",")]
        return [products[i]["product_id"] for i in indices if 0 <= i < len(products)]
    except (ValueError, IndexError):
        log("Invalid selection")
        return []


# ==================== URL指定収集 ====================

def extract_creator_id_from_url(url: str) -> int | None:
    """クリエイターURLからIDを抽出"""
    match = re.search(r"/stickershop/author/(\d+)", url)
    return int(match.group(1)) if match else None


def extract_product_id_from_url(url: str) -> int | None:
    """スタンプURLからIDを抽出"""
    match = re.search(r"/stickershop/product/(\d+)", url)
    return int(match.group(1)) if match else None


def fetch_creator_products(
    limiter: RateLimiter,
    client: httpx.Client,
    creator_id: int,
    max_pages: int = 10,
    timeout_sec: float = 30.0,
) -> list[int]:
    """クリエイターの全スタンプIDを取得"""
    product_ids: list[int] = []
    page = 1

    while page <= max_pages:
        url = f"https://store.line.me/stickershop/author/{creator_id}/ja?page={page}"
        limiter.wait()

        try:
            r = client.get(url, timeout=timeout_sec)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            log(f"  [error] HTTP {e.response.status_code}")
            break

        soup = BeautifulSoup(r.text, "lxml")
        found_on_page = []

        for a in soup.select("a[href*='/stickershop/product/']"):
            href = a.get("href", "")
            match = re.search(r"/stickershop/product/(\d+)", href)
            if match:
                pid = int(match.group(1))
                if pid not in product_ids and pid not in found_on_page:
                    found_on_page.append(pid)

        if not found_on_page:
            break

        product_ids.extend(found_on_page)
        log(f"  Page {page}: found {len(found_on_page)} products")
        page += 1

    return product_ids


def collect_by_url(
    limiter: RateLimiter,
    client: httpx.Client,
    url: str,
    collect_meta: bool = True,
    timeout_sec: float = 30.0,
) -> dict:
    """URL指定でデータを収集"""
    result = {
        "url": url,
        "type": None,
        "products_found": 0,
        "meta_collected": 0,
        "product_ids": [],
    }

    # クリエイターURL
    creator_id = extract_creator_id_from_url(url)
    if creator_id:
        result["type"] = "creator"
        result["creator_id"] = creator_id
        log(f"Fetching products from creator/{creator_id}...")

        product_ids = fetch_creator_products(limiter, client, creator_id, timeout_sec=timeout_sec)
        result["products_found"] = len(product_ids)
        result["product_ids"] = product_ids

        # DBに登録
        try:
            from .database import get_connection
        except ImportError:
            from database import get_connection

        for pid in product_ids:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO products_meta (product_id, store_url, creator_id)
                VALUES (?, ?, ?)
                """,
                (pid, f"https://store.line.me/stickershop/product/{pid}/ja", creator_id)
            )
            conn.commit()
            conn.close()

        if collect_meta and product_ids:
            log(f"Collecting metadata for {len(product_ids)} products...")
            result["meta_collected"] = collect_metadata(limiter, client, product_ids, timeout_sec=timeout_sec)

        return result

    # スタンプURL
    product_id = extract_product_id_from_url(url)
    if product_id:
        result["type"] = "product"
        result["product_id"] = product_id
        result["products_found"] = 1
        result["product_ids"] = [product_id]
        log(f"Fetching product/{product_id}...")

        if collect_meta:
            result["meta_collected"] = collect_metadata(limiter, client, [product_id], timeout_sec=timeout_sec)

        return result

    result["error"] = "Unknown URL format"
    return result


# ==================== CLI ====================

def cmd_collect(args: argparse.Namespace) -> None:
    """ランキング＋メタデータを収集"""
    init_database()
    limiter = RateLimiter(min_interval_sec=args.min_interval_sec)

    with httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True) as client:
        log("[step 1/2] Collecting rankings...")
        snapshots, product_ids = collect_rankings(
            limiter, client, max_items=args.max_items
        )
        log(f"  Created {snapshots} snapshots, found {len(product_ids)} products")

        log("[step 2/2] Collecting metadata...")
        meta_count = collect_metadata(limiter, client, limit=args.meta_limit)
        log(f"  Collected metadata for {meta_count} products")


def cmd_fetch_url(args: argparse.Namespace) -> None:
    """URL指定でデータを収集"""
    init_database()
    limiter = RateLimiter(min_interval_sec=args.min_interval_sec)

    with httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True) as client:
        result = collect_by_url(
            limiter, client, args.url,
            collect_meta=not args.skip_meta,
        )

        if result.get("error"):
            log(f"[error] {result['error']}")
            return

        log(f"[result] Type: {result['type']}")
        log(f"[result] Products found: {result['products_found']}")
        log(f"[result] Metadata collected: {result['meta_collected']}")

        if args.analyze and result["product_ids"]:
            # アナライザ決定（新形式 --analyzer 優先、後方互換 --gemini）
            analyzer_type = getattr(args, 'analyzer', None)
            if analyzer_type is None and getattr(args, 'gemini', False):
                analyzer_type = "gemini"
            ai_limit = getattr(args, 'ai_limit', None) or getattr(args, 'gemini_limit', 5)

            log("[step] Analyzing features...")
            if analyzer_type:
                log(f"  AI analyzer: {analyzer_type} (limit: {ai_limit})")
            for pid in result["product_ids"]:
                count = analyze_product_features(
                    limiter, client, pid,
                    analyzer_type=analyzer_type,
                    ai_limit=ai_limit,
                )
                log(f"  product/{pid}: {count} stickers analyzed")


def cmd_analyze(args: argparse.Namespace) -> None:
    """特徴抽出を実行"""
    init_database()
    limiter = RateLimiter(min_interval_sec=args.min_interval_sec)

    # 対象商品を決定
    if args.interactive:
        product_ids = interactive_select_products()
    elif args.product_ids:
        product_ids = [int(x) for x in args.product_ids.split(",")]
    else:
        product_ids = get_products_without_features(limit=args.limit)

    if not product_ids:
        log("No products to analyze")
        return

    # アナライザ決定（新形式 --analyzer 優先、後方互換 --gemini）
    analyzer_type = getattr(args, 'analyzer', None)
    if analyzer_type is None and getattr(args, 'gemini', False):
        analyzer_type = "gemini"
    ai_limit = getattr(args, 'ai_limit', None) or getattr(args, 'gemini_limit', 5)

    log(f"Analyzing {len(product_ids)} products...")
    if analyzer_type:
        log(f"  AI analyzer: {analyzer_type} (limit per product: {ai_limit})")

    with httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True) as client:
        for i, pid in enumerate(product_ids, 1):
            log(f"[{i}/{len(product_ids)}] product/{pid}")
            count = analyze_product_features(
                limiter, client, pid,
                analyzer_type=analyzer_type,
                ai_limit=ai_limit,
            )
            log(f"  Processed {count} stickers")


def cmd_stats(args: argparse.Namespace) -> None:
    """統計を表示"""
    init_database()
    stats = get_trend_stats()

    print("\n=== Trend Collection Stats ===")
    print(f"  Ranking snapshots: {stats['snapshots']}")
    print(f"  Products: {stats['products']}")
    print(f"  Products with meta: {stats['products_with_meta']}")
    print(f"  Products analyzed: {stats['products_with_features']}")
    print(f"  Stickers analyzed: {stats['stickers_analyzed']}")
    print(f"  Stickers with embeddings: {stats['stickers_with_embeddings']}")
    print(f"  Knowledge entries: {stats['knowledge_entries']}")


def cmd_list(args: argparse.Namespace) -> None:
    """商品リストを表示"""
    init_database()

    analyzed = None
    if args.filter == "analyzed":
        analyzed = True
    elif args.filter == "pending":
        analyzed = False

    products = list_products_for_analysis(analyzed=analyzed, limit=args.limit)

    print(f"\n=== Products ({args.filter}) ===")
    for p in products:
        status = "[analyzed]" if p.get("feature_analyzed_at") else "[pending]"
        title = p.get("title", "N/A")[:40]
        creator = p.get("creator_name", "N/A")[:20]
        print(f"  {status} {p['product_id']:10d} | {title} | {creator}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="trend_collector",
        description="LINE STORE Trend Collector",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # collect
    s1 = sub.add_parser("collect", help="Collect rankings and metadata")
    s1.add_argument("--max-items", type=int, default=100)
    s1.add_argument("--meta-limit", type=int, default=50)
    s1.add_argument("--min-interval-sec", type=float, default=1.0)
    s1.set_defaults(func=cmd_collect)

    # fetch (URL指定)
    s_fetch = sub.add_parser("fetch", help="Fetch data by URL (creator or product)")
    s_fetch.add_argument("url", help="Creator URL or Product URL")
    s_fetch.add_argument("--skip-meta", action="store_true", help="Skip metadata collection")
    s_fetch.add_argument("--analyze", "-a", action="store_true", help="Also analyze features")
    s_fetch.add_argument("--analyzer", choices=["claude", "gemini"], help="AI analyzer to use")
    s_fetch.add_argument("--gemini", "-g", action="store_true", help="[Deprecated] Use --analyzer gemini")
    s_fetch.add_argument("--ai-limit", type=int, default=5, help="Max stickers to analyze with AI per product")
    s_fetch.add_argument("--gemini-limit", type=int, default=5, help="[Deprecated] Use --ai-limit")
    s_fetch.add_argument("--min-interval-sec", type=float, default=1.0)
    s_fetch.set_defaults(func=cmd_fetch_url)

    # analyze
    s2 = sub.add_parser("analyze", help="Analyze product features")
    s2.add_argument("--product-ids", help="Comma-separated product IDs")
    s2.add_argument("--limit", type=int, default=10)
    s2.add_argument("--interactive", "-i", action="store_true", help="Interactive selection")
    s2.add_argument("--analyzer", choices=["claude", "gemini"], help="AI analyzer to use")
    s2.add_argument("--gemini", "-g", action="store_true", help="[Deprecated] Use --analyzer gemini")
    s2.add_argument("--ai-limit", type=int, default=5, help="Max stickers to analyze with AI per product")
    s2.add_argument("--gemini-limit", type=int, default=5, help="[Deprecated] Use --ai-limit")
    s2.add_argument("--min-interval-sec", type=float, default=1.0)
    s2.set_defaults(func=cmd_analyze)

    # stats
    s3 = sub.add_parser("stats", help="Show statistics")
    s3.set_defaults(func=cmd_stats)

    # list
    s4 = sub.add_parser("list", help="List products")
    s4.add_argument("--filter", choices=["all", "analyzed", "pending"], default="all")
    s4.add_argument("--limit", type=int, default=50)
    s4.set_defaults(func=cmd_list)

    return p


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
