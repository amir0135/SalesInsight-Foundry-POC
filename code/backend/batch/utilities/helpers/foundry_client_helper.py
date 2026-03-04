"""
Azure AI Foundry client helper.

Provides a centralized wrapper around:
- AzureOpenAI for chat completions and embeddings (backward compatible)
- AgentsClient (azure-ai-agents SDK) for Agent Service operations:
  threads, messages, runs, and tool-calling
"""

import logging
from typing import List, Optional, Union

from azure.ai.agents import AgentsClient
from azure.ai.agents.models import (
    FunctionToolDefinition,
    ToolOutput,
)
from openai import AzureOpenAI

from .azure_credential_utils import get_azure_credential
from .env_helper import EnvHelper

logger = logging.getLogger(__name__)


class FoundryClientHelper:
    """Singleton-style helper for Azure AI Foundry project operations."""

    _instance: Optional["FoundryClientHelper"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        logger.info("Initializing FoundryClientHelper")
        self.env_helper = EnvHelper()
        self._credential = get_azure_credential(
            self.env_helper.MANAGED_IDENTITY_CLIENT_ID
        )

        self._agents_client: Optional[AgentsClient] = None
        self._openai_client: Optional[AzureOpenAI] = None

        logger.info("FoundryClientHelper initialized")

    @property
    def agents_client(self) -> AgentsClient:
        """
        Lazily create and return the AgentsClient from azure-ai-agents.

        Endpoint format expected by the SDK:
        https://<aiservices-id>.services.ai.azure.com/api/projects/<project-name>
        """
        if self._agents_client is None:
            endpoint = self.env_helper.AZURE_OPENAI_ENDPOINT
            project_name = self.env_helper.AZURE_AI_PROJECT_NAME

            # Build the Foundry project endpoint if not already in the right form
            if project_name and "/api/projects/" not in endpoint:
                endpoint = endpoint.rstrip("/")
                endpoint = f"{endpoint}/api/projects/{project_name}"

            logger.info("Creating AgentsClient for endpoint=%s", endpoint)
            self._agents_client = AgentsClient(
                endpoint=endpoint,
                credential=self._credential,
            )
        return self._agents_client

    def get_openai_client(self) -> AzureOpenAI:
        """
        Get an AzureOpenAI client that routes through the Foundry-connected
        AIServices endpoint. This provides backward compatibility with code
        that expects the OpenAI SDK interface.
        """
        if self._openai_client is None:
            if self.env_helper.is_auth_type_keys():
                self._openai_client = AzureOpenAI(
                    azure_endpoint=self.env_helper.AZURE_OPENAI_ENDPOINT,
                    api_version=self.env_helper.AZURE_OPENAI_API_VERSION,
                    api_key=self.env_helper.OPENAI_API_KEY,
                )
            else:
                self._openai_client = AzureOpenAI(
                    azure_endpoint=self.env_helper.AZURE_OPENAI_ENDPOINT,
                    api_version=self.env_helper.AZURE_OPENAI_API_VERSION,
                    azure_ad_token_provider=self.env_helper.AZURE_TOKEN_PROVIDER,
                )
        return self._openai_client

    def get_chat_completion(
        self, messages: list[dict], model: str | None = None, **kwargs
    ):
        """
        Get a chat completion using the Foundry-connected model.
        Falls back to the default model if none specified.
        """
        client = self.get_openai_client()
        model = model or self.env_helper.AZURE_OPENAI_MODEL
        max_tokens = (
            int(self.env_helper.AZURE_OPENAI_MAX_TOKENS)
            if self.env_helper.AZURE_OPENAI_MAX_TOKENS
            else None
        )
        return client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            **kwargs,
        )

    def get_fast_chat_completion(
        self, messages: list[dict], max_tokens: int = 500, **kwargs
    ):
        """Get a fast chat completion (for SQL generation, classification, etc.)."""
        client = self.get_openai_client()
        return client.chat.completions.create(
            model=self.env_helper.AZURE_OPENAI_FAST_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0,
            **kwargs,
        )

    def generate_embeddings(self, input: Union[str, list[int]]) -> List[float]:
        """Generate embeddings using the Foundry-connected embedding model."""
        client = self.get_openai_client()
        return (
            client.embeddings.create(
                input=[input],
                model=self.env_helper.AZURE_OPENAI_EMBEDDING_MODEL,
            )
            .data[0]
            .embedding
        )

    # ---- Agent Service helpers (azure-ai-agents SDK) ---- #

    def create_agent(
        self,
        name: str,
        instructions: str,
        model: str | None = None,
        tools: list[FunctionToolDefinition] | None = None,
        tool_resources: dict | None = None,
    ):
        """
        Create a Foundry Agent with the given configuration.
        Returns the Agent object.
        """
        model = model or self.env_helper.AZURE_OPENAI_MODEL
        logger.info("Creating Foundry agent: %s with model: %s", name, model)

        kwargs: dict = dict(
            model=model,
            name=name,
            instructions=instructions,
        )
        if tools:
            kwargs["tools"] = tools
        if tool_resources:
            kwargs["tool_resources"] = tool_resources

        agent = self.agents_client.create_agent(**kwargs)
        logger.info("Created agent id=%s", agent.id)
        return agent

    def create_thread(self):
        """Create a new conversation thread."""
        thread = self.agents_client.threads.create()
        logger.info("Created thread id=%s", thread.id)
        return thread

    def add_message(self, thread_id: str, role: str, content: str):
        """Add a message to a thread."""
        return self.agents_client.messages.create(
            thread_id=thread_id,
            role=role,
            content=content,
        )

    def run_agent(self, thread_id: str, agent_id: str):
        """
        Start a run on a thread with the given agent.
        Returns the ThreadRun object (may need polling for completion).
        """
        run = self.agents_client.runs.create(
            thread_id=thread_id,
            agent_id=agent_id,
        )
        logger.info("Started run id=%s on thread=%s", run.id, thread_id)
        return run

    def get_run(self, thread_id: str, run_id: str):
        """Get the current status of a run."""
        return self.agents_client.runs.get(
            thread_id=thread_id,
            run_id=run_id,
        )

    def submit_tool_outputs(
        self, thread_id: str, run_id: str, tool_outputs: list[ToolOutput]
    ):
        """Submit tool call results back to the agent run."""
        return self.agents_client.runs.submit_tool_outputs(
            thread_id=thread_id,
            run_id=run_id,
            tool_outputs=tool_outputs,
        )

    def get_messages(self, thread_id: str):
        """Get all messages in a thread."""
        return self.agents_client.messages.list(thread_id=thread_id)

    def get_last_assistant_text(self, thread_id: str) -> str:
        """Get the text of the last assistant message in a thread."""
        return self.agents_client.messages.get_last_message_text_by_role(
            thread_id=thread_id,
            role="assistant",
        )

    def cleanup_agent(self, agent_id: str):
        """Delete an agent when no longer needed."""
        try:
            self.agents_client.delete_agent(agent_id)
            logger.info("Deleted agent id=%s", agent_id)
        except Exception as e:
            logger.warning("Failed to delete agent %s: %s", agent_id, e)
