"""Settings application service."""
from __future__ import annotations

from ...domain.authorization.permissions import Permission
from ...domain.settings.entities import DEFAULT_CATEGORIES, DEFAULT_TIMEZONE, OperatorSettings
from ...domain.shared.clock import Clock
from ...domain.shared.errors import AuthorizationError
from ..commands import UpdateSettingsCommand
from ..dto import CategoryDTO, SettingsDTO
from ..ports.clock import IdGenerator
from ..ports.identity import AuthorizationPort
from ..ports.persistence import DatabaseFactoryPort


class SettingsService:
    def __init__(
        self,
        database: DatabaseFactoryPort,
        authorizer: AuthorizationPort,
        clock: Clock,
        ids: IdGenerator,
    ) -> None:
        self._database = database
        self._authorizer = authorizer
        self._clock = clock
        self._ids = ids

    def _authorize(self, principal, permission: Permission) -> None:
        decision = self._authorizer.authorize(principal, permission)
        if not decision.allowed:
            raise AuthorizationError(decision.reason, code=decision.code)

    def get_settings(self, principal) -> SettingsDTO:
        self._authorize(principal, Permission.SETTINGS_READ)
        with self._database.create() as uow:
            settings, created = self._ensure(uow, principal)
            if uow.categories.count(principal.id) == 0:
                self._seed_default_categories(uow, principal.id, created=True)
                created = True
            if created:
                uow.commit()
            categories = uow.categories.list(principal.id, include_inactive=True)
            return SettingsDTO(
                warning_window_days=settings.warning_window_days,
                timezone=settings.timezone,
                categories=[
                    CategoryDTO(id=c.id, name=c.name, active=c.active, is_default=c.is_default) for c in categories
                ],
            )

    def update_settings(self, principal, command: UpdateSettingsCommand) -> SettingsDTO:
        self._authorize(principal, Permission.SETTINGS_UPDATE)
        with self._database.create() as uow:
            settings, _ = self._ensure(uow, principal)
            settings.update(
                self._clock.now_utc(),
                warning_window_days=command.warning_window_days,
                timezone=command.timezone,
            )
            uow.settings.save(settings)
            uow.commit()
            categories = uow.categories.list(principal.id, include_inactive=True)
            return SettingsDTO(
                warning_window_days=settings.warning_window_days,
                timezone=settings.timezone,
                categories=[
                    CategoryDTO(id=c.id, name=c.name, active=c.active, is_default=c.is_default) for c in categories
                ],
            )

    def _seed_default_categories(self, uow, owner_id: str, *, created: bool) -> None:  # noqa: ANN001
        from ...domain.settings.entities import Category

        now = self._clock.now_utc()
        for name in DEFAULT_CATEGORIES:
            uow.categories.save(
                Category(
                    id=self._ids.new_id(),
                    owner_id=owner_id,
                    name=name,
                    created_at=now,
                    is_default=True,
                )
            )

    def _ensure(self, uow, principal) -> tuple[OperatorSettings, bool]:  # noqa: ANN001
        """Return (settings, created).  Creates defaults if missing."""
        settings = uow.settings.get(principal.id)
        if settings is None:
            settings = OperatorSettings(
                owner_id=principal.id,
                warning_window_days=3,
                timezone=principal.timezone or DEFAULT_TIMEZONE,
            )
            uow.settings.save(settings)
            return settings, True
        return settings, False

    def default_categories(self) -> tuple[str, ...]:
        return DEFAULT_CATEGORIES
