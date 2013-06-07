# -*- coding: utf-8 -*-
# This file is part of EXMO2010 software.
# Copyright 2010, 2011, 2013 Al Nikolov
# Copyright 2010, 2011 non-profit partnership Institute of Information Freedom Development
# Copyright 2012, 2013 Foundation "Institute for Information Freedom Development"
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
import re

from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import render_to_response, redirect
from django.template import RequestContext, Context, Template
from django.utils.http import base36_to_int, is_safe_url
from django.core.urlresolvers import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.conf import settings
from django.forms.fields import Field
from django.views.csrf import CSRF_FAILURE_TEMPLATE
from django.middleware.csrf import REASON_NO_CSRF_COOKIE
from django.middleware.csrf import REASON_NO_REFERER
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.models import User
from django.contrib.auth import login, REDIRECT_FIELD_NAME
from django.contrib.auth.views import login as auth_login
from django.contrib.auth.views import password_reset as auth_password_reset
from django.contrib.auth.views import password_reset_done as auth_password_reset_done
from django.contrib.sites.models import RequestSite
from django.contrib.sites.models import Site
from django.utils.translation import ugettext as _
from registration.backends import get_backend

from auth.forms import CustomPasswordResetForm
from bread_crumbs.views import breadcrumbs
from exmo2010.custom_registration.forms import ExmoAuthenticationForm, RegistrationFormFull, RegistrationFormShort
from exmo2010.custom_registration.forms import ResendEmailForm, SetPasswordForm
from exmo2010.custom_registration.models import CustomRegistrationProfile


@csrf_protect
def password_reset_redirect(request, **kwargs):
    if request.user.is_authenticated():
        return redirect('exmo2010:index')
    kwargs['extra_context'] = {'current_title': _('Password reset (step %d from 3)') % 1}
    kwargs['password_reset_form'] = CustomPasswordResetForm
    crumbs = ['Home']
    breadcrumbs(request, crumbs)
    return auth_password_reset(request, **kwargs)


def password_reset_done(request, **kwargs):
    kwargs['extra_context'] = {'current_title': _('Password reset (step %d from 3)') % 2}
    crumbs = ['Home']
    breadcrumbs(request, crumbs)
    return auth_password_reset_done(request, **kwargs)


@never_cache
def password_reset_confirm(request, uidb36=None, token=None,
                   template_name='registration/password_reset_confirm.html',
                   token_generator=default_token_generator,
                   current_app=None, extra_context=None):
    """
    Переприсанная стандартная вьюха для смены пароля.
    Изменение - немедленный логин после установки нового пароля.
    """
    assert uidb36 is not None and token is not None # checked by URLconf
    post_reset_redirect = reverse('exmo2010:index')
    try:
        uid_int = base36_to_int(uidb36)
        user = User.objects.get(id=uid_int)
    except (ValueError, User.DoesNotExist):
        user = None

    if user is not None and token_generator.check_token(user, token):
        validlink = True
        if request.method == 'POST':
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                user.backend='django.contrib.auth.backends.ModelBackend'
                login(request, user)
                return HttpResponseRedirect(post_reset_redirect)
        else:
            form = SetPasswordForm(None)
    else:
        validlink = False
        form = None
    title = _('Password reset (step %d from 3)') % 3
    context = {
        'form': form,
        'validlink': validlink,
        'current_title': title,
        }
    context.update(extra_context or {})

    crumbs = ['Home']
    breadcrumbs(request, crumbs)

    return render_to_response(template_name, context,
        context_instance=RequestContext(request, current_app=current_app))


def register_test_cookie(request, backend, success_url=None, form_class=None,
                         disallowed_url='registration_disallowed',
                         template_name='registration/registration_form.html',
                         extra_context=None):
    """
    Регистрация пользователя.
    Создано основе стандартного представления register из django-registration
    путем добавления в начале проверки включенности cookies в браузере,
    и фокусов с формой в зависимости от статуса регистрирующегося.
    """
    if request.method == 'POST':
        if request.session.test_cookie_worked():
            request.session.delete_test_cookie()
        else:
            return render_to_response('cookies.html', RequestContext(request))

    request.session.set_test_cookie()
    backend = get_backend(backend)
    if not backend.registration_allowed(request):
        return redirect(disallowed_url)

    if request.method == 'POST':
        status = int(request.POST.get("status", u"0"))
        if status == 1:  # интересующийся гражданин.
            form = RegistrationFormShort(data=request.POST,
                files=request.FILES)
        else:  # представитель организации.
            form = RegistrationFormFull(data=request.POST, files=request.FILES)

        if form.is_valid():
            new_user = backend.register(request, **form.cleaned_data)
            if success_url is None:
                to, args, kwargs = backend.post_registration_redirect(request,
                    new_user)
                return redirect(to, *args, **kwargs)
            else:
                return redirect(success_url)
        else:
            if status == 1:
                form = RegistrationFormFull(data=request.POST,
                                            files=request.FILES)
    else:
        form = RegistrationFormFull()

    if extra_context is None:
        extra_context = {}

    extra_context.update({'required_error':
                              Field.default_error_messages['required']})

    context = RequestContext(request)
    for key, value in extra_context.items():
        context[key] = callable(value) and value() or value

    crumbs = ['Home']
    breadcrumbs(request, crumbs)
    title = _('Registration (step %(step)s from %(steps)s)') % {'step': 1, 'steps': 2}

    return render_to_response(template_name,
        {'form': form, 'current_title': title},
        context_instance=context)


@csrf_protect
@never_cache
def login_test_cookie(request, template_name='registration/login.html',
          redirect_field_name=REDIRECT_FIELD_NAME,
          authentication_form=ExmoAuthenticationForm,
          current_app=None, extra_context=None):
    """
    Проверяет работу cookie и возвращает стандартную вью для логина.
    Написан на основе оргинального auth_login.
    """

    # Перенаправление на главную залогиненных пользователей.
    if request.user.is_authenticated():
        return redirect('exmo2010:index')

    redirect_to = request.REQUEST.get(redirect_field_name, '')

    context = {}

    if request.method == "POST":

        if request.user.is_authenticated():
            return redirect('exmo2010:index')

        if not request.session.test_cookie_worked():
            return render_to_response('cookies.html', RequestContext(request))

        form = authentication_form(data=request.POST)
        if form.is_valid():
            # Ensure the user-originating redirection url is safe.
            if not is_safe_url(url=redirect_to, host=request.get_host()):
                redirect_to = settings.LOGIN_REDIRECT_URL

            user = form.get_user()

            # Неактивные пользователи, присутствующие
            # в модели RegistrationProfile, не подтвердили
            # по почте свою регистрацию.
            if not user.is_active:
                if CustomRegistrationProfile.objects.filter(user=user).exists():
                    context.update({'resend_email': True})
            else:
                # Okay, security check complete. Log the user in.
                auth_login(request, user)

                if request.session.test_cookie_worked():
                    request.session.delete_test_cookie()

                return HttpResponseRedirect(redirect_to)
    else:
        form = authentication_form(request)

    request.session.set_test_cookie()

    if Site._meta.installed:
        current_site = Site.objects.get_current()
    else:
        current_site = RequestSite(request)

    title = _('Login')
    context.update({
        'form': form,
        redirect_field_name: redirect_to,
        'site': current_site,
        'site_name': current_site.name,
        'current_title': title,
        })
    context.update(extra_context or {})

    context.update({'required_error': Field.default_error_messages['required']})

    crumbs = ['Home']
    breadcrumbs(request, crumbs)

    return render_to_response(template_name, context,
                              context_instance=RequestContext(
                                  request, current_app=current_app))


def resend_email(request):
    # Перенаправление на главную залогиненных пользователей.
    if request.user.is_authenticated():
        return redirect('exmo2010:index')

    form = ResendEmailForm()
    if request.method == "POST":
        form = ResendEmailForm(request.POST)
        if form.is_valid():
            user = form.get_user
            registration_profile = CustomRegistrationProfile.objects.get(
                user=user)
            if Site._meta.installed:
                site = Site.objects.get_current()
            else:
                site = RequestSite(request)
            registration_profile.send_activation_email(site)
            return HttpResponseRedirect(
                reverse('exmo2010:registration_complete'))
    context = {'form': form}
    return render_to_response('registration/resend_email_form.html',
                              context,
                              context_instance=RequestContext(request))


def csrf_failure(request, reason=""):
    """
    Вызывается при непрохождении джанговских тестов.
    Cross Site Request Forgery protection. Переписана для того,
    чтобы объясняла пользователю о выключенных cookies в браузере.
    """
    if reason == REASON_NO_CSRF_COOKIE:
        return render_to_response('cookies.html', RequestContext(request))
    else:
        t = Template(CSRF_FAILURE_TEMPLATE)
        c = Context({'DEBUG': settings.DEBUG,
                     'reason': reason,
                     'no_referer': reason == REASON_NO_REFERER
                     })
        return HttpResponseForbidden(t.render(c), mimetype='text/html')


def activate_redirect(request, backend,
             template_name='registration/activate.html',
             success_url=None, extra_context=None, **kwargs):
    """
    Вью на основании registration, добавлен редирект на страницу
    логина, если backend.activate() возвращает False
    """

    # Проверка наличия ключа активации и является ли он 160-битным значением
    # в шестнадцатеричной форме записи
    activation_key = kwargs.get('activation_key')
    hex_pattern = re.compile(r'^[0-9a-f]{40}$')
    is_hex = re.search(hex_pattern, activation_key)
    if activation_key and is_hex:
        backend = get_backend(backend)
        account = backend.activate(request, **kwargs)

        if account:
            # успех
            if success_url is None:
                to, args, kwargs = backend.post_activation_redirect(request,
                                                                    account)
                return redirect(to, *args, **kwargs)
            else:
                return redirect(success_url)

        # если ключ правильный, но пользователь уже активирован
        return redirect('exmo2010:auth_login')

    # если ключ активации неправильный
    if extra_context is None:
        extra_context = {}
    context = RequestContext(request)
    for key, value in extra_context.items():
        context[key] = callable(value) and value() or value

    return render_to_response(template_name,
        kwargs,
        context_instance=context)