"""
mcp_server.py - MAYA MCP Server
Exposes Corona chatbot tools as an MCP server any AI client can connect to.
Run: python mcp_server.py
"""

import os
import re
import sys
from dotenv import load_dotenv
load_dotenv()

from fastmcp import FastMCP

mcp = FastMCP(
    name="MAYA — Corona Toilet Intelligence",
    instructions=(
        "Tools for querying Corona toilet product data, customer reviews, "
        "weather, and web search. Built on 221 real customer reviews and "
        "product spec sheets for 49 Corona toilet products."
    )
)


@mcp.tool()
def get_weather(location: str) -> str:
    """Get current weather for any city. Example: 'Bogotá' or 'New York'."""
    import requests
    try:
        url = f"https://wttr.in/{location}?format=%C+%t+%h+humidity&lang=en"
        r = requests.get(url, timeout=5)
        return f"{location}: {r.text.strip()}"
    except Exception as e:
        return f"Weather unavailable: {e}"


@mcp.tool()
def web_search(query: str) -> str:
    """Search the web for real-time info — stock prices, news, current events."""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        if not results:
            return "No results found."
        return "\n".join([f"{r['title']}: {r['body']}" for r in results])
    except Exception as e:
        return f"Search failed: {e}"


@mcp.tool()
def query_corona_products(filter_description: str) -> str:
    """
    Query the Corona toilet product database using natural language.
    Examples: 'toilets with less than 3.8 Lpf', 'ADA compliant toilets', 'Nyren specifications'
    Returns matching product info from 221 reviews + spec sheets.
    """
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vs = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
    results = vs.similarity_search(filter_description, k=10)

    if not results:
        return "No matching products found."

    seen = set()
    output = []
    for doc in results:
        product = doc.metadata.get("product", "")
        if product and product not in seen and product.lower() not in ("unknown", "nan"):
            seen.add(product)
        output.append(doc.page_content[:300])

    return "\n\n---\n\n".join(output[:5])


@mcp.tool()
def generate_product_table(attributes: str) -> str:
    """
    Generate an HTML comparison table of Corona toilet products.
    attributes: comma-separated list e.g. 'water consumption, dimensions, ADA compliance'
    Returns an HTML table string.
    """
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vs = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
    results = vs.similarity_search(f"product specifications {attributes}", k=15)

    products = {}
    attr_list = [a.strip().lower() for a in re.sub(r'\s+and\s+', ', ', attributes, flags=re.IGNORECASE).split(",")]

    for doc in results:
        product = doc.metadata.get("product", "")
        if not product or product.lower() in ("unknown", "nan"):
            continue
        if product not in products:
            products[product] = {a: "-" for a in attr_list}
        text = doc.page_content.lower()

        if "water consumption" in attr_list or "lpf" in attr_list:
            match = re.search(r'(\d+[\.,]\d+)\s*(?:lpf|liters|litros|l/flush|gpf)', text)
            if match:
                products[product]["water consumption"] = match.group(1) + " Lpf"

        if "ada" in attr_list or "ada compliance" in attr_list:
            if "ada" in text:
                products[product]["ada"] = "Yes"
                products[product]["ada compliance"] = "Yes"

        if "dimensions" in attr_list:
            match = re.search(r'(\d+)\s*[xX]\s*(\d+)\s*[xX]\s*(\d+)', text)
            if match:
                products[product]["dimensions"] = f"{match.group(1)}x{match.group(2)}x{match.group(3)} cm"

        if "flush type" in attr_list or "flush" in attr_list:
            if "dual" in text:
                products[product]["flush type"] = "Dual Flush"
            elif "single" in text:
                products[product]["flush type"] = "Single Flush"

    if not products:
        return "<p>No product data found.</p>"

    cols = attr_list
    header = "<th>Product</th>" + "".join(f"<th>{c.title()}</th>" for c in cols)
    rows = ""
    for name, data in list(products.items())[:10]:
        cells = "".join(f"<td>{data.get(c, '-')}</td>" for c in cols)
        rows += f"<tr><td><strong>{name}</strong></td>{cells}</tr>"

    return f'<table border="1" cellpadding="6"><thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table>'


@mcp.tool()
def get_product_sentiment(product_name: str) -> str:
    """
    Get sentiment analysis for a specific Corona toilet product.
    Returns positive/negative/neutral review breakdown with key themes.
    """
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vs = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
    results = vs.similarity_search(f"{product_name} review sentiment", k=15)

    positive, negative, neutral = [], [], []
    for doc in results:
        sentiment = doc.metadata.get("sentiment", "").lower()
        if "positive" in sentiment:
            positive.append(doc.page_content[:150])
        elif "negative" in sentiment:
            negative.append(doc.page_content[:150])
        else:
            neutral.append(doc.page_content[:150])

    return (
        f"Product: {product_name}\n"
        f"Positive reviews: {len(positive)}\n"
        f"Negative reviews: {len(negative)}\n"
        f"Neutral reviews: {len(neutral)}\n\n"
        f"Sample positive: {positive[0] if positive else 'None'}\n\n"
        f"Sample negative: {negative[0] if negative else 'None'}"
    )


@mcp.tool()
def execute_code(code: str) -> str:
    """
    Execute Python code safely and return the output.
    Use for calculations, data analysis, statistics on review data.
    Blocked: os, sys, subprocess, file access, network calls.
    """
    import io, contextlib, traceback, math, statistics

    blocked = ["import os", "import sys", "import subprocess", "open(",
               "__import__", "shutil", "socket", "requests", "urllib"]
    for b in blocked:
        if b in code:
            return f"Blocked: '{b}' not allowed."

    safe_globals = {
        "__builtins__": {
            "print": print, "len": len, "range": range, "sum": sum,
            "min": min, "max": max, "abs": abs, "round": round,
            "sorted": sorted, "enumerate": enumerate, "zip": zip,
            "list": list, "dict": dict, "set": set, "tuple": tuple,
            "str": str, "int": int, "float": float, "bool": bool,
            "isinstance": isinstance, "type": type,
        },
        "math": math, "statistics": statistics,
    }

    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            exec(code, safe_globals)
        result = output.getvalue().strip()
        return result if result else "Executed (no output)."
    except Exception:
        return f"Error:\n{traceback.format_exc()}"


if __name__ == "__main__":
    print("Starting MAYA MCP Server...")
    print("Tools: get_weather, web_search, query_corona_products, generate_product_table, get_product_sentiment")
    print("Connect via Claude Desktop or any MCP client")
    mcp.run(transport="stdio")
