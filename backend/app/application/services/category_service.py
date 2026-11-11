"""Category application service: list, create, rename, deactivate, delete."""
from __future__ import annotations

from ...domain.authorization.permissions import Permission
from ...domain.settings.entities import Category
from ...domain.shared.clock import Clock
from ...domain.shared.errors import AuthorizationError, ConflictError, NotFoundError
from ...domain.tasks.value_objects import normalize_category
from ..commands import CreateCategoryCommand, UpdateCategoryCommand
from ..dto import CategoryDTO
from ..ports.clock import IdGenerator
from ..ports.identity import AuthorizationPort
from ..ports.persistence import DatabaseFactoryPort


class CategoryService:
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

    def list_categories(self, principal, *, include_inactive: bool = False) -> list[CategoryDTO]:
        self._authorize(principal, Permission.SETTINGS_READ)
        with self._database.create() as uow:
            return [
                CategoryDTO(id=c.id, name=c.name, active=c.active, is_default=c.is_default)
                for c in uow.categories.list(principal.id, include_inactive=include_inactive)
            ]

    def create_category(self, principal, command: CreateCategoryCommand) -> CategoryDTO:
        self._authorize(principal, Permission.CATEGORIES_MANAGE)
        name = normalize_category(command.name)
        with self._database.create() as uow:
            if uow.categories.find_by_name(name, principal.id) is not None:
                raise ConflictError(f"Category {name!r} already exists")
            category = Category(
                id=self._ids.new_id(),
                owner_id=principal.id,
                name=name,
                created_at=self._clock.now_utc(),
            )
            uow.categories.save(category)
            uow.commit()
            return CategoryDTO(id=category.id, name=category.name, active=True, is_default=False)

    def update_category(self, principal, category_id: str, command: UpdateCategoryCommand) -> CategoryDTO:
        self._authorize(principal, Permission.CATEGORIES_MANAGE)
        with self._database.create() as uow:
            category = uow.categories.get_by_id(category_id, principal.id)
            if category is None:
                raise NotFoundError(f"Category {category_id} not found")
            if command.name is not None:
                new_name = normalize_category(command.name)
                existing = uow.categories.find_by_name(new_name, principal.id)
                if existing is not None and existing.id != category.id:
                    raise ConflictError(f"Category {new_name!r} already exists")
                category.rename(new_name)
            if command.active is not None:
                category.active = command.active
            uow.categories.save(category)
            uow.commit()
            return CategoryDTO(
                id=category.id, name=category.name, active=category.active, is_default=category.is_default
            )

    def delete_category(self, principal, category_id: str) -> None:
        self._authorize(principal, Permission.CATEGORIES_MANAGE)
        with self._database.create() as uow:
            category = uow.categories.get_by_id(category_id, principal.id)
            if category is None:
                raise NotFoundError(f"Category {category_id} not found")
            if category.is_default:
                # Default categories are deactivated, not deleted, so a demo
                # reset can restore them cleanly.
                category.deactivate()
                uow.categories.save(category)
            else:
                uow.categories.delete(category_id, principal.id)
            uow.commit()

    def restore_defaults(self, uow, owner_id: str, now) -> int:  # noqa: ANN001
        """Ensure every default category exists and is active. Returns count restored."""
        from ...domain.settings.entities import DEFAULT_CATEGORIES

        restored = 0
        for name in DEFAULT_CATEGORIES:
            existing = uow.categories.find_by_name(name, owner_id)
            if existing is None:
                uow.categories.save(
                    Category(
                        id=self._ids.new_id(),
                        owner_id=owner_id,
                        name=name,
                        created_at=now,
                        is_default=True,
                    )
                )
                restored += 1
            elif not existing.active:
                existing.active = True
                uow.categories.save(existing)
                restored += 1
        return restored
