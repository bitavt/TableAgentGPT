import os
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
import duckdb
from langchain_openai import ChatOpenAI

# custom imports
from pydantic_models import SqlEvent, DataLoadEvent, ChatState
from logging_configs import *
from constants import MAX_RETRY_SQL_GENERATION




# set up database connection
db_conn = duckdb.connect()

# set up LMM connection
model = ChatOpenAI(model="gpt-4o-mini")



######################
# Handle user input
######################
def handle_user_input(state: ChatState) -> ChatState:
    """
    Gets user input and processes special commands (/q to quit, /load to load data).
    Updates the state with the new user question or additional clarification details.

    Attributes:
        Takes in the ChatState object (which stores chat history, SQL details, and more)

    Returns:
        The updated ChatState after processing user input.
    """

    # print the last message in the conversation history (for debugging)
    logger.critical(state.conversation_history[-1].content)
    # get the user input prompt
    user_input = input(">>> User prompt (/q to quit, /load to load data): ")
    # if user requests to quit end the session
    if user_input.lower().startswith("/q"):
        state.next_step = "END"
    # if user requests to load the data, parse the command and set the next step to load_data
    elif user_input.lower().startswith("/load"):
        try:
            # Expected format: /load file_path table_columns_description
            _, file_path, table_columns_description = user_input.split()
            state.data_load_event = DataLoadEvent(
                file_path=file_path,
                table_columns_description=table_columns_description,
            )
            state.next_step = "load_data"
        except Exception:
            logger.exception(
                "Error parsing load command. Expected usage: /load <file_path>"
                "<table_columns_description>"
            )
            # ask the user to try again
            state.next_step = "handle_user_input"
    # ensure data is loaded before asking questions
    elif not state.table_schemas:
        # If no table schema is loaded, ask the user to load data first
        state.update_conversation_history(
            SystemMessage(
                content="Please load your data first using the command /load <file_path> "
                " <table_columns_description>."
            )
        )
        # ask the user to try again
        state.next_step = "handle_user_input"

    else:
        # if the user is asking question, add it to the conversation history
        state.update_conversation_history(HumanMessage(content=user_input))
        # Reset the SQL event state so that agent can generate a SQL query.
        state.sql_event = SqlEvent(user_question=user_input)
        state.next_step = "build_query"
    return state


###############
# Load data
###############
@log
def load_data(state: ChatState) -> ChatState:
    """
    Loads a CSV file into DuckDB, reads its metadata, and appends the table schema
    to the state.
    """
    file_path = state.data_load_event.file_path
    table_columns_description = state.data_load_event.table_columns_description
    # extract table name from its path
    table_name = os.path.splitext(os.path.basename(file_path))[0]

    # executes an SQL command to create a table from the CSV file in DuckDB
    db_conn.execute(
        f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM '{file_path}'"
    )
    logger.debug("Data file loaded into DuckDB.")

    # read metadata from the file
    with open(table_columns_description, "r") as fp:  # type: ignore
        meta = fp.read()
        table_info = f"Table: {table_name}\n{meta}\n"

    # add table schema information to the state.
    state.table_schemas += table_info
    # Update conversation history.
    state.update_conversation_history(
        SystemMessage(
            content=f"Table '{table_name}' loaded with metadata:\n{table_info}"
        )
    )
    state.next_step = "handle_user_input"
    return state


####################
# Build SQL query
####################
@log
def build_query(state: ChatState) -> ChatState:
    """
    Builds a DuckDB SQL query by analyzing the user question, previous interactions,
    table schemas, and any error messages from previous attempts.

    The prompt instructs the LLM to:
      - Deeply analyze the user's intent based on the current question and interaction history.
      - Generate a complete DuckDB SQL query if the intent is clear.
      - If the intent is ambiguous, ask for additional details in a free-form clarification
        message.
      - If a previous SQL query resulted in an error, incorporate the error message and correct
        the query.

    Returns only the SQL query text (or a clarification question) without extra commentary.
    """
    # calls the LLM and gives it the conversation history.
    llm_response = model.invoke(state.get_conversation_history())

    # If a clarification is needed, ask for more details.
    if llm_response.content.startswith("[CLARIFICATION]"):
        # extracts the clarification message.
        clarification_text = llm_response.content.split("[CLARIFICATION]")[1].strip()
        clarification_msg = (
            "Your question is ambiguous. "
            f"Please provide additional details: {clarification_text}"
        )
        # add a new AI message asking the user for more details.
        state.update_conversation_history(AIMessage(content=clarification_msg))
        # set the next step to "handle_user_input", so the user can refine their question.
        state.next_step = "handle_user_input"
        return state

    # remove unnecessary formatting (like markdown SQL blocks).
    query_text = llm_response.content.replace("```sql", "").replace("```", "").strip()
    # log the genrated SQL query
    logger.debug(query_text)
    # store the SQL query in chat history so the AI remembers it.
    state.update_conversation_history(AIMessage(content=query_text))
    # save the query text for execution
    state.sql_event.sql_text = query_text
    state.next_step = "execute_query"
    return state


#########################
# Execute the SQL query
#########################
@log
def execute_query(state: ChatState) -> ChatState:
    """
    Executes the generated SQL query. If execution fails, the error message is captured,
    and the state is updated to trigger query regeneration.
    """
    try:
        # run the SQL query
        result = db_conn.execute(state.sql_event.sql_text).fetchall()
        state.sql_event.sql_result = result
        state.sql_event.error = None
        state.next_step = "post_execution"
    except Exception as e:
        state.sql_event.sql_result = None
        # store the error message
        state.sql_event.error = str(e)
        # increment the retry count
        state.sql_event.retry_count += 1
        # log the error
        logger.exception("SQL execution failed with error: %s", str(e))
        if state.sql_event.retry_count > MAX_RETRY_SQL_GENERATION:
            state.update_conversation_history(
                AIMessage(
                    content=f"Unfortunately, I was unable to execute your requests "
                    "after {MAX_RETRY_SQL_GENERATION} attempts."
                )
            )
            # let the user ask another question
            state.next_step = "handle_user_input"
        else:
            state.update_conversation_history(
                AIMessage(
                    content=(
                        f"The generated SQL query raised this error:\n{state.sql_event.error}\n"
                    )
                )
            )
            # try to fix the SQL query
            state.next_step = "build_query"
    return state

###################################################
# Generate human-friendly response from SQL result
###################################################
@log
def post_execution(state: ChatState) -> ChatState:
    """
    Processes the SQL query result and generates a concise, human-readable summary.
    """
    sql_results = AIMessage(content=f"SQL results are: {state.sql_event.sql_result}")
    state.update_conversation_history(sql_results)
    interpret_msgs = [
        SystemMessage(
            content="You are an intelligent assistant that summarizes SQL query results based on "
            f"given table schemas. \nTable Schemas: {state.table_schemas}"
        ),
        HumanMessage(content=state.sql_event.user_question),
        AIMessage(content=f"Generated SQL Text is: {state.sql_event.sql_text}"),
        sql_results,
    ]
    # call the llm to summarize the SQL results in a human-friendly language
    llm_response = model.invoke(interpret_msgs)
    state.update_conversation_history(AIMessage(content=llm_response.content))
    state.sql_event.llm_response = llm_response.content
    # let user ask another question
    state.next_step = "handle_user_input"
    return state


def route_to_next_step(state: ChatState) -> str:
    """Determines the next lang graph step based on the current state."""
    logger.debug(f"Routing to {state.next_step} step...")
    return state.next_step