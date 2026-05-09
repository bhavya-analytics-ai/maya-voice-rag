"""
scrape_corona.py - Scrape corona.co product listings and add to ChromaDB
Run: python scrape_corona.py
"""

import os
import re
import sys
from dotenv import load_dotenv
load_dotenv()

from playwright.sync_api import sync_playwright
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHROMA_DIR = "./chroma_db"
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

CATEGORY_URLS = [
    "https://www.corona.co/productos/sanitarios/sanitarios-individuales/c/sanitarios-individuales",
    "https://www.corona.co/productos/sanitarios/combos-sanitarios/c/combos-sanitarios",
]


def scroll_and_get_text(page):
    for i in range(10):
        page.evaluate(f"window.scrollTo(0, {(i+1) * 1000})")
        page.wait_for_timeout(800)
    return page.inner_text("body")


def parse_products_from_listing(text):
    """Extract (ref, name, price) tuples from listing page text."""
    products = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    for i, line in enumerate(lines):
        if line.startswith("Ref:"):
            ref = line.replace("Ref:", "").strip()
            name = lines[i + 1].strip() if i + 1 < len(lines) else ""
            # Price is usually 2 lines down — look for $ sign
            price = ""
            for j in range(i + 1, min(i + 5, len(lines))):
                if "$" in lines[j] or "AGREGAR" in lines[j] or "AVÍSAME" in lines[j]:
                    price = lines[j] if "$" in lines[j] else "Price not listed"
                    break
            if ref and name and not name.startswith("Ref:"):
                products.append((ref, name, price))

    return products


def scrape_product_page(page, ref, name, price):
    """Scrape individual product page for specs."""
    try:
        page.goto(f"https://www.corona.co/p/{ref}", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)
        text = page.inner_text("body")
        lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 3]

        # Find the relevant product section (skip nav)
        start = 0
        for i, l in enumerate(lines):
            if name[:15].lower() in l.lower() or ref in l:
                start = max(0, i - 2)
                break

        content = f"Product: {name}\nRef/SKU: {ref}\nPrice: {price}\nSource: corona.co\n\n"
        content += "\n".join(lines[start:start + 80])
        return content

    except Exception as e:
        print(f"    Failed to scrape {ref}: {e}")
        return f"Product: {name}\nRef/SKU: {ref}\nPrice: {price}\nSource: corona.co"


def main():
    all_docs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for cat_url in CATEGORY_URLS:
            print(f"\nScraping category: {cat_url}")
            page.goto(cat_url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(4000)
            text = scroll_and_get_text(page)

            products = parse_products_from_listing(text)
            print(f"  Found {len(products)} products")

            for ref, name, price in products:
                print(f"  → {name} ({ref}) {price}")
                content = scrape_product_page(page, ref, name, price)
                chunks = splitter.split_text(content)
                for chunk in chunks:
                    all_docs.append(Document(
                        page_content=chunk,
                        metadata={
                            "source": "corona.co website",
                            "type": "product_listing",
                            "product": name,
                            "sku": ref,
                            "price": price,
                        }
                    ))

        browser.close()

    print(f"\nTotal chunks scraped: {len(all_docs)}")

    if not all_docs:
        print("No products found — nothing to add.")
        return

    print("Adding to ChromaDB...")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vs = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
    vs.add_documents(all_docs)
    print(f"Done. Total chunks in DB: {vs._collection.count()}")


if __name__ == "__main__":
    main()
