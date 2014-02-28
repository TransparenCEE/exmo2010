# -*- coding: utf-8 -*-
# This file is part of EXMO2010 software.
# Copyright 2010, 2011, 2013 Al Nikolov
# Copyright 2010, 2011 non-profit partnership Institute of Information Freedom Development
# Copyright 2012-2014 Foundation "Institute for Information Freedom Development"
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import string
import time

from django import forms
from django.core.validators import BaseValidator
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ObjectDoesNotExist
from annoying.decorators import autostrip

from exmo2010.custom_registration.models import CustomRegistrationProfile
from exmo2010.models import Organization


PASSWORD_ALLOWED_CHARS = string.ascii_letters + string.digits

STATUS_CHOICES = (
    (0, _('representative')),
    (1, _('private person')),
)


@autostrip
class RegistrationFormShort(forms.Form):
    """Укороченная форма регистрации.
    Используется, если выбран статус "интересующийся гражданин".
    На имя и отчество выделено по 15 символов, чтобы они вместе вместились
    в поле first_name модели User.
    """
    status = forms.ChoiceField(label=_("Status"), choices=STATUS_CHOICES)
    first_name = forms.CharField(label=_("First name"), required=False,
                                 widget=forms.TextInput(attrs={"maxlength": 14}))
    patronymic = forms.CharField(label=_("Patronymic"), required=False,
                                 widget=forms.TextInput(attrs={"maxlength": 14}))
    last_name = forms.CharField(label=_("Last name"), required=False,
                                widget=forms.TextInput(attrs={"maxlength": 30}))
    email = forms.EmailField(label=_("E-mail"),
                             widget=forms.TextInput({"maxlength": 75}))
    password = forms.CharField(label=_("Password"),
                               widget=forms.TextInput(attrs={"maxlength": 24, "autocomplete": "off"}))
    subscribe = forms.BooleanField(label=_("Subscribe to news"), required=False)

    def __init__(self, *args, **kwargs):
        super(RegistrationFormShort, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            if field.required:
                field.error_messages.update({
                    'required': _('{fieldname} is required field.').format(fieldname=field.label)
                })

    def clean_password(self):
        """Проверка пароля на наличие недопустимых символов."""
        password = self.cleaned_data.get('password')
        for char in password:
            if char not in PASSWORD_ALLOWED_CHARS:
                raise forms.ValidationError(_("Password contains unallowed characters. "
                                              "Please use only latin letters and digits."))
        return password

    def clean_email(self):
        """
        Validate that the supplied email address is unique for the site.

        """
        email = self.cleaned_data['email']
        if User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).exists():
            raise forms.ValidationError(_("This email address is already in use. "
                                          "Please supply a different email address."))
        return email


class InvCodeMinLengthValidator(BaseValidator):
    compare = lambda self, a, b: a < b
    clean   = lambda self, x: len(x)
    message = _(u'Ensure invitation code has at least %(limit_value)d characters (it has %(show_value)d).')
    code = 'min_length'


class InvCodeMaxLengthValidator(BaseValidator):
    compare = lambda self, a, b: a > b
    clean   = lambda self, x: len(x)
    message = _(u'Ensure invitation code has at most %(limit_value)d characters (it has %(show_value)d).')
    code = 'max_length'


@autostrip
class RegistrationFormFull(RegistrationFormShort):
    """Полная форма регистрации.
    Используется, если выбран статус "представитель организации".
    На имя и отчество выделено по 15 символов, чтобы они вместе вместились
    в поле first_name модели User.
    """
    position = forms.CharField(label=_("Job title"), required=False,
                               widget=forms.TextInput(attrs={"maxlength": 48}))
    phone = forms.CharField(label=_("Phone number"), required=False,
                            widget=forms.TextInput(attrs={"maxlength": 30}))
    invitation_code = forms.CharField(label=_("Invitation code"),
                                      widget=forms.TextInput(attrs={"maxlength": 6}),
                                      validators=[InvCodeMinLengthValidator(6), InvCodeMaxLengthValidator(6)])

    def clean_invitation_code(self):
        """
        Проверить, что код приглашения существует.
        """
        invitation_code = self.cleaned_data.get('invitation_code')
        if not Organization.objects.filter(inv_code=invitation_code).exists():
            time.sleep(3)  # Чтобы усложнить перебор.
            raise forms.ValidationError(_("Submitted invitation code does not exist. Please enter correct one."))
        else:
            return invitation_code

    def __init__(self, *args, **kwargs):
        super(RegistrationFormFull, self).__init__(*args, **kwargs)
        # Правильно упорядочиваем поля.
        self.fields.keyOrder = ['status', 'first_name', 'patronymic',
                                'last_name', 'position', 'phone', 'email',
                                'password', 'invitation_code', 'subscribe']


@autostrip
class SetPasswordForm(forms.Form):
    """
    A form that lets a user change set his/her password without
    entering the old password
    """
    new_password = forms.CharField(label=_("New password"),
        widget=forms.TextInput)

    def clean_new_password(self):
        """Проверка пароля на наличие недопустимых символов."""
        password = self.cleaned_data.get('new_password')
        for char in password:
            if char not in PASSWORD_ALLOWED_CHARS:
                raise forms.ValidationError(_("Password contains unallowed "
                                              "characters. Please use only "
                                              "latin letters and digits."))
        return password

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super(SetPasswordForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        self.user.set_password(self.cleaned_data['new_password'])
        if commit:
            self.user.save()
        return self.user


class ExmoAuthenticationForm(AuthenticationForm):
    """
    В стандартную форму аутентикации добавлена проверка
    для тех неактивных пользователей, которые
    не подтвердили письмо активации.
    """
    username = forms.CharField(label=_("E-mail"), max_length=30)

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            self.user_cache = authenticate(username=username, password=password)
            if self.user_cache is None:
                raise forms.ValidationError(_("Please enter a correct username and password. Note that both fields are case-sensitive."))
            elif not self.user_cache.is_active:
                # Прошедшие активацию пользователи отсутствуют
                # в модели RegistrationProfile
                if not CustomRegistrationProfile.objects.filter(
                        user=self.user_cache).exists():
                    raise forms.ValidationError(_("This account is inactive."))
        self.check_for_test_cookie()
        return self.cleaned_data


class ResendEmailForm(forms.Form):
    """
    Форма для повторной отправки письма активации
    """
    email = forms.EmailField(label=_("E-mail"))

    def clean_email(self):
        """
        Проверяет присутствие пользователя в базе с этой почтой
        """
        data = self.cleaned_data['email']
        if data:
            try:
                user = User.objects.get(email=data)
            except ObjectDoesNotExist:
                raise forms.ValidationError(
                    _("There's no user with that e-mail.")
                )
            else:
                self.user = user
                if user.is_active:
                    raise forms.ValidationError(
                        _("Account is activated already.")
                    )
                elif not CustomRegistrationProfile.objects.filter(
                        user=user).exists():
                    raise forms.ValidationError(_("This account is inactive."))
                return self.cleaned_data
        return data

    def get_user(self):
        return self.user
