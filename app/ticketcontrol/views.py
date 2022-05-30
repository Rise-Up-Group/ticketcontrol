import json
import logging
import os

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.core.validators import validate_email
from django.shortcuts import render, redirect
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
# from settings import general

from django.views.static import serve

from .models import *

logger = logging.getLogger(__name__)


def render_error(request, status, message=""):
    title_list = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method not allowed",
        406: "Not Acceptable",
        409: "Conflict",
        410: "Gone",
        411: "Length Required",
        500: "Internal Server Error"
    }
    title = str(status) + " - " + title_list.get(status, "")

    context = {'title': title, 'message': message, 'status': status, 'meme_mode': settings.GENERAL['meme_mode']}
    return render(request, "error.html", context, status=status)


def dashboard_view(request):
    if request.user.is_authenticated:
        own_tickets = Ticket.objects.filter(owner=request.user.id, hidden=False)
        part_tickets = Ticket.objects.filter(participating=request.user.id, hidden=False).exclude(owner=request.user.id)
        context = {'tickets': {'own': own_tickets, 'part': part_tickets}}
        return render(request, "dashboard.html", context)
    else:
        return render(request, "home.html")


@login_required()
def mytickets_view(request):
    own_tickets = Ticket.objects.filter(owner=request.user.id, hidden=False)
    part_tickets = Ticket.objects.filter(participating=request.user.id).exclude(owner=request.user.id, moderator=request.user.id, hidden=False)
    mod_tickets = Ticket.objects.filter(moderator=request.user.id).exclude(owner=request.user.id, hidden=False)
    context = {'tickets': {'own': own_tickets, 'part': part_tickets, 'mod': mod_tickets}}
    return render(request, "ticket/manage.html", context)


@login_required()
def ticket_view(request, id):
    id = str(id)  # TODO: no conversion

    try:
        ticket = Ticket.objects.get(pk=id)
        if ticket.hidden and not request.user.has_perm("ticketcontrol.unhide_ticket"):
            return render_error(request, 404, "Ticket does not exist")
        comments = Comment.objects.filter(ticket_id=ticket.id)

        categories = Category.objects.all()
        context = {"ticket": ticket, "moderators": ticket.moderator.all(),
                   "participants": ticket.participating.all(), "comments": comments, "categories": categories}
        return render(request, "ticket/detail.html", context)
    except Ticket.DoesNotExist:
        return render_error(request, 404, "Ticket does not exist")


def handler404(request, exception, template_name="error.html"):
    return render_error(request, 404)


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
            if user.is_active and user.email_confirmed:
                login(request, user)
                if next is not False:
                    return HttpResponseRedirect(next)
                return redirect("dashboard")
            else:
                error = "User is not activated or email address is not confirmed"
        else:
            error = "Wrong username or password"
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "user/login.html", {"error": error, "next": next})


def register_view(request):
    if request.method == 'POST':
        password = request.POST['password']
        confirmPassword = request.POST['confirm_password']
        if password == confirmPassword:
            if len(password) < 8:
                return render_error(request, 411, "Password must be at least 8 characters long")
            if not User.objects.filter(email=request.POST['email']).exists() and not User.objects.filter(
                    username=request.POST['username']).exists():
                user = User.add_user("", request.POST['firstname'], request.POST['lastname'],
                                     request.POST['username'], password, groups=None, is_active=True,
                                     email_confirmed=False)
                user.new_email = request.POST['email']
                user.save()
                User.send_emailverification_mail(user, request)
                return render(request, "user/activate.html")
            else:
                return render_error(request, 409, "Username or email already exists")
        else:
            # Should not happen anyway
            return render_error(request, 409, "Passwords do not match")
    return render(request, "user/register.html")


def activate_user_view(request):
    if request.method == "POST":
        try:
            user = User.objects.get(id=request.POST['user-id'])
        except User.DoesNotExist:
            return render_error(request, 404, "User does not exist")
        token = request.POST['token']
        if account_activation_token.check_token(user, token):
            if not User.objects.filter(email=user.new_email).exists():
                if not user.email_confirmed:
                    user.email_confirmed = True
                    user.email = user.new_email
                    user.new_email = ""
                else:
                    user.email = user.new_email
                    user.new_email = ""
                user.save()
                return redirect("login")
            return render_error(request, 409, "E-Mail address already exists")
        else:
            return render_error(request, 498)
    try:
        user = User.objects.get(id=request.GET['user-id'])
    except User.DoesNotExist:
        return render_error(request, 404, "User does not exist")
    return render(request, "user/activate.html", {"content_user": user, "token": request.GET['token']})


def user_passwordreset_view(request):
    if request.method == "POST":
        try:
            user = User.objects.get(id=request.POST['user-id'])
        except User.DoesNotExist:
            return render_error(request, 404, "User does not exist")
        token = request.POST['token']
        if password_reset_token.check_token(user, token):
            if request.POST['password'] == request.POST['confirm_password']:
                user.set_password(request.POST['password'])
                user.save()
                login(request, user)
                return redirect("dashboard")
            return render_error(request, 409, "Passwords do not match")
        else:
            return render_error(request, 498)
    try:
        user = User.objects.get(id=request.GET['user-id'])
    except User.DoesNotExist:
        return render_error(request, 404, "User does not exist")
    return render(request, "user/passwordreset.html",
                  {"content_user": user, "token": request.GET['token']})


def user_passwordreset_request_view(request):
    if request.method == "POST":
        username = request.POST['username']
        try:
            try:
                validate_email(username)
                user = User.objects.get(email=username)
            except ValidationError:
                user = User.objects.get(username=username)
        except User.DoesNotExist:
            return render_error(request, 404, "User does not exist")
        user.send_passwordreset_mail(request)
        return render(request, "user/passwordreset_request.html", {"sent_email": True})
    return render(request, "user/passwordreset_request.html")


@permission_required("ticketcontrol.add_user")
def create_user_view(request):
    if (request.method == 'POST'):
        password = request.POST['password']
        if len(password) < 8:
            return render_error(request, 411, "Password must be at least 8 characters long")
        groups = None
        if request.user.has_perm("ticketcontrol.change_user_permission"):
            groups = request.POST.getlist("groups")
        if not User.objects.filter(email=request.POST['email']).exists() and not User.objects.filter(
                username=request.POST['username']).exists():
            User.add_user(request.POST['email'], request.POST['firstname'], request.POST['lastname'],
                          request.POST['username'], password, groups, request.POST.get("is_active", False) == "on",
                          email_confirmed=True)
            return redirect("manage_users")
        else:
            return render_error(request, 409, "Username or E-Mail already exists")
    return render(request, "user/create.html", {"groups": Group.objects.all(),
                                                "can_change_permission": request.user.has_perm(
                                                    "ticketcontrol.change_user_permission")})


@permission_required("ticketcontrol.view_user")
def manage_users_view(request):
    return render(request, "user/manage.html",
                  {"users": User.objects.all().exclude(username="ghost"), "can_create": request.user.has_perm("ticketcontrol.create_user"),
                   "can_change": request.user.has_perm("ticketcontrol.change_user"),
                   "can_delete": request.user.has_perm("ticketcontrol.delete_user")})


@login_required()
def user_details_view(request, id):
    try:
        user = User.objects.get(id=id)
    except User.DoesNotExist:
        return render_error(request, 404, "User does not exist")
    if request.user.has_perm("ticketcontrol.view_user") or request.user.id == id:
        return render(request, "user/details.html", {"content_user": user,
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
    return JsonResponse(res, safe=False)  # It's ok. Disables typecheck for dict. Make sure to only pass an array


@login_required()
def edit_user_view(request, id):
    if request.user.has_perm("ticketcontrol.change_user") or request.user.id == id:
        if request.method == 'POST':
            password = request.POST['password']
            if password != "" and len(password) < 8:
                return render_error(request, 411, "Password must be at least 8 characters long")
            groups = None
            if request.user.has_perm("ticketcontrol.change_user_permission"):
                groups = request.POST.getlist("groups")
            try:
                user = User.objects.get(id=id)
            except User.DoesNotExist:
                return render_error(request, 404, "User does not exist")
            if user.username == "ghost":
                return render_error(request, 403, "Editing the user ghost is not allowed")
            if user.username == request.POST['username'] or not User.objects.filter(
                    username=request.POST['username']).exists():
                user.update_user(None, request.POST['firstname'], request.POST['lastname'],
                                 request.POST['username'], password, groups,
                                 request.POST.get("is_active", False) == "on")
                if user.email != request.POST['email']:
                    if not User.objects.filter(email=request.POST['email']).exists():
                        if request.user.has_perm("ticketcontrol.change_user"):
                            user.email = request.POST['email']
                            user.save()
                        else:
                            user.update_user(email=request.POST['email'])
                            user.send_emailverification_mail(request)
                            return render(request, "user/activate.html")
                    else:
                        return render_error(request, 409, "E-Mail already exists")
                    return redirect("edit_user", id=id)
            else:
                return render_error(request, 409, "Username already exists")
        try:
            user = User.objects.get(pk=id)
        except User.DoesNotExist:
            return render_error(request, 404, "User does not exist")
        groups = []
        for group in user.groups.all():
            groups.append(group.id)

        if user.username == "ghost":
            return render_error(request, 403, "Editing user ghost is not allowed")
        return render(request, "user/edit.html",
                      {"content_user": user, "userGroups": groups, "groups": Group.objects.all(),
                       "can_change_permission": request.user.has_perm(
                           "ticketcontrol.change_user_permission"),
                       "can_change": True,
                       "can_delete": request.user.has_perm("ticketcontrol.delete_user") or request.user.id == id})
    return redirect("login")


@login_required()
def profile_view(request):
    return edit_user_view(request, request.user.id)


def unrestricted_delete_user_view(request, id):
    if request.method == 'POST':
        try:
            user = User.objects.get(id=id)
        except User.DoesNotExist:
            return render_error(request, 404, "User does not exist")
        if user.username not in ("ghost", "admin"):
            user.delete()
        else:
            return render_error(request, 403, "Deleting user " + user.username + " is not allowed")
        return redirect("manage_users")


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
                  {"groups": Group.objects.all().order_by("id"), "can_create": request.user.has_perm("ticketcontrol.create_user")})


# noinspection PyPep8Naming
@permission_required("auth.create_group")
def create_group_view(request):
    if request.method == 'POST':
        try:
            group = Group.objects.create(name=request.POST['name'])
        except Group.DoesNotExist:
            return render_error(request, 404, "Group does not exist")
        permissions = request.POST.getlist("permissions")
        all_permissions = Permission.objects.all()
        for permission in permissions:
            in_all_permissions = False
            for perm in all_permissions:
                if int(perm.perm.id) == int(permission):
                    in_all_permissions = True
            if in_all_permissions:
                group.permissions.add(permission)
        group.save()
        return redirect("manage_groups")
    return render(request, "user/group/create.html", {"permissions": Permission.objects.all()})


@permission_required("auth.view_group")
def edit_group_view(request, id):
    can_edit = request.user.has_perm("auth.change_group")
    try:
        group = Group.objects.get(id=id)
    except Group.DoesNotExist:
        return render_error(request, 404, "Group does not exist")
    if request.method == 'POST' and can_edit:
        if group.name != "admin" and group.name != "moderator" and group.name != "user":
            group.name = request.POST['name']
        if group.name != "admin":  # admin is superuser anyway
            groupPermissions = group.permissions.all()
            permissions = request.POST.getlist("permissions")
            allPermissions = Permission.objects.all()
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
                    if int(perm.perm.id) == int(permission):
                        inAllPermissions = True
                if not inGroupPermissions and inAllPermissions:
                    group.permissions.add(permission)
            group.save()
            return redirect("manage_groups")
        return render_error(request, 403, "Editing default group \"admin\" is not allowed.")
    groupPermissions = []
    for permissionId in group.permissions.all().values_list("id", flat=True):
        groupPermissions.append(permissionId)
    return render(request, "user/group/edit.html",
                  {"group": group, "group_permissions": groupPermissions, "permissions": Permission.objects.all(),
                   "can_change": can_edit, "can_delete": request.user.has_perm(
                      "ticketcontrol.delete_group") and group.name != "admin" and group.name != "moderator" and group.name != "user"})


@permission_required("auth.delete_group")
def delete_group_view(request, id):
    try:
        group = Group.objects.get(id=id)
    except Group.DoesNotExist:
        return render_error(request, 404, "Group does not exist")
    if group.name == "admin" or group.name == "moderator" or group.name == "user":
        return render_error(request, 403, "Deleting default group \"" + group.name + "\" is not allowed.")
    if request.method == 'POST':
        group.delete()
        return redirect("manage_groups")


@login_required()
def ticket_new_view(request):
    if request.method == 'POST':
        try:
            user = User.objects.get(id=request.user.id)
        except User.DoesNotExist:
            return render_error(request, 404, "User does not exist")
        ticket = Ticket.add_ticket(request.POST["title"], request.POST["description"], user,
                                   Category.objects.get(id=request.POST["category"]), request.POST["location"])
        for attachment_id in request.POST.getlist("attachments"):
            try:
                attachment = Attachment.objects.get(id=attachment_id)
            except Attachment.DoesNotExist:
                return render_error(request, 404, "Attachment does not exist")
            if attachment.user.id == request.user.id:
                ticket.attachment_set.add(attachment)
        ticket.save()
        return redirect('/ticket/my')
    else:
        category = Category.objects.all()
        context = {"category": category}
        return render(request, "ticket/new.html", context)


@login_required()
def ticket_comment_add(request, id):
    if request.method == 'POST':
        try:
            ticket = Ticket.objects.get(id=id)
            user = User.objects.get(id=request.user.id)
        except Ticket.DoesNotExist:
            return render_error(request, 404, "Ticket does not exist")
        except User.DoesNotExist:
            return render_error(request, 404, "User does not exist")
        comment = ticket.add_comment(request.POST["comment"], user)
        for attachment_id in request.POST.getlist("attachments"):
            try:
                attachment = Attachment.objects.get(id=attachment_id)
            except Attachment.DoesNotExist:
                return render_error(request, 404, "Attachment does not exist")
            if attachment.user.id == request.user.id:
                comment.attachment_set.add(attachment)
        comment.save()
        return redirect('/ticket/' + str(id))
    return render_error(request, 405, "This site is only available for POST requests")


@login_required()
def ticket_participant_add(request, id, username=None):
    if request.method == "POST":
        if username == None:
            return render_error(request, 406, "Username is required")
        try:
            ticket = Ticket.objects.get(id=id)
            if request.user.id == ticket.owner.id or request.user.has_perm("ticketcontrol.change_ticket"):
                ticket.participating.add(User.objects.get(username=username))
                return HttpResponse(status=200)
            return render_error(request, 403, "You don't have the permission to add a participant to this ticket")
        except Ticket.DoesNotExist:
            return render_error(request, 404, "Ticket does not exist")
        except User.DoesNotExist:
            return render_error(request, 404, "User does not exist")
        #except DatabaseError:
            #return render_error(request, 409, "Database error") # TODO
    return render_error(request, 405, "This page is only for post requests")


@permission_required("ticketcontrol.change_ticket")
def ticket_moderator_add(request, id, username=None):
    if request.method == "POST":
        if username == None:
            return render_error(request, 406, "Username is required")
        try:
            ticket = Ticket.objects.get(id=id)
            ticket.moderator.add(User.objects.get(username=username))
            if ticket.status == "Unassigned":
                ticket.set_status("Assigned")
                ticket.save()
            return HttpResponse(status=200)
        except Ticket.DoesNotExist:
            return render_error(request, 404, "Ticket does not exist")
        except User.DoesNotExist:
            return render_error(request, 404, "User does not exist")
        #except DatabaseError:
            #return render_error(request, 409, "Database error") # TODO
    return render_error(request, 405, "This page is only for post requests")


def attachment_access_control(request, id, name=None):
    if name is None:
        name = str(id)
    try:
        attachment = Attachment.objects.get(id=id)
    except Attachment.DoesNotExist:
        return render_error(request, 404, "Attachment does not exist")
    authorized = False
    if request.user.id == attachment.user.id:
        authorized = True
    elif attachment.ticket is not None and request.user.id == attachment.ticket.owner.id:
        authorized = True
    elif attachment.comment is not None and request.user.id == attachment.comment.user.id:
        authorized = True
    elif request.user.has_perm("ticketcontrol.view_attachment"):
        authorized = True
    else:
        for participant in attachment.ticket.participating.all():
            if request.user.id == participant.id:
                authorized = True
        if not authorized:
            for moderator in attachment.ticket.moderator.all():
                if request.user.id == moderator.id:
                    authorized = True
    if authorized:
        if not settings.DEBUG:
            response = HttpResponse()
            # Content-type will be detected by nginx
            del response['Content-Type']
            response['X-Accel-Redirect'] = '/serve_attachment/' + str(id)
            response['Content-Disposition'] = 'attachment;filename="' + name + '"'
            return response
        else:
            response = serve(request, str(id), document_root="uploads")
            response['Content-Disposition'] = 'attachment;filename="' + name + '"'
            return response
    else:
        return render_error(request, 403)


def upload_attachment(request):
    if request.method == "POST":
        try:
            file = request.FILES['attachment']
            attachment = Attachment.objects.create(filename=file.name, size=file.size, ticket=None, comment=None,
                                                   user=User.objects.get(id=request.user.id))
            with open("uploads/" + str(attachment.id), "wb+") as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            if request.POST.get("ticket"):
                ticket = Ticket.objects.get(id=request.POST['ticket'])
                if request.user.id == ticket.owner.id or request.user.has_perm("ticketcontrol.add_attachment"):
                    attachment.ticket = ticket
            elif request.POST.get("comment"):
                comment = Comment.objects.get(id=request.POST['comment'])
                if request.user.id == comment.user.id or request.user.has_perm("ticketcontrol.add_attachment"):
                    attachment.comment = comment
            attachment.save()
            return HttpResponse(str(attachment.id))
        except User.DoesNotExist:
            return render_error(request, 404, "User does not exist")
        except Ticket.DoesNotExist:
            return render_error(request, 404, "Ticket does not exist")
        except Comment.DoesNotExist:
            return render_error(request, 404, "Comment does not exist")
        except PermissionError:
            return render_error(request, 403, "Unable to save attachment")
    return render_error(request, 405, "This site is only available for post requests")


def delete_attachment(request, id):
    if request.method == "POST":
        try:
            attachment = Attachment.objects.get(id=id)
        except Attachment.DoesNotExist:
            return render_error(request, 404, "Attachment does not exist")
        authorized = False
        if request.user.id == attachment.user.id or request.user.has_perm("ticketcontrol.delete_attachment"):
            authorized = True
        elif attachment.ticket is not None and request.user.id == attachment.ticket.owner.id:
            authorized = True
        elif attachment.comment is not None and request.user.id == attachment.comment.user.id:
            authorized = True
        if authorized:
            try:
                os.remove("uploads/" + str(id))
            except PermissionError:
                return render_error(request, 403, "Unable to delete attachment")
            except FileNotFoundError:
                return render_error(request, 404, "Unable to delete attachment: File not found")
            attachment.delete()
            return HttpResponse(status=200)
        else:
            return render_error(request, 403, "You aren't allowed to delete this attachment")
    return render_error(request, 405, "This site is only available for post requests")

          
@permission_required("ticketcontrol.change_ticket")
def ticket_status_update(request, id):
    if request.method == "POST":
        try:
            ticket = Ticket.objects.get(id=id)
            ticket.set_status(request.POST['status_choice'])
            return redirect("ticket_view", id=id)
        except Ticket.DoesNotExist:
            return render_error(request, 404, "Ticket does not exist")
        #except DatabaseError:
            #return render_error(request, 409, "Database error") # TODO
    return render_error(request, 400, "This site is only available for post requests")


def settings_view(request):
    if request.user.is_superuser:
        try:
            settings_file = open("settings/settings.json")
            settings_json = json.load(settings_file)
            settings_file.close()
        except FileNotFoundError:
            return render_error(request, 404, "The settings file does not exist")
        except PermissionError:
            return render_error(request, 403, "Unable to open settings file")
        if request.method == "POST":
            general = settings_json['general']
            general['contact_email'] = request.POST['general.contact-email']
            general['allow_location'] = request.POST.get("general.allow-location", False) == "on"
            general['force_location'] = request.POST.get("general.force-location", False) == "on"
            general['meme_mode'] = request.POST.get("general.meme-mode", False) == "on"
            email_server = settings_json['email_server']
            email_server['smtp_host'] = request.POST['email-server.smtp-host']
            email_server['smtp_port'] = int(request.POST['email-server.smtp-port'])
            email_server['smtp_use_tls'] = request.POST.get("email-server.smtp-use-tls", False) == "on"
            email_server['smtp_use_ssl'] = request.POST.get("email-server.smtp-use-ssl", False) == "on"
            email_server['smtp_user'] = request.POST['email-server.smtp-user']
            if request.POST['email-server.smtp-password'] is not None and request.POST['email-server.smtp-password'] != "":
                email_server['smtp_password'] = request.POST['email-server.smtp-password']

            content = settings_json['content']
            content['frontpage'] = request.POST['content.frontpage']
            content['half_page'] = request.POST['content.half-page']
            content['imprint'] = request.POST['content.imprint']

            register = settings_json['register']
            register['allow_custom_nickname'] = request.POST.get("register.allow-custom-nickname", False) == "on"
            register['email_whitelist_enable'] = request.POST.get("register.email-whitelist-enable", False) == "on"
            register['email_whitelist'] = []
            for entry in request.POST.getlist('register.email-whitelist'):
                register['email_whitelist'].append(entry)

            legal = settings_json['legal']
            legal['privacy_and_policy'] = request.POST['legal.privacy-and-policy']

            try:
                settings_file = open("settings/settings.json", "w+")
                json.dump(settings_json, settings_file)
                settings_file.close()
            except PermissionError:
                return render_error(request, 403, "Unable to save settings file")

            if request.POST.get('restart-server', False) == "on":
                os.system("/sbin/reboot")

        return render(request, "settings.html", {"settings": settings_json})
    else:
        return render_error(request, 403, "Only superuser is allowed to change system settings")


@permission_required("ticketcontrol.add_category")
def create_category_view(request):
    if request.method == "POST":
        Category.objects.create(name=request.POST['name'], color=request.POST['color'].strip("#"))
        return redirect("manage_categories")
    else:
        return render(request, "category/create.html")

@permission_required("ticketcontrol.view_category")
def edit_category_view(request, id):
    try:
        category = Category.objects.get(id=id)
    except Category.DoesNotExist:
        return render_error(request, 404, "Category does not exist")
    if request.method == "POST":
        if request.user.has_perm("ticketcontrol.edit_category"):
            category.name = request.POST['name']
            category.color = request.POST['color'].strip("#")
            category.save()
            return redirect("manage_categories")
        else:
            return redirect("login")
    return render(request, "category/edit.html", {"category": category,
                                                  "can_change": request.user.has_perm("ticketcontrol.change_category"),
                                                  "can_delete": request.user.has_perm("ticketcontrol.delete_category")})


@permission_required("ticketcontrol.delete_category")
def delete_category_view(request, id):
    if request.method == "POST":
        try:
            category = Category.objects.get(id=id)
        except Category.DoesNotExist:
            return render_error(request, 404, "Category does not exist")
        category.delete()
        return redirect("manage_categories")
    else:
        return render_error(request, 405, "This site is only available for POST requests")


@permission_required("ticketcontrol.view_category")
def manage_categories_view(request):
    return render(request, "category/manage.html",
                  {"categories": Category.objects.all(), "can_create": request.user.has_perm("ticketcontrol.create_category")})


@permission_required("ticketcontrol.hide_ticket")
def ticket_hide(request, id):
    if request.method == "POST":
        try:
            ticket = Ticket.objects.get(id=id)
            ticket.set_hidden(True)
            return redirect("dashboard")
        except Ticket.DoesNotExist:
            return render_error(request, 404, "Ticket does not exist")
        #except DatabaseError:
            #return render_error(request, 409, "Database error") # TODO
    return render_error(request, 405, "This site is only available for POST requests")


@permission_required("ticketcontrol.unhide_ticket")
def ticket_unhide(request, id):
    if request.method == "POST":
        try:
            ticket = Ticket.objects.get(id=id)
            ticket.set_hidden(False)
            return redirect("ticket_view", id=id)
        except Ticket.DoesNotExist:
            return render_error(request, 404, "Ticket does not exist")
        #except DatabaseError:
            #return render_error(request, 409, "Database error") # TODO
    return render_error(request, 405, "This site is only available for POST requests")


@permission_required("ticketcontrol.delete_ticket")
def ticket_delete(request, id):
    if request.method == "POST":
        try:
            ticket = Ticket.objects.get(id=id)
            ticket.delete()
            return redirect("dashboard")
        except Ticket.DoesNotExist:
            return render_error(request, 404, "Ticket does not exist")
        #except DatabaseError:
            #return render_error(request, 409, "Database error") # TODO
    else:
        return render_error(request, 405, "This site is only available for POST requests")

def ticket_info_update(request, id):
    if request.method == "POST":
        try:
            ticket = Ticket.objects.get(id=id)
            if request.user.id == ticket.owner or request.user.has_perm("ticketcontrol.change_ticket"):
                if request.POST['title'] != "" and not None:
                    ticket.title = request.POST['title']
                if request.POST['location'] != "" and not None:
                    ticket.location = request.POST['location']
                if not request.POST['category'] in (0, "", "0", None):
                    ticket.category = Category.objects.get(id=request.POST['category'])
                ticket.save()
            else:
                return render_error(request, 403, "You aren't allowed to edit tickets or you aren't the owner of the ticket")
            return redirect("ticket_view", id=id)
        except Ticket.DoesNotExist:
            return render_error(request, 404, "Ticket doesn't exist")
        #except DatabaseError:
            #return render_error(request, 409, "Database error") # TODO
    else:
        return render_error(request, 405, "This site is only available for POST requests")


def edit_comment(request, id):
    if request.method == "POST":
        try:
            comment = Comment.objects.get(id=id)
        except Comment.DoesNotExist:
            return render_error(request, 404, "Comment not found")
        if request.user.has_perm("ticketcontrol.change_comment") or request.user.id == comment.user.id:
            comment.content = request.POST['content']
            comment.save()
            return redirect('ticket_view', id=comment.ticket_id)
        else:
            return render_error(request, 403, "You aren't allowed to edit comments or you aren't the owner of this comment")
    else:
        return render_error(request, 405, "This site is only available for POST requests")


def ticket_edit(request, id):
    if request.method == "POST":
        try:
            ticket = Ticket.objects.get(id=id)
        except Ticket.DoesNotExist:
            return render_error(request, 404, "Ticket does not exist")
        if request.user.has_perm("ticketcontrol.change_ticket") or request.user.id == ticket.owner.id:
            ticket.description = request.POST['description']
            ticket.save()
            return redirect('ticket_view', id=id)
        else:
            return render_error(request, 403, "You aren't allowed to edit this ticket")
    else:
        return render_error(request, 405, "This site is only available for POST requests")

