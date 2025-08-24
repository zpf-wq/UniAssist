import logging
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import click
from dotenv import load_dotenv

from agent import WeatherAgent
from A2A.custom_types import AgentCapabilities, AgentCard, AgentSkill, MissingAPIKeyError
from A2A.push_notification_auth import PushNotificationSenderAuth
from A2A.server import A2AServer
from task_manager import AgentTaskManager

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.command()
@click.option("--host", "host", default="localhost")
@click.option("--port", "port", default=8001)
def main(host, port):
    """Starts the Currency Agent server."""
    try:
        if not os.getenv("DEEPSEEK_API_KEY"):
            raise MissingAPIKeyError("DEEPSEEK_API_KEY environment variable not set.")

        capabilities = AgentCapabilities(streaming=True, pushNotifications=False)
        skill = AgentSkill(
            id="query_weather",
            name="Weather Query Tool",
            description="Provides current weather for a given city",
            tags=["weather", "temperature"],
            examples=["What's the weather in BeiJing?"],
        )
        agent_card = AgentCard(
            name="Weather Agent",
            description="Helps users get current weather conditions and forecasts for specific cities",
            url=f"http://{host}:{port}/",
            version="1.0.0",
            defaultInputModes=WeatherAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=WeatherAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )

        notification_sender_auth = PushNotificationSenderAuth()
        notification_sender_auth.generate_jwk()
        server = A2AServer(
            agent_card=agent_card,
            task_manager=AgentTaskManager(
                agent=WeatherAgent(), notification_sender_auth=notification_sender_auth
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
