from app.models.auth import User

ACTIVE_USER_STATUS = 1
SUPER_ADMIN_ROLE = "super_admin"
WILDCARD_PERMISSION = "*"


class AuthPolicy:
    def can_login(self, user: User) -> bool:
        return user.status == ACTIVE_USER_STATUS

    def token_permissions(
        self,
        *,
        roles: set[str],
        permissions: set[str],
    ) -> set[str]:
        if SUPER_ADMIN_ROLE in roles:
            return {WILDCARD_PERMISSION}
        return permissions

    def has_permission(self, permissions: set[str], code: str) -> bool:
        return WILDCARD_PERMISSION in permissions or code in permissions
