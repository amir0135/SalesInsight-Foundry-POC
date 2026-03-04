"""
Foundry Agent Orchestrator.

Uses Azure AI Foundry's Agent Service (azure-ai-agents SDK) to manage
conversation threads and tool-calling. The agent is created with function
tool definitions that mirror the existing ChatPlugin/DatabaseChatPlugin
tools, but the tool execution happens locally (preserving NL2SQL, document
search, etc.).
"""

import json
import logging
import os
import time as timing_module

from azure.ai.agents.models import (
    FunctionToolDefinition,
    FunctionDefinition,
    RunStatus,
    ToolOutput,
)

from ..common.answer import Answer
from ..helpers.llm_helper import LLMHelper
from ..helpers.env_helper import EnvHelper
from ..tools.question_answer_tool import QuestionAnswerTool
from ..tools.text_processing_tool import TextProcessingTool
from .orchestrator_base import OrchestratorBase

logger = logging.getLogger(__name__)


def _build_tool_definitions() -> list[FunctionToolDefinition]:
    """
    Build the list of function tool definitions for the Foundry agent.
    Mirrors the tools defined in ChatPlugin / DatabaseChatPlugin.
    Uses the azure-ai-agents FunctionToolDefinition model.
    """
    tools: list[FunctionToolDefinition] = [
        FunctionToolDefinition(
            function=FunctionDefinition(
                name="search_documents",
                description="Provide answers to any fact question coming from users by searching uploaded documents.",
                parameters={
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "A standalone question, converted from the chat history",
                        }
                    },
                    "required": ["question"],
                },
            )
        ),
        FunctionToolDefinition(
            function=FunctionDefinition(
                name="text_processing",
                description="Useful when you want to apply a transformation on the text, like translate, summarize, rephrase and so on.",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The text to be processed",
                        },
                        "operation": {
                            "type": "string",
                            "description": "The operation to be performed on the text. Like Translate to Italian, Summarize, Paraphrase, etc.",
                        },
                    },
                    "required": ["text", "operation"],
                },
            )
        ),
    ]

    # Add database tools if enabled
    if os.getenv("USE_REDSHIFT", "false").lower() == "true":
        tools.extend(
            [
                FunctionToolDefinition(
                    function=FunctionDefinition(
                        name="query_database",
                        description=(
                            "Query the operational database. Use for questions about "
                            "errors, disconnections, connections, facilities, counts, totals, "
                            "top N, averages, sums. Generates SQL and returns database results."
                        ),
                        parameters={
                            "type": "object",
                            "properties": {
                                "question": {
                                    "type": "string",
                                    "description": "The question exactly as asked",
                                },
                                "max_rows": {
                                    "type": "integer",
                                    "description": "Maximum rows to return (default: 50, max: 100)",
                                    "default": 50,
                                },
                            },
                            "required": ["question"],
                        },
                    )
                ),
                FunctionToolDefinition(
                    function=FunctionDefinition(
                        name="analyze_database",
                        description="Deep analysis of database data. Use for facility health assessment, comparing multiple facilities, trend analysis, or correlating errors with connectivity issues.",
                        parameters={
                            "type": "object",
                            "properties": {
                                "analysis_type": {
                                    "type": "string",
                                    "enum": [
                                        "facility_health",
                                        "compare_facilities",
                                        "trend",
                                        "correlation",
                                    ],
                                    "description": "Type of analysis to perform",
                                },
                                "facility_id": {
                                    "type": "string",
                                    "description": "Facility name or ID",
                                    "default": "",
                                },
                                "facility_ids": {
                                    "type": "string",
                                    "description": "Comma-separated facility IDs for comparison",
                                    "default": "",
                                },
                                "metric": {
                                    "type": "string",
                                    "description": "'errors', 'connectivity', or 'data_quality'",
                                    "default": "errors",
                                },
                                "range_days": {
                                    "type": "integer",
                                    "description": "Days to analyze",
                                    "default": 30,
                                },
                            },
                            "required": ["analysis_type"],
                        },
                    )
                ),
            ]
        )

    return tools


def _get_system_prompt() -> str:
    """Get the system prompt for the Foundry agent."""
    use_redshift = os.getenv("USE_REDSHIFT", "false").lower() == "true"
    env_helper = EnvHelper()

    system_message = env_helper.SEMANTIC_KERNEL_SYSTEM_PROMPT
    if system_message:
        return system_message

    if use_redshift:
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
"""
    else:
        return """You help employees to navigate only private information sources.
You must prioritize the function call over your general knowledge for any question by calling the search_documents function.
Call the text_processing function when the user request an operation on the current context, such as translate, summarize, or paraphrase. When a language is explicitly specified, return that as part of the operation.
When directly replying to the user, always reply in the language the user is speaking.
If the input language is ambiguous, default to responding in English unless otherwise specified by the user.
You **must not** respond if asked to List all documents in your repository.
"""


class FoundryAgentOrchestrator(OrchestratorBase):
    """
    Orchestrator that uses Azure AI Foundry Agent Service.

    Flow:
    1. Creates a Foundry agent with function tool definitions
    2. Creates a thread, adds the user message
    3. Runs the agent — agent decides which tools to call
    4. When tool_calls are returned, executes them locally
    5. Submits results back to the agent
    6. Returns the final response
    """

    def __init__(self) -> None:
        super().__init__()
        self.llm_helper = LLMHelper()
        self.env_helper = EnvHelper()
        self._foundry_helper = self.llm_helper.get_foundry_helper()
        self._agent = None

    def _get_or_create_agent(self):
        """Lazily create the Foundry agent."""
        if self._agent is None:
            tools = _build_tool_definitions()
            system_prompt = _get_system_prompt()
            self._agent = self._foundry_helper.create_agent(
                name="salesinsight-agent",
                instructions=system_prompt,
                model=self.env_helper.AZURE_OPENAI_MODEL,
                tools=tools,
            )
        return self._agent

    def _execute_tool_call(
        self,
        function_name: str,
        arguments: dict,
        user_message: str,
        chat_history: list[dict],
    ) -> Answer:
        """Execute a tool call locally and return an Answer."""
        logger.info("Executing tool: %s with args: %s", function_name, arguments)

        if function_name == "search_documents":
            question = arguments.get("question", user_message)
            return QuestionAnswerTool().answer_question(
                question=question, chat_history=chat_history
            )

        elif function_name == "text_processing":
            text = arguments.get("text", "")
            operation = arguments.get("operation", "")
            return TextProcessingTool().answer_question(
                question=user_message,
                chat_history=chat_history,
                text=text,
                operation=operation,
            )

        elif function_name == "query_database":
            from ..tools.database_nl_query_tool import DatabaseNLQueryTool

            question = arguments.get("question", user_message)
            max_rows = min(int(arguments.get("max_rows", 50)), 100)
            return DatabaseNLQueryTool().query_with_natural_language(
                question=question, max_rows=max_rows
            )

        elif function_name == "analyze_database":
            from ..tools.database_analysis_tool import DatabaseAnalysisTool

            tool = DatabaseAnalysisTool()
            analysis_type = arguments.get("analysis_type", "")
            facility_id = arguments.get("facility_id", "")
            facility_ids = arguments.get("facility_ids", "")
            metric = arguments.get("metric", "errors")
            range_days = int(arguments.get("range_days", 30))

            if analysis_type == "facility_health":
                return tool.analyze_facility_health(facility_id, range_days)
            elif analysis_type == "compare_facilities":
                fac_list = [f.strip() for f in facility_ids.split(",") if f.strip()]
                return tool.compare_facilities(fac_list, range_days)
            elif analysis_type == "trend":
                return tool.analyze_trend(metric, range_days, facility_id)
            elif analysis_type == "correlation":
                return tool.correlate_errors_connectivity(range_days, facility_id)
            else:
                return Answer(
                    question=user_message,
                    answer=f"Unknown analysis type: {analysis_type}",
                    source_documents=[],
                )

        else:
            logger.warning("Unknown tool: %s", function_name)
            return Answer(
                question=user_message,
                answer=f"Unknown tool: {function_name}",
                source_documents=[],
            )

    async def orchestrate(
        self, user_message: str, chat_history: list[dict], **kwargs: dict
    ) -> list[dict]:
        total_start = timing_module.perf_counter()
        timings = {}

        logger.info("FoundryAgentOrchestrator.orchestrate started")
        force_database = kwargs.get("force_database", False)

        # Direct database bypass
        if force_database:
            logger.info("Force database mode: bypassing agent")
            result = await self._handle_force_database_query(user_message, chat_history)
            timings["total"] = timing_module.perf_counter() - total_start
            logger.info("Orchestrator timings (force_db): TOTAL=%.3f", timings["total"])
            return result

        # Content safety input check
        if self.config.prompts.enable_content_safety:
            if response := self.call_content_safety_input(user_message):
                return response

        step_start = timing_module.perf_counter()

        # Get or create the agent
        agent = self._get_or_create_agent()

        # Create a thread and add the user message
        thread = self._foundry_helper.create_thread()
        self._foundry_helper.add_message(thread.id, "user", user_message)

        timings["setup"] = timing_module.perf_counter() - step_start
        step_start = timing_module.perf_counter()

        # Run the agent
        run = self._foundry_helper.run_agent(thread.id, agent.id)

        # Poll for completion
        max_polls = 60
        poll_interval = 1.0
        answer = None
        tool_answer = None

        for _ in range(max_polls):
            run = self._foundry_helper.get_run(thread.id, run.id)

            if run.status == RunStatus.COMPLETED:
                timings["agent_run"] = timing_module.perf_counter() - step_start
                # Extract the assistant's response
                answer_text = self._foundry_helper.get_last_assistant_text(
                    thread.id
                )
                answer = Answer(
                    question=user_message,
                    answer=answer_text or "",
                    source_documents=(
                        tool_answer.source_documents if tool_answer else []
                    ),
                    prompt_tokens=getattr(
                        run.usage, "prompt_tokens", 0
                    )
                    if run.usage
                    else 0,
                    completion_tokens=getattr(
                        run.usage, "completion_tokens", 0
                    )
                    if run.usage
                    else 0,
                )
                break

            elif run.status == RunStatus.REQUIRES_ACTION:
                timings["agent_tool_selection"] = (
                    timing_module.perf_counter() - step_start
                )
                step_start = timing_module.perf_counter()

                # Process tool calls
                tool_outputs = []
                tool_calls = run.required_action.submit_tool_outputs.tool_calls

                for tool_call in tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)

                    logger.info("Agent requested tool: %s", fn_name)

                    tool_answer = self._execute_tool_call(
                        fn_name, fn_args, user_message, chat_history
                    )

                    self.log_tokens(
                        prompt_tokens=tool_answer.prompt_tokens or 0,
                        completion_tokens=tool_answer.completion_tokens or 0,
                    )

                    tool_outputs.append(
                        ToolOutput(
                            tool_call_id=tool_call.id,
                            output=tool_answer.answer,
                        )
                    )

                timings["tool_execution"] = timing_module.perf_counter() - step_start
                step_start = timing_module.perf_counter()

                # Submit tool outputs back to the agent
                self._foundry_helper.submit_tool_outputs(
                    thread.id, run.id, tool_outputs
                )

            elif run.status in (
                RunStatus.FAILED,
                RunStatus.CANCELLED,
                RunStatus.EXPIRED,
            ):
                logger.error("Agent run failed with status: %s", run.status)
                answer = Answer(
                    question=user_message,
                    answer=f"Agent run failed: {run.status}. {getattr(run, 'last_error', '')}",
                    source_documents=[],
                )
                break

            else:
                # Still in progress — wait and poll
                import asyncio

                await asyncio.sleep(poll_interval)

        if answer is None:
            answer = Answer(
                question=user_message,
                answer="Agent run timed out. Please try again.",
                source_documents=[],
            )

        self.log_tokens(
            prompt_tokens=answer.prompt_tokens or 0,
            completion_tokens=answer.completion_tokens or 0,
        )

        # Content safety output check
        if self.config.prompts.enable_content_safety:
            if response := self.call_content_safety_output(user_message, answer.answer):
                return response

        timings["total"] = timing_module.perf_counter() - total_start
        logger.info(
            "FoundryAgent timings: setup=%.3f, tool_select=%.3f, tool_exec=%.3f, agent_run=%.3f, TOTAL=%.3f",
            timings.get("setup", 0),
            timings.get("agent_tool_selection", 0),
            timings.get("tool_execution", 0),
            timings.get("agent_run", 0),
            timings.get("total", 0),
        )

        # Format output for the UI
        messages = self.output_parser.parse(
            question=answer.question,
            answer=answer.answer,
            source_documents=answer.source_documents,
        )
        logger.info("FoundryAgentOrchestrator.orchestrate ended")
        return messages

    async def _handle_force_database_query(
        self, user_message: str, chat_history: list[dict]
    ) -> list[dict]:
        """Handle /database command by directly calling the Database query tool."""
        from ..tools.database_nl_query_tool import DatabaseNLQueryTool

        try:
            if os.getenv("USE_REDSHIFT", "false").lower() != "true":
                answer = Answer(
                    question=user_message,
                    answer="Database queries are not enabled. Set USE_REDSHIFT=true to enable database integration.",
                    source_documents=[],
                )
            else:
                tool = DatabaseNLQueryTool()
                answer = tool.query_with_natural_language(
                    question=user_message, max_rows=100
                )
                logger.info("Force database query executed successfully")

            self.log_tokens(
                prompt_tokens=answer.prompt_tokens or 0,
                completion_tokens=answer.completion_tokens or 0,
            )

            return self.output_parser.parse(
                question=answer.question,
                answer=answer.answer,
                source_documents=answer.source_documents,
            )

        except Exception as e:
            logger.error("Error in force database query: %s", str(e), exc_info=True)
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
