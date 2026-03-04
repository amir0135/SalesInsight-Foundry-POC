import os
from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
from azure.identity.aio import (
    ManagedIdentityCredential as AioManagedIdentityCredential,
    DefaultAzureCredential as AioDefaultAzureCredential,
)


async def get_azure_credential_async(client_id=None):
    """
    Returns an Azure credential asynchronously based on the application environment.

    If the environment is 'dev', it uses DefaultAzureCredential with IMDS excluded for faster auth.
    Otherwise, it uses AioManagedIdentityCredential.

    Args:
        client_id (str, optional): The client ID for the Managed Identity Credential.

    Returns:
        Credential object: Either AioDefaultAzureCredential or AioManagedIdentityCredential.
    """
    if os.getenv("APP_ENV", "prod").lower() == "dev":
        # Exclude managed identity to avoid slow IMDS probing on local dev
        return AioDefaultAzureCredential(exclude_managed_identity_credential=True)
    else:
        return AioManagedIdentityCredential(client_id=client_id)


def get_azure_credential(client_id=None):
    """
    Returns an Azure credential based on the application environment.

    If the environment is 'dev', it uses DefaultAzureCredential with IMDS excluded for faster auth.
    Otherwise, it uses ManagedIdentityCredential.

    Args:
        client_id (str, optional): The client ID for the Managed Identity Credential.

    Returns:
        Credential object: Either DefaultAzureCredential or ManagedIdentityCredential.
    """
    if os.getenv("APP_ENV", "prod").lower() == "dev":
        # Exclude managed identity to avoid slow IMDS probing on local dev
        return DefaultAzureCredential(exclude_managed_identity_credential=True)
    else:
        return ManagedIdentityCredential(client_id=client_id)
