from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

from .models import Project, TrackerGroup


def group_access_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, group_id, *args, **kwargs):
        group = get_object_or_404(TrackerGroup, id=group_id)

        if not (
            request.user == group.owner or request.user in group.members.all()
        ):
            return PermissionDenied("No access to this group")

        return view_func(request, group_id, *args, group=group, **kwargs)

    return _wrapped_view


def project_access_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, project_id, *args, **kwargs):
        project = get_object_or_404(Project, id=project_id)

        if not (
            request.user == project.owner
            or request.user in project.members.all()
        ):
            return PermissionDenied("No access to this project")

        return view_func(request, project_id, *args, project=project, **kwargs)

    return _wrapped_view
