import logging
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import click
from dotenv import load_dotenv

from agent import TavilyAgent
from A2A.custom_types import AgentCapabilities, AgentCard, AgentSkill, MissingAPIKeyError
from A2A.push_notification_auth import PushNotificationSenderAuth
from A2A.server import A2AServer
from task_manager import AgentTaskManager

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.command()
@click.option("--host", "host", default="localhost")
@click.option("--port", "port", default=8002)
def main(host, port):
    """Starts the Currency Agent server."""
    try:
        if not os.getenv("DEEPSEEK_API_KEY"):
            raise MissingAPIKeyError("DEEPSEEK_API_KEY environment variable not set.")

        capabilities = AgentCapabilities(streaming=True, pushNotifications=False)
        skill = AgentSkill(
            id="tavily_search",
            name="Tavily Search Tool",
            description="Performs web searches using the Tavily API and returns summarized results with sources.",
            tags=["search", "web", "tavily"],
            examples=["Search for MCP protocol", "Find latest AI research papers"],
        )

        agent_card = AgentCard(
            name="Tavily Agent",
            description="Helps users perform factual and informational searches using Tavily API.",
            url=f"http://{host}:{port}/",
            version="1.0.0",
            defaultInputModes=["text/plain", "application/json"],
            defaultOutputModes=["application/json"],
            capabilities=capabilities,
            skills=[skill],
        )

        notification_sender_auth = PushNotificationSenderAuth()
        notification_sender_auth.generate_jwk()
        server = A2AServer(
            agent_card=agent_card,
            task_manager=AgentTaskManager(
                agent=TavilyAgent(), notification_sender_auth=notification_sender_auth
            ),
            host=host,
            port=port,
        )

        server.app.add_route(
            "/.well-known/jwks.json",
            notification_sender_auth.handle_jwks_endpoint,
            methods=["GET"],
        )

        logger.info(f"Starting server on {host}:{port}")
        server.start()
    except MissingAPIKeyError as e:
        logger.error(f"Error: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        exit(1)


if __name__ == "__main__":
    main()
