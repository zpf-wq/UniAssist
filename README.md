# UniAssist
# 🚀 OmniAgent Framework

**OmniAgent** is a multi-agent orchestration framework built on top of **A2A (Agent-to-Agent)** and **MCP (Model Context Protocol)**.
 It is designed to serve as a scalable **personal assistant system**, capable of breaking down complex tasks, distributing them across agents, and integrating results from external services.

------

## ✨ Features

- **Multi-protocol support**: Combines **A2A** for agent communication and **MCP** for tool/service integration.
- **Task decomposition**: The **Scheduler Agent** breaks down user queries into step-by-step subtasks.
- **Distributed orchestration**: The **Manager Agent** asynchronously dispatches subtasks to worker agents via A2A.
- **Service execution**: Worker Agents interact with external tools/services through MCP Servers.
- **Extensible**: Easily integrate new MCP Servers and Worker Agents to expand capabilities.

------

## 📦 Use Cases

- 🔍 **Search & aggregation**: Break a query into multiple searches → dispatch workers → call MCP search APIs → aggregate results.
- 📊 **Data pipeline**: Split into fetch, clean, analyze → parallelized across agents → report generation.
- 🤖 **Personal assistant**: Query weather, check calendar, fetch exchange rates → results combined in a single response.

------

## ⚙️ Quick Start

```
git clone https://github.com/zpf-wq/UniAssist.git
cd UniAssist

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python Weather/mcp_app.py
python Weather/agentpartner.py

python Currency/mcp_app.py
python Currency/agentpartner.py

python Tavily/mcp_app.py
python Tavily/agentpartner.py

python main_Agent.py
```

------

## 📚 Example

### Input

```
Check today’s weather in Beijing and also give me the USD to RMB exchange rate.
```

### Execution Flow

1. **Scheduler Agent** → splits into:
   - Get Beijing weather
   - Get USD → RMB exchange rate
2. **Manager Agent** → dispatches both tasks asynchronously
3. **Worker Agents** → call corresponding MCP Servers (weather API / FX API)
4. **Results aggregated → returned to user**

### Output

```
Beijing weather today: Cloudy, high 31°C, low 24°C.
USD to RMB exchange rate: 7.12.
```

------

## 🛠️ Roadmap

-  Core A2A + MCP orchestration
-  End-to-end task decomposition and execution
-  Pluggable MCP tool registry
-  Multi-turn task tracking with memory
-  Web UI & visualization dashboard

------

## 📜 License

MIT License © 2025
