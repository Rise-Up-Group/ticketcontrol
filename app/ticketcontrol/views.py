import logging

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect, Http404, JsonResponse
from django.core.validators import validate_email
from django.shortcuts import get_object_or_404, get_list_or_404
from django.shortcuts import render, redirect

from .models import *

logger = logging.getLogger(__name__)


def render_error(request, title, message):
    context = {'title': title, 'message': message}
    return render(request, "error.html", context)

def dashboard_view(request):
    tickets = Ticket.objects.filter(owner=request.user.id)
    context = {'tickets': tickets}
    return render(request, "dashboard.html", context)


def home_view(request):
    return render(request, "home.html")


##TODO: fix
@login_required()
def mytickets_view(request):
    context = {"tickets": Ticket.objects.filter(owner=request.user.id)}
    return render(request, "ticket/manage.html", context)

@login_required()
def ticket_view(request, id):
    id = str(id)  # TODO: no conversion

    context = {}
    try:
        ticket = get_object_or_404(Ticket, pk=id)
        try:
            comments = get_list_or_404(Comment, ticket_id=ticket.id)
            try:
                category = get_list_or_404(Category)
                context = {"ticket": ticket, "moderator": ticket.moderator.all(),
                           "participants": ticket.participating.all(), "comments": comments, "category": category}
                return render(request, "ticket/detail.html", context)
            except Http404:
                return render_error(request, "404 - Not Found", "Unable to load Category")
        except Http404:
            return render_error(request, "404 - Not Found", "Comments in Ticket " + id + " Not Found")

        try:
            category = get_list_or_404(Category)
            context = {"ticket": ticket, "moderator": ticket.moderator.all(),
                       "participants": ticket.participating.all(), "comments": comments, "category": category}
            return render(request, "ticket/detail.html", context)
        except Http404:
            return render_error(request, "404 - Not Found", "Unable to load Category")
    except Http404:
        return render_error(request, "404 - Not Found", "Ticket " + id + " Not Found")


def handler404(request, exception, template_name="error.html"):
    response = HttpResponse("404 page")  # TODO: render template
    response.status_code = 404
    return response


def logout_view(request):
    logout(request)
    return redirect("/")


def login_view(request):
    error = ""
    next = request.GET.get("next", False)
    if next == False:
        next = request.POST.get("next", False)
    if request.method == 'POST':
        username = str(request.POST['username'])
        password = request.POST['password']
        try:
            validate_email(username)
            try:
                user = User.objects.get(email=username)
            except ObjectDoesNotExist:
                user = None
        except ValidationError:
            try:
                user = User.objects.get(username=username)
            except ObjectDoesNotExist:
                user = None

        if user is not None and user.check_password(password):
            if user.is_active:
                login(request, user)
                if next is not False:
                    return HttpResponseRedirect(next)
                return redirect("dashboard")
            else:
                error = "User is not activated"
        else:
            error = "Wrong username or password"

    return render(request, "user/login.html", {"error": error, "next": next})


def register_view(request):
    if request.method == 'POST':
        password = request.POST['password']
        confirmPassword = request.POST['confirm_password']
        if password == confirmPassword:
            user = User.add_user(request.POST['email'], request.POST['firstname'], request.POST['lastname'],
                                 request.POST['username'], password, None, 1)  # None: groups, 1: is_active
            login(request, user)
            return redirect("profile")
        else:
            # Should not happen anyway
            return render_error(request, "Passwords do not match", "")
    return render(request, "user/register.html")


@permission_required("ticketcontrol.add_user")
def create_user_view(request):
    if (request.method == 'POST'):
        password = request.POST['password']
        groups = None
        if request.user.has_perm("ticketcontrol.change_user_permission"):
            groups = request.POST.getlist("groups")
        User.add_user(request.POST['email'], request.POST['firstname'], request.POST['lastname'],
                      request.POST['username'], password, groups, request.POST.get("is_active", False) == "on")
        return redirect("manage_users")
    return render(request, "user/create.html", {"groups": Group.objects.all(),
                                                "can_change_permission": request.user.has_perm(
                                                    "ticketcontrol.change_user_permission")})


@permission_required("ticketcontrol.view_user")
def manage_users_view(request):
    return render(request, "user/manage.html",
                  {"users": User.objects.all(), "can_create": request.user.has_perm("ticketcontrol.create_user"),
                   "can_change": request.user.has_perm("ticketcontrol.change_user"),
                   "can_delete": request.user.has_perm("ticketcontrol.delete_user")})


@login_required()
def user_details_view(request, id):
    if request.user.has_perm("ticketcontrol.view_user") or request.user.id == id:
        return render(request, "user/details.html", {"user": User.objects.get(id=id),
                                                     "can_change": request.user.has_perm(
                                                         "ticketcontrol.change_user") or request.user.id == id})
    return redirect("login")


@login_required()
def user_live_search(request, typed_username):
    some_users = User.objects.filter(username__contains=typed_username)[:10]
    res = []
    for user in some_users:
        newUser = {"username": user.username, "first_name": user.first_name, "last_name": user.last_name, "id": user.id}
        res.append(newUser)
    return JsonResponse(res, safe=False) # It's ok. Disables typecheck for dict. Make sure to only pass an array


def unrestricted_edit_user_view(request, id, changePermission, deletePermission):
    if request.method == 'POST':
        password = request.POST['password']
        passwordRetype = request.POST['password_retype']
        if password == "" or password == passwordRetype:
            groups = None
            if request.user.has_perm("ticketcontrol.change_user_permission"):
                groups = request.POST.getlist("groups")
            User.update_user(id, request.POST['email'], request.POST['firstname'], request.POST['lastname'],
                             request.POST['username'], password, groups, request.POST.get("is_active", False) == "on")
            return redirect("user_details", id=id)
        else:
            # Should not happen anyway
            return render_error(request, "Passwords do not match", "")
    user = get_object_or_404(User, pk=id)
    groups = []
    for group in user.groups.all():
        groups.append(group.id)
    return render(request, "user/edit.html", {"user": user, "userGroups": groups, "groups": Group.objects.all(),
                                              "can_change_permission": request.user.has_perm(
                                                  "ticketcontrol.change_user_permission"),
                                              "can_change": changePermission, "can_delete": deletePermission})


@login_required()
def edit_user_view(request, id):
    if request.user.has_perm("ticketcontrol.change_user") or request.user.id == id:
        return unrestricted_edit_user_view(request, id, True,
                                           request.user.has_perm("ticketcontrol.delete_user") or request.user.id == id)
    return redirect("login")


@login_required()
def profile_view(request):
    return edit_user_view(request, request.user.id)


def unrestricted_delete_user_view(request, id):
    if request.method == 'POST':
        User.delete_user(id)
        return redirect("manage_users")
    return render(request, "user/delete.html", {"user": get_object_or_404(User, pk=id)})


@permission_required("ticketcontrol.delete_user")
def restricted_delete_user_view(request, id):
    return unrestricted_delete_user_view(request, id)


@login_required()
def delete_user_view(request, id):
    if (request.user.id == id):
        return unrestricted_delete_user_view(request, id)
    return restricted_delete_user_view(request, id)


@permission_required("auth.view_group")
def manage_groups_view(request):
    return render(request, "user/group/manage.html",
                  {"groups": Group.objects.all(), "can_create": request.user.has_perm("ticketcontrol.create_user")})


@permission_required("auth.create_group")
def create_group_view(request):
    if request.method == 'POST':
        group = Group.objects.create(name=request.POST['name'])
        permissions = request.POST.getlist("permissions")
        allPermissions = Permission.objects.all().values_list("id", flat=True)
        for permission in permissions:
            inAllPermissions = False
            for perm in allPermissions:
                if int(perm) == int(permission):
                    inAllPermissions = True
            if inAllPermissions:
                group.permissions.add(permission)
        group.save()
        return redirect("manage_groups")
    return render(request, "user/group/create.html", {"permissions": Permission.objects.all()})


@permission_required("auth.view_group")
def edit_group_view(request, id):
    canEdit = request.user.has_perm("auth.change_group")
    group = get_object_or_404(Group, id=id)
    if request.method == 'POST' and canEdit:
        if group.name != "admin" and group.name != "moderator" and group.name != "user":
            group.name = request.POST['name']
        if group.name != "admin":  # admin is superuser anyway
            groupPermissions = group.permissions.all()
            permissions = request.POST.getlist("permissions")
            allPermissions = Permission.objects.all().values_list("id", flat=True)
            for permission in groupPermissions:
                if not permission.id in permissions:
                    group.permissions.remove(permission.id)

            for permission in permissions:
                inGroupPermissions = False
                for perm in groupPermissions:
                    if perm.id == permission:
                        inGroupPermissions = True
                inAllPermissions = False
                for perm in allPermissions:
                    if int(perm) == int(permission):
                        inAllPermissions = True
                if not inGroupPermissions and inAllPermissions:
                    group.permissions.add(permission)
            group.save()
            return redirect("manage_groups")
        return render_error(request, "Unable to edit group",
                            "Editing default group \"" + group.name + "\" is not allowed.")
    groupPermissions = []
    for permissionId in group.permissions.all().values_list("id", flat=True):
        groupPermissions.append(permissionId)
    return render(request, "user/group/edit.html",
                  {"group": group, "group_permissions": groupPermissions, "permissions": Permission.objects.all(),
                   "can_change": canEdit, "can_delete": request.user.has_perm(
                      "ticketcontrol.delete_group") and group.name != "admin" and group.name != "moderator" and group.name != "user"})


@permission_required("auth.delete_group")
def delete_group_view(request, id):
    group = Group.objects.get(id=id)
    if group.name == "admin" or group.name == "moderator" or group.name == "user":
        return render_error(request, "Unable to delete group",
                            "Deleting default group \"" + group.name + "\" is not allowed.")
    if request.method == 'POST':
        group.delete()
        return redirect("manage_groups")
    return render(request, "user/group/delete.html", {"group": group})


@login_required()
def ticket_new_view(request):
    if request.method == 'POST':
        Ticket.add_ticket(request.POST["title"], request.POST["description"], User.objects.get(id=request.user.id),
                          Category.objects.get(id=request.POST["category"]))
        return redirect('/ticket/my')
    else:
        try:
            category = get_list_or_404(Category)
            context = {"category": category}
            return render(request, "ticket/new.html", context)
        except Http404:
            return render_error(request, "404 - Not Found", "Unable to load Category")


@login_required()
def ticket_comment_add(request, id):
    if request.method == 'POST':
        ticket = Ticket.objects.get(id=id)
        ticket.add_comment(request.POST["comment"], User.objects.get(id=request.user.id))
        return redirect('/ticket/' + str(id))
