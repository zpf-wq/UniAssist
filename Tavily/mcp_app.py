from mcp.server.fastmcp import FastMCP
import httpx
import os
import requests
from dotenv import load_dotenv
load_dotenv()

mcp = FastMCP(name="WeatherServer", host="127.0.0.1", port=3002)


@mcp.tool()
async def tavily_search(query: str) -> dict:
    """
    使用 Tavily API 根据问题搜索问题回答，返回前5条标题、描述和链接。

    参数:
        query (str): 关键词，如 "MCP是什么"

    返回:
        str: JSON 字符串，包含问题的回答和回答的链接，同时将回答的内容翻译为中文
    """
    url = "https://api.tavily.com/search"
    headers = {"Content-Type": "application/json"}
    payload = {
        "api_key": "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",
        "query": query,
        "search_depth": "basic",
        "include_answer": True,
        "include_sources": True,
        "max_results": 5
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()

        answer = data.get("answer", "No answer found.")
        sources = data.get("results", [])
        source_links = "\n".join([f"- [{src['title']}]({src['url']})" for src in sources[:3]])

        # return f"**Answer:**\n{answer}\n\n**Sources:**\n{source_links}"
        print(answer)
        return {
            "answer": answer,
            "sources": source_links,
        }
    except Exception as e:
        return {"Search failed": {str(e)}}


if __name__ == "__main__":
    mcp.run(transport="sse")
