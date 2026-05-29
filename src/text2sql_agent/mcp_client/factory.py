"""Registry-based MCP client factory.

Register new backends by decorating the class:

    @mcp_client_registry.register("bigquery")
    class BigQueryMCPClient(BaseSQLMCPClient):
        ...

Then instantiate via:

    client = create_mcp_client("postgresql")
"""

from typing import Callable

from text2sql_agent.mcp_client.base import BaseSQLMCPClient


class _MCPClientRegistry:
    """Registry mapping backend names to client classes."""

    def __init__(self) -> None:
        self._backends: dict[str, type[BaseSQLMCPClient]] = {}

    def register(self, name: str) -> Callable[[type[BaseSQLMCPClient]], type[BaseSQLMCPClient]]:
        """Decorator to register an MCP client class under a backend name."""

        def decorator(cls: type[BaseSQLMCPClient]) -> type[BaseSQLMCPClient]:
            self._backends[name] = cls
            return cls

        return decorator

    @property
    def available_backends(self) -> list[str]:
        return list(self._backends.keys())

    def get(self, name: str) -> type[BaseSQLMCPClient]:
        if name not in self._backends:
            available = ", ".join(self._backends.keys()) or "(none)"
            raise ValueError(
                f"Unknown MCP backend: '{name}'. Available: {available}"
            )
        return self._backends[name]


mcp_client_registry = _MCPClientRegistry()


def create_mcp_client(backend: str | None = None, **kwargs) -> BaseSQLMCPClient:
    """Create an MCP client instance by backend name.

    Args:
        backend: Backend identifier (e.g. "postgresql", "bigquery").
                 If None, uses settings.mcp_backend.
        **kwargs: Passed to the client constructor.
    """
    if backend is None:
        from text2sql_agent.config import settings
        backend = settings.mcp_backend

    cls = mcp_client_registry.get(backend)
    return cls(**kwargs)
