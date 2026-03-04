"""
Azure AI Foundry client helper.

Provides a centralized wrapper around AIProjectClient for:
- Chat completions (routed through Foundry's connected AIServices)
- Embeddings generation
- Agent Service access (threads, messages, runs)
- Tracing / telemetry configuration
"""

import logging
from functools import lru_cache
from typing import List, Optional, Union

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AgentsApiResponseFormatMode,
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

        # Build the project endpoint from the resource group + project name
        # Format: https://<location>.api.azureml.ms/
        # The AIProjectClient needs the full connection string or endpoint
        self._project_client: Optional[AIProjectClient] = None
        self._openai_client: Optional[AzureOpenAI] = None

        logger.info("FoundryClientHelper initialized")

    @property
    def project_client(self) -> AIProjectClient:
        """Lazily create and return the AIProjectClient."""
        if self._project_client is None:
            endpoint = self.env_helper.AZURE_OPENAI_ENDPOINT
            subscription_id = self.env_helper.AZURE_SUBSCRIPTION_ID
            resource_group = self.env_helper.AZURE_RESOURCE_GROUP
            project_name = self.env_helper.AZURE_AI_PROJECT_NAME

            logger.info(
                "Creating AIProjectClient for project=%s in rg=%s",
                project_name,
                resource_group,
            )

            self._project_client = AIProjectClient(
                credential=self._credential,
                endpoint=endpoint,
                subscription_id=subscription_id,
                resource_group_name=resource_group,
                project_name=project_name,
            )
        return self._project_client

    @property
    def inference_client(self):
        """Get the inference client from AIProjectClient for chat/embeddings."""
        return self.project_client.inference

    @property
    def agents_client(self):
        """Get the agents client for Foundry Agent Service operations."""
        return self.project_client.agents

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

    # ---- Agent Service helpers ---- #

    def create_agent(
        self,
        name: str,
        instructions: str,
        model: str | None = None,
        tools: list | None = None,
        tool_resources: dict | None = None,
    ):
        """
        Create a Foundry Agent with the given configuration.
        Returns the agent object.
        """
        model = model or self.env_helper.AZURE_OPENAI_MODEL
        logger.info("Creating Foundry agent: %s with model: %s", name, model)

        agent = self.agents_client.create_agent(
            model=model,
            name=name,
            instructions=instructions,
            tools=tools or [],
            tool_resources=tool_resources or {},
        )
        logger.info("Created agent id=%s", agent.id)
        return agent

    def create_thread(self):
        """Create a new conversation thread."""
        thread = self.agents_client.create_thread()
        logger.info("Created thread id=%s", thread.id)
        return thread

    def add_message(self, thread_id: str, role: str, content: str):
        """Add a message to a thread."""
        return self.agents_client.create_message(
            thread_id=thread_id,
            role=role,
            content=content,
        )

    def run_agent(self, thread_id: str, agent_id: str):
        """
        Start a run on a thread with the given agent.
        Returns the run object (may need polling for completion).
        """
        run = self.agents_client.create_run(
            thread_id=thread_id,
            agent_id=agent_id,
        )
        logger.info("Started run id=%s on thread=%s", run.id, thread_id)
        return run

    def get_run(self, thread_id: str, run_id: str):
        """Get the status of a run."""
        return self.agents_client.get_run(
            thread_id=thread_id,
            run_id=run_id,
        )

    def submit_tool_outputs(
        self, thread_id: str, run_id: str, tool_outputs: list[dict]
    ):
        """Submit tool call results back to the agent run."""
        return self.agents_client.submit_tool_outputs_to_run(
            thread_id=thread_id,
            run_id=run_id,
            tool_outputs=tool_outputs,
        )

    def get_messages(self, thread_id: str):
        """Get all messages in a thread."""
        return self.agents_client.list_messages(thread_id=thread_id)

    def cleanup_agent(self, agent_id: str):
        """Delete an agent when no longer needed."""
        try:
            self.agents_client.delete_agent(agent_id)
            logger.info("Deleted agent id=%s", agent_id)
        except Exception as e:
            logger.warning("Failed to delete agent %s: %s", agent_id, e)
