from fastmcp import FastMCP

from tools.user_tools import create_user, identify, get_profile
from tools.topic_tools import start_topic, complete_topic
from tools.event_tools import log_event, store_code_artifact
from tools.capsule_tools import store_capsule, get_capsule
from tools.review_tools import store_review_answer
from tools.context_tools import get_agent_context
from tools.card_tools import create_cards_from_capsule, get_due_cards, log_card_attempt
from tools.mastery_tools import record_mastery, get_mastery_progress, get_next_focus

mcp = FastMCP("proof-forge")

mcp.tool()(create_user)
mcp.tool()(identify)
mcp.tool()(get_profile)
mcp.tool()(start_topic)
mcp.tool()(complete_topic)
mcp.tool()(log_event)
mcp.tool()(store_code_artifact)
mcp.tool()(store_capsule)
mcp.tool()(get_capsule)
mcp.tool()(store_review_answer)
mcp.tool()(get_agent_context)
mcp.tool()(create_cards_from_capsule)
mcp.tool()(get_due_cards)
mcp.tool()(log_card_attempt)
mcp.tool()(record_mastery)
mcp.tool()(get_mastery_progress)
mcp.tool()(get_next_focus)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
