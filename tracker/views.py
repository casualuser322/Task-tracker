import json

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.forms import modelformset_factory
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django.views.decorators.vary import vary_on_cookie

from accounts.models import TicketsUser
from taskboard.decorators import rate_limit, retry

from .decorators import group_access_required, project_access_required
from .forms import (
    CommentForm,
    GroupForm,
    ProjectForm,
    SecureAttachmentForm,
    TicketForm,
)
from .models import (
    Invitation,
    Project,
    SubTask,
    Ticket,
    TrackerGroup,
)


@cache_page(60 * 2)
@vary_on_cookie
@login_required
def group_list(request):
    user = request.user

    owned_groups = user.owned_groups.all()
    member_groups = user.attached_groups.all()

    return render(
        request,
        "groups/groups_main.html",
        {
            "owned_groups": owned_groups,
            "member_groups": member_groups,
        },
    )


@login_required
@rate_limit("create_group", limit=20, period=60)
def create_group(request):
    if request.method == "POST":
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.owner = request.user
            group.save()
            form.save_m2m()

            group.members.add(request.user)

            emails = request.POST.get("emails", "")
            if emails:
                for email in emails.split(","):
                    email = email.strip()
                    try:
                        target_user = TicketsUser.objects.get(email=email)
                        Invitation.objects.create(
                            owner=request.user,
                            target_user=target_user,
                            target_group=group,
                            invitation_type="group",
                        )
                    except TicketsUser.DoesNotExist:
                        continue

            messages.success(request, "Group is created!")
            return redirect("group_list")
    else:
        form = GroupForm()

    return render(
        request,
        "groups/groups_create.html",
        {
            "form": form,
        },
    )


@cache_page(60 * 2)
@vary_on_cookie
@login_required
@group_access_required
def group_view(request, group_id, group=None):
    projects = (
        group.projects.select_related("owner")
        .prefetch_related("members", "tickets")
        .order_by("-created_at")
    )

    all_members = group.members.all()
    if not all_members.filter(id=group.owner.id).exists():
        all_members = list(all_members) + [group.owner]

    return render(
        request,
        "groups/groups_view.html",
        {
            "group": group,
            "projects": projects,
            "members": all_members,
            "user_can_edit": request.user == group.owner,
            "user_is_member": request.user in group.members.all(),
        },
    )


@login_required
@rate_limit("edit_group", limit=20, period=60)
@group_access_required
def edit_group(request, group_id, group=None):
    user = request.user

    if user.id != group.owner.id:
        return HttpResponseForbidden(
            "You do not have permission to edit this group"
        )

    if request.method == "POST":
        form = GroupForm(request.POST, request.FILES, instance=group)
        if form.is_valid():
            with transaction.atomic():
                prtctd_group = TrackerGroup.objects.select_for_update().get(
                    id=group_id
                )

                prtctd_group.title = form.cleaned_data.get("title")
                prtctd_group.description = form.cleaned_data.get("description")
                prtctd_group.save()

            return redirect("group_detail", group_id=prtctd_group.id)
    else:
        form = GroupForm(instance=group)

    return render(
        request,
        "groups/groups_edit.html",
        {
            "form": form,
            "group": group,
        },
    )


@login_required
@rate_limit("delete_group_member", limit=20, period=60)
@group_access_required
@retry(max_attempts=3)
def delete_group_member(request, group_id, pk, group=None):
    user = request.user

    if user.id == group.owner.id and pk in group.attached_groups.all():
        group.members.remove(pk)

    return redirect(request.META.get("HTTP_REFERER", reverse("group_view")))


@login_required
@rate_limit("leave_group_member", limit=20, period=60)
@retry(max_attempts=3)
def leave_group_member(request, group_id):
    user = request.user
    group = get_object_or_404(TrackerGroup, id=group_id)

    if group.owner != user:
        if group.members.filter(id=user.id).exists():
            group.members.remove(user)
            messages.success(request, f"You left the group {group.title}.")
        else:
            messages.warning(request, "You are not a member of this group.")
    else:
        messages.error(request, "Group owners cannot leave their own group.")

    return redirect(
        request.META.get(
            "HTTP_REFERER", reverse("group_list", args=[group_id])
        )
    )


@login_required
@rate_limit("edit_project", limit=20, period=60)
@project_access_required
def edit_project(request, project_id, project=None):
    user = request.user

    if user.id != project.owner.id:
        return HttpResponseForbidden(
            "You do not have permission to edit this project"
        )

    if request.method == "POST":
        form = ProjectForm(request.POST, request.FILES, instance=project)
        if form.is_valid():
            with transaction.atomic():
                prtctd_project = Project.objects.select_for_update().get(
                    id=project_id
                )

                prtctd_project.title = form.cleaned_data.get("title")
                prtctd_project.description = form.cleaned_data.get(
                    "description"
                )
                prtctd_project.save()

            return redirect("project_details", project_id=prtctd_project.id)
    else:
        form = GroupForm(instance=project)

    return render(
        request,
        "projects/project_edit.html",
        {
            "form": form,
            "project": project,
        },
    )


@login_required
@rate_limit("delete_project", limit=20, period=60)
@group_access_required
@retry(max_attempts=3)
def delete_project(request, group_id, project_id, group=None):
    user = request.user
    project = get_object_or_404(Project, id=project_id)

    if user.id == project.owner.id:
        project.delete()

    return redirect(
        request.META.get(
            "HTTP_REFERER", reverse("group_view", args=[group_id])
        )
    )


@login_required
@rate_limit("user_email_autocomplete", limit=20, period=60)
@retry(max_attempts=3)
def user_email_autocomplete(request):
    query = request.GET.get("q", "")
    users = TicketsUser.objects.filter(email__icontains=query)[:10]
    results = [{"id": u.id, "email": u.email} for u in users]

    return JsonResponse(results, safe=False)


@login_required
@rate_limit("send_invitation", limit=20, period=60)
@group_access_required
@retry(max_attempts=3)
def send_invitation(request, group_id, group=None):
    current_user = request.user
    emails = request.POST.get("emails", "").strip()

    if emails:
        if group.owner.id == current_user.id:
            for email in [e.strip() for e in emails.split(",") if e.strip()]:
                user = get_object_or_404(TicketsUser, email=email)
                Invitation.objects.create(
                    owner=current_user,
                    target_user=user,
                    target_group=group,
                    invitation_type="group",
                )
        else:
            messages.error(
                request, "You don't have permission to send invitation"
            )

    return redirect(
        request.META.get(
            "HTTP_REFERER", reverse("group_view", args=[group_id])
        )
    )


@login_required
@rate_limit("group_delete", limit=20, period=60)
@group_access_required
@retry(max_attempts=3)
def group_delete(request, group_id, pk, group=None):
    if request.method == "POST":
        if group.owner == request.user:
            group.delete()
            messages.success(request, "Group deleted successfully!")
        else:
            messages.error(
                request, "You do not have permission to delete this group."
            )

    return redirect(
        request.META.get(
            "HTTP_REFERER", reverse("group_view", args=[group_id])
        )
    )


@cache_page(60 * 2)
@vary_on_cookie
@login_required
def project_list(request):
    user = request.user
    projects = user.projects.filter(members=user.id)
    owned_projects = user.owned_projects.all()

    return render(
        request,
        "projects/project_list.html",
        {
            "projects": projects,
            "owned_projects": owned_projects,
        },
    )


@login_required
@rate_limit("create_project", limit=20, period=60)
@group_access_required
def create_project(request, group_id, group=None):
    user = request.user
    if request.method == "POST":
        form = ProjectForm(request.POST)
        emails = request.POST.get("emails", "").split(",")

        if form.is_valid():
            project = form.save(commit=False)
            project.owner = user
            project.attached_group = group
            project.save()
            project.members.add(user)

            if emails:
                for email in emails:
                    email = email.strip()
                    coworker = TicketsUser.objects.filter(email=email).first()
                    if coworker:
                        project.members.add(coworker)
            messages.success(request, "Project is created!")
            return redirect(
                request.META.get(
                    "HTTP_REFERER", reverse("group_view", args=[group_id])
                )
            )
    else:
        form = ProjectForm()

    return render(request, "projects/create_project.html", {"form": form})


@cache_page(60 * 2)
@vary_on_cookie
@login_required
@project_access_required
def project_details(request, project_id, project=None):
    tickets = project.tickets.all()

    statuses = [
        {"key": "open", "label": "Open", "badge_class": "bg-secondary"},
        {
            "key": "in_progress",
            "label": "In Progress",
            "badge_class": "bg-warning text-dark",
        },
        {
            "key": "testing",
            "label": "Testing",
            "badge_class": "bg-info text-dark",
        },
        {"key": "done", "label": "Done", "badge_class": "bg-success"},
        {
            "key": "closed",
            "label": "Closed",
            "badge_class": "bg-dark text-white",
        },
    ]

    priority = [
        {"key": "low", "label": "Low", "badge_class": "badge-success"},
        {"key": "medium", "label": "Medium", "badge_class": "badge-warning"},
        {"key": "high", "label": "High", "badge_class": "badge-danger"},
    ]

    return render(
        request,
        "projects/project_details.html",
        {
            "project": project,
            "tickets": tickets,
            "statuses": statuses,
            "priority": priority,
        },
    )


@cache_page(60 * 2)
@vary_on_cookie
@login_required
def ticket_list(request):
    user = request.user
    user_tickets = Ticket.objects.filter(assignee=user.id)

    return render(
        request, "tickets/ticket_list.html", {"user_tickets": user_tickets}
    )


@require_POST
@csrf_protect
@rate_limit("update_task_status", limit=20, period=60)
@project_access_required
@retry(max_attempts=3)
def update_task_status(request, project_id, project=None):
    try:
        data = json.loads(request.body)
        task_id = data.get("task_id")
        status = data.get("status")
        task = get_object_or_404(Ticket, id=task_id, project_id=project_id)

        valid_statuses = [choice[0] for choice in Ticket.STATUS_CHOICES]
        if status not in valid_statuses:
            return JsonResponse(
                {"success": False, "error": "Invalid status"}, status=400
            )

        task.status = status
        task.save()

        return JsonResponse(
            {
                "success": True,
                "status": task.status,
                "status_display": task.get_status_display(),
            }
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_POST
@rate_limit("add_subtask", limit=20, period=60)
@retry(max_attempts=3)
def add_subtask(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if request.method == "POST":
        SubTask.objects.create(ticket=ticket, text=request.POST.get("subtask"))

    return redirect(
        "ticket_detail", project_id=ticket.project.id, ticket_id=ticket.id
    )


@login_required
@rate_limit("update_task_ajax", limit=20, period=60)
@project_access_required
@retry(max_attempts=3)
def update_task_ajax(request, project_id, ticket_id, task_id):
    if request.method == "POST":
        try:
            task = SubTask.objects.get(id=task_id, ticket_id=ticket_id)
            data = json.loads(request.body)
            task.is_done = data.get("completed", False)
            task.save()
            return JsonResponse({"status": "success"})
        except SubTask.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "Task not found"}, status=404
            )

    return JsonResponse({"status": "error"}, status=400)


@login_required
@rate_limit(
    "ticket_detail", limit=20, period=60
)  # TODO Temporary, before decompose
@project_access_required
def ticket_detail(request, project_id, ticket_id, project):  # TODO Decopose
    ticket = get_object_or_404(Ticket, id=ticket_id)

    comments = ticket.comments.all()
    attachments = ticket.attachments.all()
    subtasks = ticket.subtasks.all()

    SubTaskFormSet = modelformset_factory(
        SubTask,
        fields=("text", "is_done"),
        extra=0,
        widgets={
            "text": forms.TextInput(attrs={"class": "form-control"}),
            "is_done": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        },
    )

    form = TicketForm(instance=ticket, project=project)
    comment_form = CommentForm()
    attachment_form = SecureAttachmentForm()
    formset = SubTaskFormSet(queryset=subtasks)

    if request.method == "POST":
        if "add_comment" in request.POST:
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.ticket = ticket
                comment.author = request.user
                comment.save()
                messages.success(request, "Comment added!")
                return redirect(
                    "ticket_detail", project_id=project_id, ticket_id=ticket.id
                )

        elif "add_attachment" in request.POST:
            attachment_form = SecureAttachmentForm(request.POST, request.FILES)
            if attachment_form.is_valid():
                attachment = attachment_form.save(commit=False)
                attachment.ticket = ticket
                attachment.uploaded_by = request.user
                attachment.save()
                messages.success(request, "File attached!")
                return redirect(
                    "ticket_detail", project_id=project_id, ticket_id=ticket.id
                )
            else:
                messages.error(
                    request,
                    "Error attaching file. Please check the file type and size.",
                )

        elif "update_subtasks" in request.POST:
            formset = SubTaskFormSet(request.POST, queryset=subtasks)
            if formset.is_valid():
                formset.save()
                messages.success(request, "Subtasks updated!")
                return redirect(
                    "ticket_detail", project_id=project_id, ticket_id=ticket.id
                )

        elif "add_subtask" in request.POST:
            new_text = request.POST.get("new_subtask")
            if new_text:
                SubTask.objects.create(ticket=ticket, text=new_text)
                messages.success(request, "Subtask added!")
                return redirect(
                    "ticket_detail", project_id=project_id, ticket_id=ticket.id
                )

        else:
            form = TicketForm(request.POST, instance=ticket, project=project)
            if form.is_valid():
                form.save()
                messages.success(request, "Ticket updated successfully!")
                return redirect(
                    "ticket_detail", project_id=project_id, ticket_id=ticket.id
                )

    return render(
        request,
        "tickets/ticket_detail.html",
        {
            "project": project,
            "ticket": ticket,
            "comments": comments,
            "attachments": attachments,
            "comment_form": comment_form,
            "formset": formset,
            "attachment_form": attachment_form,
            "form": form,
            "PRIORITY_CHOICES": Ticket.PRIORITY_CHOICES,
        },
    )


@login_required
@rate_limit("create_ticket", limit=20, period=60)
@project_access_required
def create_ticket(request, project_id, project):
    if request.method == "POST":
        form = TicketForm(request.POST, project=project)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.project = project
            ticket.creator = request.user
            ticket.save()
            messages.success(request, "Ticket created!")
            return redirect("project_details", project_id=project.id)
    else:
        form = TicketForm(project=project)

    return render(
        request,
        "tickets/create_ticket.html",
        {
            "form": form,
            "project": project,
            "today": timezone.now().date(),
        },
    )


@login_required
@rate_limit("update_ticket", limit=20, period=60)
@project_access_required
def update_ticket(request, project_id, ticket_id, project=None):
    ticket = get_object_or_404(Ticket, id=ticket_id, project=project)

    if request.method == "POST":
        ticket_form = TicketForm(
            request.POST, instance=ticket, project=ticket.project
        )
        if ticket_form.is_valid():
            ticket_form.save()
            messages.success(request, "Ticket is updated")

            return redirect(
                "ticket_detail",
                project_id=ticket.project.id,
                ticket_id=ticket.id,
            )
    else:
        ticket_form = TicketForm(instance=ticket, project=ticket.project)

    return render(
        request,
        "tickets/ticket_form.html",
        {
            "form": ticket_form,
            "ticket": ticket,
        },
    )


def index(request):
    user = request.user
    if user.is_authenticated:
        return redirect("group_list")
    else:
        return redirect("register")
