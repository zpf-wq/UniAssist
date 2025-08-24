import typer
import redis
import uuid
from langgraph.checkpoint.redis import RedisSaver
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, END
from host_agent import HostAgent, build_react_agent
from langchain_deepseek import ChatDeepSeek
from langchain_core.prompts import ChatPromptTemplate
from typing import List, Any, Tuple, Dict


class DummyReactAgent:
    """一个测试用的 react_agent，每次 invoke 都返回固定回答。"""
    def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        # 读取 messages 历史（可选）
        messages = input_data.get("messages", [])

        # 返回固定的 AIMessage
        ai_msg = AIMessage(content="这是固定返回的测试结果")
        return {"messages": messages + [ai_msg]}


def make_planner():
    llm = ChatDeepSeek(
        model="deepseek-chat"
    )
    system = (
        "你是一个任务分解器。"
        "你的目标是把用户的问题拆解成**最小功能级别的任务**，但不要过度细化为人类的操作步骤。"
        "规则："
        "1. **合并不同类别的查询**：如果用户提出多个独立的查询（如查天气、查汇率、查新闻等），没有前后依赖关系，必须合并为一个任务。"
        "   - 例子：用户说“查上海天气，再查美元汇率”，你要拆解为："
        "     - “查询上海天气和美元兑人民币汇率”。"
        "2. **分解同类别的查询**：如果用户在同一类问题上提出多个对象（如多个城市的天气、多个币种的汇率），则需要拆分成多个任务。"
        "   - 例子：用户说“查北京和上海的天气”，你要拆解为："
        "     - “查询北京天气”；“查询上海天气”。"
        "   - 例子：用户说“查美元和欧元的汇率”，你要拆解为："
        "     - “查询美元兑人民币汇率”；“查询欧元兑人民币汇率”。"
        "3. **功能级别拆解**：只保留可以直接交给代理执行的任务。"
        "   - ✅ 例子：“查询上海天气和美元兑人民币汇率”。"
        "   - ❌ 不要输出“打开网站”、“输入上海”、“点击查询”。"
        "4. **保持顺序**：只有在任务确实有前后依赖时才分开拆解；否则按照规则 1 和 2 合理合并或拆分。"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("user", "{question}")
    ])
    chain = prompt | llm
    return chain


class StepState(dict):
    steps: List[str]
    current: int
    history: List[Any]
    messages: List[Any]   # 保存对话历史（用于把上一步结果带入下一步）


def executor_node(state: StepState, react_agent):
    """把当前 step 串行发送给 Host Agent（react_agent），等待其返回后再继续。"""
    step_idx = state["current"]
    step = state["steps"][step_idx]
    # print("step: ", step)
    print(f"\n[Planner] 子任务 {step_idx+1}/{len(state['steps'])}: {step}")

    # 组合历史+当前子任务，一起传给 host agent，保证上下文衔接
    history = state.get("history", [])
    # print("history: ", history)
    user_turn = {"role": "user", "content": step}
    # print("history + [user_turn]: ", history + [user_turn])

    result = react_agent.invoke({"messages": history + [user_turn]})

    # 取最后一条 AI 回复
    ai_msg = result["messages"][-1]
    # print("ai_msg: ", ai_msg)
    ai_text = ai_msg.content if isinstance(ai_msg, AIMessage) else getattr(ai_msg, "content", str(ai_msg))
    print(f"[HostAgent] 子任务 {step_idx+1} 完成")

    # 把这轮对话追加回状态，方便下一步继续用到上下文
    state["history"] = history + [ai_msg]
    # print("state: ", state)

    # 进入下一步
    state["current"] += 1
    return state


def build_serial_graph(react_agent):
    """先 planner 拆解，再 executor 串行逐步调用 host agent。"""
    planner = make_planner()

    workflow = StateGraph(StepState)

    def plan_node(state: StepState):
        # 从消息里取用户原始问题
        last_msg = state["messages"][-1]

        question = last_msg.get("content", "") if isinstance(last_msg, dict) else getattr(last_msg, "content", "")
        # print("state: ", state)
        plan_reply = planner.invoke({"question": question})
        # print("plan_reply: ", plan_reply)
        plan_text = getattr(plan_reply, "content", str(plan_reply))
        # print("plan_text: ", plan_text)

        # 按行拆解步骤（去掉编号/点号/多余空格）
        steps = [s.strip().lstrip("0123456789.、)） ").rstrip() for s in plan_text.splitlines() if s.strip()]
        # print("steps: ", steps)
        state["steps"] = steps
        state["current"] = 0
        # print("state: ", state)
        return state

    workflow.add_node("planner", plan_node)
    workflow.add_node("executor", lambda s: executor_node(s, react_agent))

    # planner -> executor
    workflow.add_edge("planner", "executor")

    # executor -> executor（如果还有剩余步骤）
    workflow.add_conditional_edges(
        "executor",
        lambda s: "executor" if s["current"] < len(s["steps"]) else END
    )

    workflow.set_entry_point("planner")

    REDIS_URI = "redis://localhost:6379"
    checkpointer = None
    with RedisSaver.from_conn_string(REDIS_URI) as _checkpointer:
        _checkpointer.setup()
        checkpointer = _checkpointer
    return workflow.compile(checkpointer=checkpointer)


app = typer.Typer()


@app.command()
def run_agent(
    Currency_url: str = "http://localhost:8000",
    Weather_url: str = "http://localhost:8001",
    Tavily_Agent: str = "http://localhost:8002"
):
    """用户输入一次；Planner 拆步；每步顺序发给 Host Agent，逐步执行。"""
    # 1) 初始化 HostAgent（连接远端服务）
    host_agent = HostAgent([Currency_url, Weather_url, Tavily_Agent])
    host_agent.initialize()

    # 2) 用 HostAgent 构建可调用的 react_agent（真正负责路由到远端）
    react_agent = build_react_agent(host_agent)
    # react_agent = DummyReactAgent()

    # 3) 构建串行执行的图
    graph = build_serial_graph(react_agent)

    typer.echo(f"Host agent ready. Connected to: {Currency_url}")
    typer.echo(f"Host agent ready. Connected to: {Weather_url}")
    typer.echo(f"Host agent ready. Connected to: {Tavily_Agent}")
    typer.echo("Type 'quit' or 'exit' to stop.")

    config = {"configurable": {"thread_id": "cli-session"}}
    while True:
        user_msg = typer.prompt("\nUser")
        if user_msg.strip().lower() in ["quit", "exit", "bye"]:
            typer.echo("Goodbye!")
            break

        # 只需把用户的原始问题交给 graph；graph 内部会先拆解，再串行执行每个 step
        raw_result = graph.invoke(
            {"messages": [{"role": "user", "content": user_msg}]}, config)  # 你可以固定，也可以每次新建

        # 从 state["history"] 里提取所有 AIMessage
        final_texts = []
        if isinstance(raw_result, dict) and "history" in raw_result:
            for msg in raw_result["history"]:
                if isinstance(msg, AIMessage):
                    final_texts.append(msg.content)

        if final_texts:
            # 拼接成多行字符串
            final_text = "\n".join(final_texts)
        else:
            final_text = str(raw_result)

        typer.echo(f"\n[Final]\n{final_text}")


def main():
    app()


if __name__ == "__main__":
    main()
