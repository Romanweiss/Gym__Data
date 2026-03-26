from dataclasses import dataclass, field


@dataclass(frozen=True)
class ActorContext:
    actor_id: str | None = None
    user_id: str | None = None
    trainer_id: str | None = None
    client_id: str | None = None
    roles: tuple[str, ...] = field(default_factory=tuple)
    authenticated: bool = False


@dataclass(frozen=True)
class SessionScope:
    session_id: str | None = None
    actor: ActorContext = field(default_factory=ActorContext)
    auth_mode: str = "stage1_single_user"

