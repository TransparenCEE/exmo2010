# -*- coding: utf-8 -*-
# This file is part of EXMO2010 software.
# Copyright 2010, 2011, 2013 Al Nikolov
# Copyright 2010, 2011 non-profit partnership Institute of Information Freedom Development
# Copyright 2012-2014 Foundation "Institute for Information Freedom Development"
# Copyright 2014-2016 IRSI LTD
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
from collections import OrderedDict, defaultdict

from ckeditor.views import upload
from django import http
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.http import HttpResponseRedirect, Http404, HttpResponseBadRequest, HttpResponseNotAllowed
from django.template import RequestContext, loader
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.utils import dateformat, translation
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt, requires_csrf_token
from django.views.generic import TemplateView, DetailView, FormView, View
from django.views.i18n import set_language
from livesettings import config_value

from ..forms import FeedbackForm, CertificateOrderForm, CertificateOrderQueryForm, TasksIndexQueryForm, ContactsForm
from ..mail import mail_certificate_order, mail_feedback, mail_contacts_frontpage
from ..models import Monitoring, ObserversGroup, StaticPage, Task, FeedbackItem
from ..models.text_fragments import FrontPageTextFragments, LicenseTextFragments
from ..models.monitoring import PRE, RATE, RES, INT, FIN, PUB
from accounts.forms import SettingsInvCodeForm
from core.response import JSONResponse
from core.views import LoginRequiredMixin
from perm_utils import annotate_exmo_perms


def index(request):
    user = request.user
    if user.is_anonymous():
        return index_anonymous(request)

    if (user.is_organization or ObserversGroup.objects.filter(users=user).exists()) and not user.is_expert:
        return index_orgs(request)

    if user.is_expertA:
        return HttpResponseRedirect(reverse('exmo2010:monitorings_list'))

    if user.is_expertB:
        return HttpResponseRedirect(reverse('exmo2010:tasks_index'))

    # Regular unprivileged users will see the same as anonymous.
    return index_anonymous(request)


def index_anonymous(request):
    fragments = {f.id: f for f in FrontPageTextFragments.objects.all()}
    context = {
        'editable': fragments,
        'feedback_items': FeedbackItem.objects.all()[:3],
        'feedback_count': FeedbackItem.objects.count(),
        'tasks': None
    }
    return TemplateResponse(request, 'home/index_anonymous.html', context=context)


def tasks_index(request):
    if not request.user.is_expertB:
        raise PermissionDenied

    queryform = TasksIndexQueryForm(request.user, request.GET)

    Monitoring.objects.filter()
    filter = Q(user=request.user, organization__monitoring__status__in=[RATE, RES, INT, FIN])
    tasks = Task.objects.filter(filter).prefetch_related('organization__monitoring', 'qanswer_set')

    if queryform.is_valid():
        tasks = queryform.apply(tasks)

    monitorings = defaultdict(list)
    tasks = annotate_exmo_perms(tasks, request.user)

    for task in tasks:
        monitorings[task.organization.monitoring].append(task)

    task_order_key = lambda task: task.status + task.completeness / 100
    for monitoring in monitorings:
        monitorings[monitoring].sort(key=task_order_key)

    context = {
        'tasks_exist': Task.objects.filter(filter).exists(),
        'monitorings': sorted(monitorings.items(), key=lambda x: x[0].publish_date),
        'queryform': queryform
    }

    return TemplateResponse(request, 'home/tasks_index.html', context)


def index_orgs(request):
    tasks = Task.approved_tasks.filter(Q(organization__observersgroup__users=request.user) |
                                       Q(organization__userprofile__user=request.user))\
                               .order_by('-organization__monitoring__publish_date')\
                               .distinct()
    int_tasks = tasks.filter(organization__monitoring__status=INT)
    fin_tasks = tasks.filter(organization__monitoring__status=FIN)
    pub_tasks = tasks.filter(organization__monitoring__status=PUB)
    context = {
        'int_tasks': int_tasks,
        'fin_tasks': fin_tasks,
        'pub_tasks': pub_tasks,
    }
    if request.user.is_organization:
        context.update({'invcodeform': SettingsInvCodeForm()})

    return TemplateResponse(request, 'home/index_orguser.html', context)


org_url_re = re.compile(
    u'(http://|https://)?(www\.)?'
    u'(?P<base_url>[a-zA-Zа-яА-Я1-9][a-zA-Zа-яА-Я1-9\-]*\.[a-zA-Zа-яА-Я1-9\-\.]+)(/.*)?$')


def ajax_index_find_score(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(permitted_methods=['GET'])

    if 'org_url' not in request.GET:
        return HttpResponseBadRequest()

    context = {'result': '', 'tasks': None, 'org_url': request.GET['org_url']}

    query = org_url_re.match(request.GET['org_url'])
    if not query:
        context['result'] = 'invalid_url'
    else:
        filter = Q(organization__url__icontains=query.group('base_url'), organization__monitoring__hidden=False)
        tasks = Task.objects.filter(filter).prefetch_related('organization__monitoring')

        if not tasks:
            context['result'] = 'not_found'
        else:
            context['tasks'] = []

            # Try to find matching unfinished monitorings to show info block.
            # We should show only one info block about RATE/RES or INT/FIN monitoring. INT/FIN has
            # precedence (as latest monitoring phase).
            for task in tasks:
                if task.organization.monitoring.status in [RATE, RES] and not context['result']:
                    context['result'] = 'rate'
                elif task.organization.monitoring.status in [INT, FIN]:
                    context['result'] = 'interaction'
                elif task.organization.monitoring.status == PUB and task.status == Task.TASK_APPROVED:
                    # Approved tasks from published monitorings should be displayed in table.
                    context['tasks'].append(task)

    return TemplateResponse(request, 'home/_search_results.html', context)


def ajax_submit_contacts_form(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(permitted_methods=['POST'])

    form = ContactsForm(request.POST)
    if form.is_valid():
        mail_contacts_frontpage(form.cleaned_data)
    else:
        return HttpResponseBadRequest()

    return JSONResponse({'ok': True})


def feedback(request):
    context = {
        'feedback_items': FeedbackItem.objects.all(),
    }
    return TemplateResponse(request, 'feedback.html', context=context)


def feedback_form(request):
    success = False

    if request.user.is_active:
        form = FeedbackForm(initial={'email': request.user.email})
    else:
        form = FeedbackForm()
    if request.method == "POST":
        form = FeedbackForm(request.POST)
        if form.is_valid():
            mail_feedback(request, form.cleaned_data['email'], form.cleaned_data['comment'])
            success = True

    context = {
        'title': _('Feedback'),
        'form': form,
        'success': success,
    }
    return TemplateResponse(request, 'feedback_form.html', context)


class StaticPageView(DetailView):
    template_name = 'exmo2010/static_page.html'

    def get_object(self, queryset=None):
        """ Create static page if it does not exist yet. Fill in default content_en if empty. """
        page, created = StaticPage.objects.get_or_create(pk=self.static_page_pk)
        if not page.content_en:
            with translation.override('en'):
                page.content_en = render_to_string(self.default_content, self.get_default_context())
            page.save()
        return page

    def get_default_context(self):
        """ Override this method to pass custom context when default content is rendered. """
        return {}


class HelpView(StaticPageView):
    static_page_pk = 'help'
    default_content = 'exmo2010/static_pages/help.html'

    def get_default_context(self):
        return {
            'support_email': config_value('EmailServer', 'DEFAULT_SUPPORT_EMAIL'),
            'registration_url': self.request.build_absolute_uri(reverse('exmo2010:registration_form'))
        }


class AboutView(StaticPageView):
    static_page_pk = 'about'
    default_content = 'exmo2010/static_pages/about.html'


class OpenDataView(TemplateView):
    template_name = 'exmo2010/opendata.html'

    def get_context_data(self, **kwargs):
        context = super(OpenDataView, self).get_context_data(**kwargs)
        license = LicenseTextFragments.objects.filter(pk='license')
        json_license = license[0].json_license if license else {}
        context['json_license'] = json_license
        return context


class CertificateOrderView(FormView):
    template_name = "certificate_order_form.html"
    form_class = CertificateOrderForm

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_organization:
            raise PermissionDenied
        return super(CertificateOrderView, self).dispatch(request, *args, **kwargs)

    def get_form(self, form_class):
        form = super(CertificateOrderView, self).get_form(form_class)
        self.rating_type = form['rating_type'].value()

        orgs = self.request.user.profile.organization.filter(monitoring__status=PUB)
        _tasks = Task.objects.filter(organization__in=orgs, status=Task.TASK_APPROVED)
        if not _tasks.exists():
            # User don't have published and approved tasks, certificate order is unavailable
            self.template_name = "certificate_order_unavailable.html"
            return None

        # Check if rating_type filter should be displayed
        pks = Monitoring.objects.filter(organization__in=orgs).values_list('pk', flat=True)
        if set(pks.filter(parameter__npa=True).distinct()) & set(pks.filter(parameter__npa=False).distinct()):
            # There is Monitoring with both npa and non-npa parameters
            self.vary_rating_type = True
        else:
            self.vary_rating_type = False

        # Apply user provided filters
        self.queryform = CertificateOrderQueryForm(self.request.GET)

        if self.queryform.is_valid():
            orgs = self.queryform.apply(orgs)

        _org_pks = set(orgs.values_list('pk', flat=True))
        _filter = {'organization__in': _org_pks}

        if self.rating_type in ['npa', 'other']:
            # NOTE: This logic works only because currently there are only 3 types of monitoring:
            # 1) Monitoring with both npa and non-npa parameters.
            # 2) Monitoring with only npa parameters.
            # 3) Monitoring with only non-npa parameters in DB, but really it does not differentiate parameters
            #    and should only be visible when "all" rating type chosen.
            # Therefore if "non-npa" ("other") rating chosen - we can first select all monitorings that have npa parameter.
            # Then caluclate "non-npa" rating. Resulting rated tasks list will be empty if there are only npa
            # parameters in monitoring (see Monitoring.rating). As a result only organizations from
            # monitorings with both npa and non-npa parameters (case 1) will be displayed
            #
            # This logic will break when real monitoring with all-non-npa parameters will be introduced.
            # It should be visible when "non-npa" rating is chosen, but filter below will exclude it :(
            _filter['parameter__npa'] = True

        # Build rated tasks ordered dict to display
        self.tasks = OrderedDict()
        for monitoring in Monitoring.objects.filter(**_filter).select_related('openness_expression')\
                                            .distinct().order_by('-publish_date'):
            for t in monitoring.rating(rating_type=self.rating_type):
                if t.organization.pk in _org_pks:
                    self.tasks[t.pk] = t

        return form

    def form_valid(self, form):
        if 'back' in self.request.POST:
            return self.render_to_response(self.get_context_data(form=form))

        email_data = self.prerender_email_text(form.cleaned_data)

        if 'confirm' in self.request.POST:
            mail_certificate_order(self.request, email_data)
            msg = _("You ordered an openness certificate. Certificate will be prepared and sent within 5 working days.")
            messages.success(self.request, msg)
            return HttpResponseRedirect(reverse('exmo2010:index'))
        else:
            return self.render_to_response(self.get_context_data(form=form, form_hidden='hidden', **email_data))

    def get_context_data(self, **kwargs):
        kwargs.setdefault('form_hidden', '')
        return super(CertificateOrderView, self).get_context_data(**kwargs)

    def get_initial(self):
        return {
            'name': self.request.user.profile.legal_name,
            'email': self.request.user.email,
            'rating_type': self.request.REQUEST.get('rating_type', 'all'),
        }

    def prerender_email_text(self, form_data):
        rating_type_text = {'all': _('by all'), 'npa': _('by normative'), 'other': _('by recommendatory')}
        task = self.tasks[form_data['task_id']]

        #xgettext:no-python-format
        description = _('For {task.organization.name} organization, which took '
                        '{task.place} place with {task.task_openness:.3f}% openness'
                        ' in rating {rating_type} parameters, which published {date}.').format(
            task=task,
            rating_type=rating_type_text[form_data['rating_type']],
            date=dateformat.format(task.organization.monitoring.publish_date, "j E Y"))

        #if form_data['delivery_method'] == "post":
            #on_address = _('On address {zip_code}, {address}, {addressee}.').format(**form_data)
        #else:
        on_address = _('On email address %s.') % form_data['email']

        email_data = {
            'organization': task.organization,
            'description': description,
            'on_address': on_address,
            'special_wishes': form_data['wishes'],
            'prepare_for': None
        }

        if form_data['addressee'] == "user":
            prepare_for = _('Prepare a certificate in the name of %s.') % form_data['name']
            email_data.update({'prepare_for': prepare_for})

        return email_data


def public_stats(request, report_type='inprogress', monitoring_pk=None):
    """
    Статистика по мониторингам.

    """
    if report_type not in ['inprogress', 'finished']:
        raise Http404

    all_monitorings = None
    paginator_list = None
    title = _('Monitoring statistics')

    if report_type == 'inprogress':
        all_monitorings = Monitoring.objects.exclude(status=PUB).exclude(hidden=True).order_by('-rate_date')
    elif report_type == 'finished':
        all_monitorings = Monitoring.objects.filter(status=PUB).exclude(hidden=True).order_by('-publish_date')

    if monitoring_pk:
        monitorings = Monitoring.objects.filter(status=PUB, pk=monitoring_pk, hidden=False)
    else:
        monitorings = all_monitorings

        paginator = Paginator(monitorings, 10)
        try:
            page = int(request.GET.get('page', '1'))
            if page < 1:
                page = 1
        except ValueError:
            page = 1

        try:
            paginator_list = paginator.page(page)
        except (EmptyPage, InvalidPage):
            paginator_list = paginator.page(1)

        monitorings = paginator_list.object_list

    return TemplateResponse(request, 'public_stats.html', {
        'paginator': paginator_list,
        'monitorings': monitorings,
        'report_type': report_type,
        'title': title,
        'monitoring_id': monitoring_pk,
        'all_monitorings': all_monitorings,
    })


class AjaxSetProfileSettingView(LoginRequiredMixin, View):
    def post(self, request):
        if request.is_ajax() and request.user.is_active:
            user = request.user
            for setting, value in request.POST.items():
                if hasattr(user.profile, setting):
                    value = int(value) if value.isdigit() else value
                    setattr(user.profile, setting, value)
            user.profile.save()

            return JSONResponse()

        raise Http404


@login_required
@csrf_exempt
def ckeditor_upload(request):
    if not (request.user.is_expert or request.user.is_translator):
        raise PermissionDenied
    return upload(request)


def change_language(request):
    """
    Change user profile language.

    """
    response = set_language(request)
    user = request.user
    if user.is_authenticated() and request.method == 'POST':
        language_code = request.POST.get('language', None)
        user.profile.language = language_code
        user.profile.save()

    return response


@requires_csrf_token
def server_error(request, template_name='500.html'):
    """
    Custom 500 error handler. Puts request in context.

    """
    t = loader.get_template(template_name)
    return http.HttpResponseServerError(t.render(RequestContext(request)))
