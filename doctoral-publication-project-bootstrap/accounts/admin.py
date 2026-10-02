from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.urls import path, reverse
from audit.admin import AuditedAdminMixin
from .forms import AccountImportForm, UserRoleActionForm
from .models import Role, User, UserRole
from .services import can_manage_accounts, import_accounts, parse_account_workbook, replace_user_role

@admin.register(User)
class AuditedUserAdmin(AuditedAdminMixin, UserAdmin):
    audit_label = "account"
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "last_login")
    ordering = ("-last_login", "username")
    readonly_fields = ("last_login", "date_joined")
    action_form = UserRoleActionForm
    actions = ("replace_selected_project_role",)
    change_list_template = "admin/accounts/user/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("bulk-import/", self.admin_site.admin_view(self.bulk_import_view), name="accounts_user_bulk_import"),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["can_bulk_manage_accounts"] = can_manage_accounts(request.user)
        return super().changelist_view(request, extra_context=extra_context)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not can_manage_accounts(request.user):
            actions.pop("replace_selected_project_role", None)
        return actions

    def bulk_import_view(self, request):
        if not can_manage_accounts(request.user):
            raise PermissionDenied("僅限系統管理員批量建立帳號。")
        form = AccountImportForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            try:
                accounts = parse_account_workbook(form.cleaned_data["workbook"])
                created = import_accounts(actor=request.user, accounts=accounts)
            except ValidationError as exc:
                form.add_error("workbook", exc)
            else:
                self.message_user(request, f"已建立 {len(created)} 個使用者。", messages.SUCCESS)
                return redirect(reverse("admin:accounts_user_changelist"))
        return render(request, "admin/accounts/user/bulk_import.html", {
            **self.admin_site.each_context(request), "title": "批量建立使用者", "form": form,
        })

    @admin.action(description="批量設定選取使用者的權限群組")
    def replace_selected_project_role(self, request, queryset):
        if not can_manage_accounts(request.user):
            raise PermissionDenied("僅限系統管理員變更權限群組。")
        role_slug = request.POST.get("role_slug")
        if role_slug not in {"advisor", "student", "admin"}:
            self.message_user(request, "請先選擇權限群組。", messages.ERROR)
            return
        try:
            for user in queryset:
                replace_user_role(actor=request.user, user=user, role_slug=role_slug)
        except (ValidationError, Role.DoesNotExist) as exc:
            self.message_user(request, "; ".join(exc.messages), messages.ERROR)
            return
        self.message_user(request, f"已更新 {queryset.count()} 個使用者的權限群組。", messages.SUCCESS)


@admin.register(Role)
class RoleAdmin(AuditedAdminMixin, admin.ModelAdmin):
    audit_label = "role"


@admin.register(UserRole)
class UserRoleAdmin(AuditedAdminMixin, admin.ModelAdmin):
    audit_label = "user_role"
    list_display = ("user", "role")
