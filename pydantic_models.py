from pydantic import BaseModel, Field
from typing import List, Union
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
# custom imports
from constants import MAX_ROW_LIMIT_SQL_QUERY



class SqlEvent(BaseModel):
    """
    Represents a SQL event with user question, generated SQL text, SQL execution result, errors, and retries.

    Attributes:
        user_question (str): User's natural language question.
        sql_text (str): Generated SQL query text.
        sql_result (List[tuple]): SQL result.
        llm_response (str): Human-friendly AI response generated from the SQL result.
        error (str): Error message from SQL execution.
        retry_count (int): Number of times the query execution was retried.
    """

    user_question: str | None = Field(None)
    sql_text: str | None = Field(None)
    sql_result: List[tuple] | None = Field(None)
    llm_response: str | None = Field(None)
    error: str | None = Field(None)
    retry_count: int = 0


class DataLoadEvent(BaseModel):
    """
    Represent Data Load Event with table name, file path, and metadata path.

    Attributes:
        file_path (str): Name of the table to be loaded.
        table_columns_description (str): Path to the metadata file.
    """

    file_path: str | None = Field(None)
    table_columns_description: str | None = Field(None)


class ChatState(BaseModel):
    """
    Stores chat history, SQL execution details, and table schema information while helping guide the AI's next steps.

    Attributes:
        conversation_history (List[Union[SystemMessage, HumanMessage, AIMessage]]): Conversation history between system, human user, and AI.
        sql_event (SqlEvent): Last SQL event.
        data_load_event (DataLoadEvent): Data loader details (if a table is being loaded).
        table_schemas (str): Table schemas and metadata.
        next_step (str): Defines what the AI should do next (e.g., ask for clarification, generate SQL, or return results).
    """

    conversation_history: List[Union[SystemMessage, HumanMessage, AIMessage]]
    sql_event: SqlEvent = SqlEvent()
    data_load_event: DataLoadEvent = DataLoadEvent()
    table_schemas: str = ""
    next_step: str = "handle_user_input"

    @property
    def system_message(self):
        """Define the system message with table schemas."""
        return SystemMessage(
            content=(
                "You are an intelligent assistant that converts natural language questions "
                "into correct DuckDB SQL queries.\n"
                "Your goal is to generate a SQL query by considering the user's intent, "
                "previous interactions, and the table schemas.\n\n"
                "Return format:\n"
                "1. If the intent is clear, generate a complete DuckDB SQL query that satisfies "
                "the request. Return only the SQL query text without any extra commentary. Limit "
                f"query response to {MAX_ROW_LIMIT_SQL_QUERY} rows at most.\n"
                "2. If the intent is ambiguous, ask a follow-up clarification question that "
                "requests additional details. Prefix your clarification question with "
                '"[CLARIFICATION]" as output.\n\n'
                "Instructions:\n"
                "1. Consider the user's intent based on the current question.\n"
                "2. If any previous SQL query resulted in an error, incorporate the error "
                "message and generate a corrected query.\n"
                "3. If previous user questions or clarifications are relevant, include them "
                "in your analysis.\n\n"
                "Table schemas: " + self.table_schemas
            )
        )

    def get_conversation_history(self):
        """
        Returns the full chat history including the AI system instructions.
        This ensures the AI always remembers past messages before responding.
        """
        return [self.system_message] + self.conversation_history

    def update_conversation_history(self, new_message):
        """
        Appends new messages to the chat history.
        Keeps track of ongoing discussions between the user and AI.
        """
        self.conversation_history.append(new_message)
