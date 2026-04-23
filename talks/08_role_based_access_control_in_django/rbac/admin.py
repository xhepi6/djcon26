from django.contrib import admin

from .models import Role, RoleAncestry, UserRole

admin.site.register(Role)
admin.site.register(RoleAncestry)
admin.site.register(UserRole)
