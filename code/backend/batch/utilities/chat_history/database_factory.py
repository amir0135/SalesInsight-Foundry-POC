# database_factory.py
import os
from ..helpers.env_helper import EnvHelper
from .cosmosdb import CosmosConversationClient
from .postgresdbservice import PostgresConversationClient
from ..helpers.azure_credential_utils import get_azure_credential
from ..helpers.config.database_type import DatabaseType


class DatabaseFactory:
    @staticmethod
    def get_conversation_client():
        env_helper: EnvHelper = EnvHelper()

        # Allow overriding the chat history database independently of DATABASE_TYPE.
        # This lets local dev use PostgreSQL for chat history while keeping
        # CosmosDB as the global DATABASE_TYPE (preserving orchestration settings).
        chat_history_db_type = os.getenv(
            "CHAT_HISTORY_DATABASE_TYPE", env_helper.DATABASE_TYPE
        )

        if chat_history_db_type == DatabaseType.POSTGRESQL.value:
            return DatabaseFactory._create_postgres_client(env_helper)
        elif chat_history_db_type == DatabaseType.COSMOSDB.value:
            return DatabaseFactory._create_cosmos_client(env_helper)
        else:
            raise ValueError(
                "Unsupported database type for chat history. "
                "Set CHAT_HISTORY_DATABASE_TYPE or DATABASE_TYPE to 'CosmosDB' or 'PostgreSQL'."
            )

    @staticmethod
    def _create_cosmos_client(env_helper):
        DatabaseFactory._validate_env_vars(
            [
                "AZURE_COSMOSDB_ACCOUNT",
                "AZURE_COSMOSDB_DATABASE",
                "AZURE_COSMOSDB_CONVERSATIONS_CONTAINER",
            ],
            env_helper,
        )

        cosmos_endpoint = (
            f"https://{env_helper.AZURE_COSMOSDB_ACCOUNT}.documents.azure.com:443/"
        )
        credential = (
            get_azure_credential(env_helper.MANAGED_IDENTITY_CLIENT_ID)
            if not env_helper.AZURE_COSMOSDB_ACCOUNT_KEY
            else env_helper.AZURE_COSMOSDB_ACCOUNT_KEY
        )
        return CosmosConversationClient(
            cosmosdb_endpoint=cosmos_endpoint,
            credential=credential,
            database_name=env_helper.AZURE_COSMOSDB_DATABASE,
            container_name=env_helper.AZURE_COSMOSDB_CONVERSATIONS_CONTAINER,
            enable_message_feedback=env_helper.AZURE_COSMOSDB_ENABLE_FEEDBACK,
        )

    @staticmethod
    def _create_postgres_client(env_helper):
        # Support dedicated chat history PG vars (for local dev override)
        user = os.getenv("CHAT_HISTORY_PG_USER") or getattr(env_helper, "POSTGRESQL_USER", "")
        host = os.getenv("CHAT_HISTORY_PG_HOST") or getattr(env_helper, "POSTGRESQL_HOST", "")
        database = os.getenv("CHAT_HISTORY_PG_DATABASE") or getattr(env_helper, "POSTGRESQL_DATABASE", "")
        password = os.getenv("CHAT_HISTORY_PG_PASSWORD", "")
        port = int(os.getenv("CHAT_HISTORY_PG_PORT", "5432"))

        if not all([user, host, database]):
            raise ValueError(
                "PostgreSQL chat history requires CHAT_HISTORY_PG_USER, "
                "CHAT_HISTORY_PG_HOST, and CHAT_HISTORY_PG_DATABASE "
                "(or POSTGRESQL_USER, POSTGRESQL_HOST, POSTGRESQL_DATABASE)."
            )

        return PostgresConversationClient(
            user=user,
            host=host,
            database=database,
            password=password or None,
            port=port,
        )

    @staticmethod
    def _validate_env_vars(required_vars, env_helper):
        for var in required_vars:
            if not getattr(env_helper, var, None):
                raise ValueError(f"Environment variable {var} is required.")
