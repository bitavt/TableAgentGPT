from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
# custom imports
from logging_configs import *
from pydantic_models import SqlEvent, DataLoadEvent, ChatState
from manage_multi_agent_states import (
    handle_user_input,
    load_data,
    build_query,
    execute_query,
    post_execution,
    route_to_next_step
)



# Build the multi-agent state graph.
graph_builder = StateGraph(ChatState)
graph_builder.add_node("handle_user_input", handle_user_input)
graph_builder.add_node("load_data", load_data)
graph_builder.add_node("build_query", build_query)
graph_builder.add_node("execute_query", execute_query)
graph_builder.add_node("post_execution", post_execution)

# Define edges between nodes.
# start at handle_user_input
graph_builder.add_edge(START, "handle_user_input")
graph_builder.add_conditional_edges(
    "handle_user_input",
    route_to_next_step,
    {
        "handle_user_input": "handle_user_input",
        "load_data": "load_data",
        "build_query": "build_query",
        "END": END,
    },
)
# after loading the data return to handle_user_input for next question
graph_builder.add_edge("load_data", "handle_user_input")
# If query generation fails, ask for more details (handle_user_input).
# If the generated query is valid, execute it (execute_query).
graph_builder.add_conditional_edges(
    "build_query",
    route_to_next_step,
    {"handle_user_input": "handle_user_input", "execute_query": "execute_query"},
)
# If execution fails, retry query generation (build_query)
# If execution succeeds, processe results (post_execution)
# If retries fail too many times, return to handle_user_input to ask the user for help
graph_builder.add_conditional_edges(
    "execute_query",
    route_to_next_step,
    {
        "build_query": "build_query",
        "post_execution": "post_execution",
        "handle_user_input": "handle_user_input",
    },
)
# After displaying results, wait for the next question
graph_builder.add_edge("post_execution", "handle_user_input")
# finalize the workflow
graph = graph_builder.compile()  # config={"recursion_limit": 1000})

# (Optional) Display the graph as an image.
# import io
# from PIL import Image
# image = Image.open(io.BytesIO(graph.get_graph().draw_mermaid_png()))
# image.show()

# Initialize state with an introduction message
chat_state = ChatState(
    conversation_history=[
        SystemMessage(
            content="Welcome to TableAgentGPT! This tool enables you to interact with your tabular data "
                    "by generating queries on your behalf.\n\n"
                    "To get started, please load your data and its metadata using the command:\n"
                    "/load <file_path> <table_columns_description>\n\n"
                    "Once your data is loaded, feel free to ask any questions, and I’ll retrieve insights for you.\n"
                    "To exit the system, simply type /q."
        )
    ],
)
# begin the agent loop
graph.invoke(chat_state)
