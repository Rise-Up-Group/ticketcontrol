from django.db import models

from django.contrib.auth.models import Group
from django.contrib.auth.models import User as BaseUser
from django.contrib.auth.models import Permission as BasePermission
import datetime
from django.utils import timezone


class User(BaseUser):
    class Meta:
        permissions = (
            ("change_user_permission", "Change the permissions of other users"),
        )

    def add_user(email, firstname, lastname, username, password, groups, isActive):
        # TODO: preview in javascrip and show to user
        # TODO: nickname has to be unique (possibly with db)
        if username == "":
            username = firstname[0:1] + ". " + lastname
        # Creates ticketcontrol.user; never create a BaseUser
        user = User.objects.create_user(username=username, password=password, email=email)
        user.first_name = firstname
        user.last_name = lastname
        if groups is not None:
            for group in groups:
                Group.objects.get(id=group).user_set.add(user)
            user.is_superuser = False
            user.is_staff = False
            adminId = Group.objects.get(name="Admin").id
            for groupId in groups:
                if int(groupId) == adminId:
                    user.is_superuser = True
                    user.is_staff = True
        else:
            Group.objects.get(name="user").user_set.add(user)
        user.is_active = isActive
        user.save()
        return user

    def update_user(id, email, firstname, lastname, username, password, groups, isActive):
        user = User.objects.get(id=id)
        if user is not None:
            user.email = email
            user.first_name = firstname
            user.last_name = lastname
            user.username = username
            if password != "" and password is not None:
                user.set_password(password)

            if groups is not None:
                userGroups = user.groups.all()
                for group in userGroups:
                    if not group.id in groups:
                        Group.objects.get(id=group.id).user_set.remove(user)
                for group in groups:
                    found = False
                    for userGroup in userGroups:
                        if userGroup.id == group:
                            found = True
                    if not found:
                        Group.objects.get(id=group).user_set.add(user)

                user.is_superuser = False
                user.is_staff = False
                adminId = Group.objects.get(name="admin").id
                for groupId in groups:
                    if int(groupId) == adminId:
                        user.is_superuser = True
                        user.is_staff = True

            if isActive is not None:
                user.is_active = isActive
            user.save()
            return user
        return None

    def delete_user(id):
        User.objects.get(id=id).delete()


class Permission(BasePermission):
    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=256)
    color = models.CharField(max_length=8)

    def __str__(self):
        return self.name


class Comment(models.Model):
    content = models.TextField()
    creationDate = models.DateTimeField(auto_now_add=True)
    num = models.IntegerField()
    ticket = models.ForeignKey("Ticket", on_delete=models.DO_NOTHING)
    user = models.ForeignKey("User", on_delete=models.DO_NOTHING)

    def __str__(self):
        return self.ticket.title + " Comment " + self.num


class Ticket(models.Model):
    class StatusChoices(models.TextChoices):
        UNASSIGNED = 'Unassigned'
        ASSIGNED = 'Assigned'
        CLOSED = 'Closed'
        OPEN = 'Open'
        WAITING = 'Waiting'

    status = models.CharField(max_length=15, choices=StatusChoices.choices, default=StatusChoices.UNASSIGNED)
    creationDate = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    owner = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name="owner")
    category = models.ForeignKey(Category, on_delete=models.DO_NOTHING)
    participating = models.ManyToManyField("User", blank=True)  # does NOT contain owner
    moderator = models.ManyToManyField("User", related_name="moderator", blank=True)  # TODO: 'moderatorS'

    def __str__(self):
        return self.title + " (" + self.owner.username + ")"


class Attachment(models.Model):
    filename = models.CharField(max_length=255)
    size = models.IntegerField()
    creationDate = models.DateTimeField(auto_now_add=True)
    ticket = models.ForeignKey(Ticket, on_delete=models.DO_NOTHING, null=True, blank=True)
    comment = models.ForeignKey(Comment, on_delete=models.DO_NOTHING, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=False, blank=False)

    def __str__(self):
        return self.ticket.title + " File: " + self.filename + "(" + self.size + ")"
