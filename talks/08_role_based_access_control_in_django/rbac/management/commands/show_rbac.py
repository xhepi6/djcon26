"""Dump the RBAC state: role hierarchy, closure rows, and user assignments."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from rbac.models import Role, RoleAncestry, UserRole

User = get_user_model()


def _print_tree(stdout, role: Role, indent: int = 0) -> None:
    perms = ", ".join(
        sorted(f"{p.content_type.app_label}.{p.codename}" for p in role.permissions.all())
    ) or "—"
    stdout.write(f"{'  ' * indent}• {role.name}  [{perms}]")
    for child in role.children.order_by("name"):
        _print_tree(stdout, child, indent + 1)


class Command(BaseCommand):
    help = "Print the role hierarchy, the RoleAncestry closure, and every user's assignments."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Roles (hierarchy):"))
        for root in Role.objects.filter(parent__isnull=True).order_by("name"):
            _print_tree(self.stdout, root)
        self.stdout.write("")

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"RoleAncestry closure ({RoleAncestry.objects.count()} rows):"
        ))
        self.stdout.write("  ancestor               descendant             depth")
        self.stdout.write("  " + "-" * 56)
        for row in RoleAncestry.objects.select_related("ancestor", "descendant").order_by(
            "descendant__name", "depth"
        ):
            self.stdout.write(
                f"  {row.ancestor.name:<22} {row.descendant.name:<22} {row.depth}"
            )
        self.stdout.write("")

        self.stdout.write(self.style.MIGRATE_HEADING("User assignments:"))
        for user in User.objects.order_by("username"):
            flag = " (superuser)" if user.is_superuser else ""
            self.stdout.write(f"  {user.username}{flag}")
            assignments = UserRole.objects.filter(user=user).select_related("role", "content_type")
            if not assignments:
                self.stdout.write("      (none)")
                continue
            for a in assignments:
                where = "globally" if a.content_type_id is None else f"on {a.scope}"
                when = "" if a.expires_at is None else f" — expires {a.expires_at.isoformat(timespec='seconds')}"
                self.stdout.write(f"      → {a.role.name} {where}{when}")
