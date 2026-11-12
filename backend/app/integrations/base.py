from abc import ABC, abstractmethod


class Capability:
    def __init__(self, name: str, available: bool, reason: str = "", requires: list[str] | None = None):
        self.name = name
        self.available = available
        self.reason = reason
        self.requires = requires or []

    def to_dict(self):
        return {"name": self.name, "available": self.available, "reason": self.reason, "requires": self.requires}


class BaseIntegration(ABC):
    kind: str = "base"
    display_name: str = "Base"

    def __init__(self, user_id: str, account=None, integration=None, db=None):
        self.user_id = user_id
        self.account = account
        self.integration = integration
        self.db = db

    @abstractmethod
    def capabilities(self) -> list[Capability]:
        """Return list of capabilities and whether they are available."""
        ...

    @abstractmethod
    async def sync(self) -> dict:
        """Run a sync, ingest events. Return summary dict."""
        ...

    def normalize_event(self, raw: dict) -> dict:
        """Convert source-specific payload into unified event dict."""
        return raw

    async def revoke(self) -> None:
        pass

    def status(self) -> dict:
        return {"kind": self.kind, "name": self.display_name}
