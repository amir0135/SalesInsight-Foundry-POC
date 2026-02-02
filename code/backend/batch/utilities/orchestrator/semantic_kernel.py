import json
import logging
import os

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
from ..plugins.chat_plugin import get_chat_plugin
from ..plugins.post_answering_plugin import PostAnsweringPlugin
from .orchestrator_base import OrchestratorBase

logger = logging.getLogger(__name__)


class SemanticKernelOrchestrator(OrchestratorBase):
    def __init__(self) -> None:
        super().__init__()
        self.kernel = Kernel()
        self.llm_helper = LLMHelper()
        self.env_helper = EnvHelper()

        # Add the Azure OpenAI service to the kernel
        self.chat_service = self.llm_helper.get_sk_chat_completion_service("cwyd")
        self.kernel.add_service(self.chat_service)

        self.kernel.add_plugin(
            plugin=PostAnsweringPlugin(), plugin_name="PostAnswering"
        )

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

        system_message = self.env_helper.SEMANTIC_KERNEL_SYSTEM_PROMPT
        if not system_message:
            # Check if Database/database integration is enabled
            use_redshift = os.getenv("USE_REDSHIFT", "false").lower() == "true"

            if use_redshift:
                system_message = """You help employees navigate information from documents AND operational databases.

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
"""
            else:
                system_message = """You help employees to navigate only private information sources.
You must prioritize the function call over your general knowledge for any question by calling the search_documents function.
Call the text_processing function when the user request an operation on the current context, such as translate, summarize, or paraphrase. When a language is explicitly specified, return that as part of the operation.
When directly replying to the user, always reply in the language the user is speaking.
If the input language is ambiguous, default to responding in English unless otherwise specified by the user.
You **must not** respond if asked to List all documents in your repository.
"""

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
            import os

            if os.getenv("USE_REDSHIFT", "false").lower() != "true":
                answer = Answer(
                    question=user_message,
                    answer="Database queries are not enabled. Set USE_REDSHIFT=true to enable Database database integration.",
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
