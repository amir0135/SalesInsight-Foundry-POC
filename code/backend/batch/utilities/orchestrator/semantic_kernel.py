import json
import logging

from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.function_choice_behavior import (
    FunctionChoiceBehavior,
)
from semantic_kernel.contents import ChatHistory
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.finish_reason import FinishReason

from ..common.answer import Answer
from ..helpers.llm_helper import LLMHelper
from ..helpers.env_helper import EnvHelper
from ..helpers.database.data_source_factory import is_database_enabled
from ..plugins.chat_plugin import get_chat_plugin
from ..plugins.post_answering_plugin import PostAnsweringPlugin
from ..search.search import Search
from .orchestrator_base import OrchestratorBase

logger = logging.getLogger(__name__)


class SemanticKernelOrchestrator(OrchestratorBase):
    def __init__(self) -> None:
        super().__init__()
        self.kernel = Kernel()
        self.llm_helper = LLMHelper()
        self.env_helper = EnvHelper()

        # Tool selection model — uses main model via SK
        # (gpt-4.1-mini triggers jailbreak filter with SK prompt templates)
        self.chat_service = self.llm_helper.get_sk_chat_completion_service("cwyd")
        self.kernel.add_service(self.chat_service)

        self.kernel.add_plugin(
            plugin=PostAnsweringPlugin(), plugin_name="PostAnswering"
        )

    def _get_system_message(self) -> str:
        """Get system message for orchestration, with clarification support."""
        system_message = self.env_helper.SEMANTIC_KERNEL_SYSTEM_PROMPT
        if system_message:
            return system_message

        if is_database_enabled():
            return """You help employees navigate information from documents AND operational databases.

TOOL SELECTION - Choose the RIGHT tool for each question:

1. **query_database** - ALWAYS use for database questions about:
   - Errors, error counts, error messages, error_logs
   - Disconnections, connections, connectivity_logs
   - Facilities, bays, radar devices
   - Questions with: "how many", "count", "total", "top N", "which has most", "list", "show"
   - Time-based queries: "last week", "past 30 days", "yesterday"

2. **search_documents** - Use for document/policy questions:
   - Contract terms, policies, procedures
   - Documentation content, specifications

3. **text_processing** - Use for transformations:
   - Translate, summarize, paraphrase text

IMPORTANT: For ANY question about errors, disconnections, facilities, or operational metrics, use query_database.
When directly replying to the user, always reply in the language the user is speaking.

CLARIFICATION - Ask follow-up questions when:
- The query is ambiguous or could mean multiple things (e.g. "What is the menu?" has no clear data mapping)
- Key terms don't match any known data domain (documents, database tables, etc.)
- The user combines unrelated questions in one message - address what you can, then ask about the unclear part
- A term could refer to different metrics (e.g. "performance" could mean revenue, order count, or delivery speed)
When clarifying, briefly explain what data IS available and ask the user to be more specific.
Do NOT guess or fabricate data. If uncertain, ask.
"""
        else:
            return """You help employees to navigate only private information sources.
You must prioritize the function call over your general knowledge for any question by calling the search_documents function.
Call the text_processing function when the user request an operation on the current context, such as translate, summarize, or paraphrase. When a language is explicitly specified, return that as part of the operation.
When directly replying to the user, always reply in the language the user is speaking.
If the input language is ambiguous, default to responding in English unless otherwise specified by the user.
Do not list all documents in the repository.

CLARIFICATION - If the user's question is vague or ambiguous:
- Ask a brief clarifying question to understand what they need
- Mention what types of information are available (uploaded documents, policies, contracts, etc.)
- If only part of the question is unclear, answer what you can and ask about the rest
Do NOT guess or fabricate information. If uncertain, ask.
"""

    async def orchestrate(
        self, user_message: str, chat_history: list[dict], **kwargs: dict
    ) -> list[dict]:
        import time as timing_module
        total_start = timing_module.perf_counter()
        timings = {}

        logger.info("Method orchestrate of semantic_kernel started")
        force_database = kwargs.get("force_database", False)

        # If force_database is True, bypass LLM tool selection and directly query
        if force_database:
            logger.info("Force database mode: bypassing tool selection")
            result = await self._handle_force_database_query(user_message, chat_history)
            timings["total"] = timing_module.perf_counter() - total_start
            logger.info("Orchestrator timings (force_db): TOTAL=%.3f", timings["total"])
            return result

        # Call Content Safety tool
        if self.config.prompts.enable_content_safety:
            if response := self.call_content_safety_input(user_message):
                return response

        step_start = timing_module.perf_counter()

        system_message = self._get_system_message()

        self.kernel.add_plugin(
            plugin=get_chat_plugin(question=user_message, chat_history=chat_history),
            plugin_name="Chat",
        )

        settings = self.llm_helper.get_sk_service_settings(self.chat_service)
        settings.function_choice_behavior = FunctionChoiceBehavior.Auto(
            auto_invoke=False, filters={"included_plugins": ["Chat"]}
        )

        orchestrate_function = self.kernel.add_function(
            plugin_name="Main",
            function_name="orchestrate",
            prompt="{{$chat_history}}{{$user_message}}",
            prompt_execution_settings=settings,
        )

        history = ChatHistory(system_message=system_message)

        for message in chat_history.copy():
            history.add_message(message)

        chat_history_str = ""
        for message in history.messages:
            chat_history_str += f"{message.role}: {message.content}\n"

        timings["setup"] = timing_module.perf_counter() - step_start
        step_start = timing_module.perf_counter()

        result: ChatMessageContent = (
            await self.kernel.invoke(
                function=orchestrate_function,
                chat_history=chat_history_str,
                user_message=user_message,
            )
        ).value[0]

        timings["llm_tool_selection"] = timing_module.perf_counter() - step_start
        step_start = timing_module.perf_counter()

        self.log_tokens(
            prompt_tokens=result.metadata["usage"].prompt_tokens,
            completion_tokens=result.metadata["usage"].completion_tokens,
        )

        if result.finish_reason == FinishReason.TOOL_CALLS:
            logger.info("Semantic Kernel function call detected")

            function_name = result.items[0].name
            logger.info(f"{function_name} function detected")
            function = self.kernel.get_function_from_fully_qualified_function_name(
                function_name
            )

            arguments = json.loads(result.items[0].arguments)

            answer: Answer = (
                await self.kernel.invoke(function=function, **arguments)
            ).value

            timings["tool_execution"] = timing_module.perf_counter() - step_start
            step_start = timing_module.perf_counter()

            self.log_tokens(
                prompt_tokens=answer.prompt_tokens,
                completion_tokens=answer.completion_tokens,
            )

            # Run post prompt if needed
            if (
                self.config.prompts.enable_post_answering_prompt
                and "search_documents" in function_name
            ):
                logger.debug("Running post answering prompt")
                answer: Answer = (
                    await self.kernel.invoke(
                        function_name="validate_answer",
                        plugin_name="PostAnswering",
                        answer=answer,
                    )
                ).value

                timings["post_answering"] = timing_module.perf_counter() - step_start

                self.log_tokens(
                    prompt_tokens=answer.prompt_tokens,
                    completion_tokens=answer.completion_tokens,
                )

            timings["total"] = timing_module.perf_counter() - total_start
            logger.info(
                "Orchestrator timings: setup=%.3f, llm_tool_select=%.3f, tool_exec=%.3f, post=%.3f, TOTAL=%.3f",
                timings.get("setup", 0),
                timings.get("llm_tool_selection", 0),
                timings.get("tool_execution", 0),
                timings.get("post_answering", 0),
                timings.get("total", 0),
            )
        else:
            logger.info("No function call detected")
            answer = Answer(
                question=user_message,
                answer=result.content,
                prompt_tokens=result.metadata["usage"].prompt_tokens,
                completion_tokens=result.metadata["usage"].completion_tokens,
            )

        # Call Content Safety tool
        if self.config.prompts.enable_content_safety:
            if response := self.call_content_safety_output(user_message, answer.answer):
                return response

        # Format the output for the UI
        messages = self.output_parser.parse(
            question=answer.question,
            answer=answer.answer,
            source_documents=answer.source_documents,
        )
        logger.info("Method orchestrate of semantic_kernel ended")
        return messages

    async def prepare_streaming(
        self, user_message: str, chat_history: list[dict], **kwargs: dict
    ) -> dict:
        """
        Async preparation phase for streaming: tool selection + search.

        Returns a dict:
        - {"streaming": False, "messages": [...]} — complete response, no streaming needed
        - {"streaming": True, "question": str, "source_documents": [...],
           "llm_messages": [...], "model": str|None} — caller should stream LLM call
        """
        logger.info("Method prepare_streaming started")
        force_database = kwargs.get("force_database", False)

        if force_database:
            result = await self.orchestrate(user_message, chat_history, **kwargs)
            return {"streaming": False, "messages": result}

        if self.config.prompts.enable_content_safety:
            if response := self.call_content_safety_input(user_message):
                return {"streaming": False, "messages": response}

        # --- Tool selection (fast model, non-streaming) ---
        system_message = self._get_system_message()

        self.kernel.add_plugin(
            plugin=get_chat_plugin(question=user_message, chat_history=chat_history),
            plugin_name="Chat",
        )

        settings = self.llm_helper.get_sk_service_settings(self.chat_service)
        settings.function_choice_behavior = FunctionChoiceBehavior.Auto(
            auto_invoke=False, filters={"included_plugins": ["Chat"]}
        )

        orchestrate_function = self.kernel.add_function(
            plugin_name="Main",
            function_name="orchestrate",
            prompt="{{$chat_history}}{{$user_message}}",
            prompt_execution_settings=settings,
        )

        history = ChatHistory(system_message=system_message)
        for message in chat_history.copy():
            history.add_message(message)

        chat_history_str = ""
        for message in history.messages:
            chat_history_str += f"{message.role}: {message.content}\n"

        result: ChatMessageContent = (
            await self.kernel.invoke(
                function=orchestrate_function,
                chat_history=chat_history_str,
                user_message=user_message,
            )
        ).value[0]

        self.log_tokens(
            prompt_tokens=result.metadata["usage"].prompt_tokens,
            completion_tokens=result.metadata["usage"].completion_tokens,
        )

        if result.finish_reason != FinishReason.TOOL_CALLS:
            answer = Answer(
                question=user_message,
                answer=result.content,
                prompt_tokens=result.metadata["usage"].prompt_tokens,
                completion_tokens=result.metadata["usage"].completion_tokens,
            )
            messages = self.output_parser.parse(
                question=answer.question,
                answer=answer.answer,
                source_documents=answer.source_documents,
            )
            return {"streaming": False, "messages": messages}

        function_name = result.items[0].name
        logger.info("prepare_streaming: %s function detected", function_name)
        arguments = json.loads(result.items[0].arguments)

        # Only stream for search_documents; other tools execute fully
        if "search_documents" not in function_name:
            function = self.kernel.get_function_from_fully_qualified_function_name(
                function_name
            )
            answer: Answer = (
                await self.kernel.invoke(function=function, **arguments)
            ).value
            self.log_tokens(
                prompt_tokens=answer.prompt_tokens,
                completion_tokens=answer.completion_tokens,
            )
            messages = self.output_parser.parse(
                question=answer.question,
                answer=answer.answer,
                source_documents=answer.source_documents,
            )
            return {"streaming": False, "messages": messages}

        # --- Streaming search_documents path ---
        # Do the search now (sync, fast), prepare LLM messages, return for caller to stream
        from ..tools.question_answer_tool import QuestionAnswerTool

        qa_tool = QuestionAnswerTool()
        question = arguments.get("question", user_message)

        source_documents = Search.get_source_documents(qa_tool.search_handler, question)

        image_urls = []
        model = None

        if qa_tool.config.prompts.use_on_your_data_format:
            llm_messages = qa_tool.generate_on_your_data_messages(
                question, chat_history, source_documents, image_urls
            )
        else:
            llm_messages = qa_tool.generate_messages(question, source_documents)

        logger.info("prepare_streaming: search done, %d docs, ready to stream LLM", len(source_documents))
        return {
            "streaming": True,
            "question": question,
            "source_documents": source_documents,
            "llm_messages": llm_messages,
            "model": model,
        }

    async def _handle_force_database_query(
        self, user_message: str, chat_history: list[dict]
    ) -> list[dict]:
        """
        Handle /database command by directly calling the Database query tool.
        Bypasses LLM tool selection for guaranteed database queries.
        """
        from ..tools.database_nl_query_tool import DatabaseNLQueryTool

        try:
            # Check if Database is enabled
            if not is_database_enabled():
                answer = Answer(
                    question=user_message,
                    answer="Database queries are not enabled. Configure a database connection (Snowflake or PostgreSQL) to enable database integration.",
                    source_documents=[],
                )
            else:
                # Directly call the Database NL query tool
                tool = DatabaseNLQueryTool()
                answer = tool.query_with_natural_language(
                    question=user_message, max_rows=100
                )
                logger.info("Force database query executed successfully")

            self.log_tokens(
                prompt_tokens=answer.prompt_tokens or 0,
                completion_tokens=answer.completion_tokens or 0,
            )

            # Format the output for the UI
            messages = self.output_parser.parse(
                question=answer.question,
                answer=answer.answer,
                source_documents=answer.source_documents,
            )
            return messages

        except Exception as e:
            logger.error(f"Error in force database query: {str(e)}", exc_info=True)
            answer = Answer(
                question=user_message,
                answer=f"Error querying database: {str(e)}",
                source_documents=[],
            )
            return self.output_parser.parse(
                question=answer.question,
                answer=answer.answer,
                source_documents=[],
            )
