from mcp.server.fastmcp import FastMCP
import httpx
import os
from dotenv import load_dotenv
load_dotenv()

mcp = FastMCP(name="WeatherServer", host="127.0.0.1", port=3001)


@mcp.tool()
async def get_weather(city: str) -> dict:
    """
        使用 OPENWEATHERMAP API 根据城市名搜索相应城市的天气将输入的城市名翻译为英文

        参数:
            city (str): 城市，如 "BeiJing"，将输入的城市名翻译为英文

        返回:
            str: JSON 字符串，包含城市、天气、温度
    """
    api_key = "dfded8c8ffe7ea9e34f9f072bd6e02c7"

    base_url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric",
        "lang": "zh_cn"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(base_url, params=params)
            response.raise_for_status()  # Raise an exception for bad status codes
            data = response.json()

            description = data["weather"][0]["description"]
            temp = data["main"]["temp"]

            # return {"city": city, "description": description, "temperature": temp}
            return {
                "city": city,
                "description": description,
                "temperature": temp
            }
        except httpx.RequestError as e:
            return {"Error fetching weather data": e}
        except KeyError:
            return {"Error: Could not parse weather data for": city}


if __name__ == "__main__":
    mcp.run(transport="sse")
