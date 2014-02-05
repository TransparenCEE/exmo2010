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
import csv
import re
import string

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.urlresolvers import reverse
from django.forms.models import modelform_factory
from django.forms.widgets import HiddenInput
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, QueryDict
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils.translation import ugettext as _
from django.views.generic import View
from django.views.generic.edit import DeleteView, UpdateView

import reversion

from accounts.forms import SettingsInvCodeForm
from core.helpers import table
from core.response import JSONResponse
from core.views import LoginRequiredMixin
from core.utils import UnicodeReader, UnicodeWriter
from exmo2010.models import Monitoring, Organization, Parameter, Score, Task, TaskHistory, UserProfile
from perm_utils import annotate_exmo_perms


def task_export(request, task_pk):
    task = get_object_or_404(Task, pk=task_pk)
    if not request.user.has_perm('exmo2010.view_task', task):
        return HttpResponseForbidden(_('Forbidden'))
    parameters = Parameter.objects.filter(monitoring=task.organization.monitoring).exclude(exclude=task.organization)
    scores = Score.objects.filter(task=task_pk, revision=Score.REVISION_DEFAULT)
    response = HttpResponse(mimetype='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename=task-%s.csv' % task_pk
    response.encoding = 'UTF-16'
    writer = UnicodeWriter(response)
    writer.writerow([
        '#Code',
        'Name',
        'Found',
        'Complete',
        'CompleteComment',
        'Topical',
        'TopicalComment',
        'Accessible',
        'AccessibleComment',
        'Hypertext',
        'HypertextComment',
        'Document',
        'DocumentComment',
        'Image',
        'ImageComment',
        'Comment'
    ])
    category = None
    subcategory = None
    for p in parameters:
        out = (
            p.code,
            p.name,
        )
        try:
            s = scores.get(parameter=p)
        except:
            out += (
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                ''
            )
        else:
            out += (s.found,)
            if p.complete:
                out += (
                    s.complete,
                    s.completeComment
                )
            else:
                out += ('', '')
            if p.topical:
                out += (
                    s.topical,
                    s.topicalComment
                )
            else:
                out += ('', '')
            if p.accessible:
                out += (
                    s.accessible,
                    s.accessibleComment
                )
            else:
                out += ('', '')
            if p.hypertext:
                out += (
                    s.hypertext,
                    s.hypertextComment
                )
            else:
                out += ('', '')
            if p.document:
                out += (
                    s.document,
                    s.documentComment
                )
            else:
                out += ('', '')
            if p.image:
                out += (
                    s.image,
                    s.imageComment
                )
            else:
                out += ('','')
            out += (s.comment,)
        writer.writerow(out)
    return response


@reversion.create_revision()
@login_required
def task_import(request, task_pk):
    task = get_object_or_404(Task, pk=task_pk)
    if not request.user.has_perm('exmo2010.fill_task', task):
        return HttpResponseForbidden(_('Forbidden'))
    if not request.FILES.has_key('taskfile'):
        return HttpResponseRedirect(reverse('exmo2010:score_list_by_task', args=[task_pk]))
    reader = UnicodeReader(request.FILES['taskfile'])
    errLog = []
    rowOKCount = 0
    rowALLCount = 0
    try:
        for row in reader:
            rowALLCount += 1
            if row[0].startswith('#'):
                errLog.append(_("row %d. Starts with '#'. Skipped") % reader.line_num)
                continue
            try:
                code = re.match('^(\d+)$', row[0])
                if not code:
                    errLog.append(_("row %(row)d (csv). Not a code: %(raw)s") % {'row': reader.line_num, 'raw': row[0]})
                    continue
                if not any(row[2:16]):
                    errLog.append(_("row %(row)d (csv). Empty score: %(raw)s") % {'row': reader.line_num, 'raw': row[0]})
                    continue
                parameter = Parameter.objects.get(code=code.group(1), monitoring=task.organization.monitoring)
                try:
                    score = Score.objects.get(task=task, parameter=parameter)
                except Score.DoesNotExist:
                    score = Score()
                score.task = task
                score.parameter = parameter
                for i, key in enumerate(['found', 'complete', 'completeComment', 'topical', 'topicalComment',
                                         'accessible', 'accessibleComment', 'hypertext', 'hypertextComment',
                                         'document', 'documentComment', 'image', 'imageComment', 'comment']):
                    value = row[i+2]
                    setattr(score, key, value if value else None)
                score.full_clean()
                score.save()
            except ValidationError, e:
                errLog.append(_("row %(row)d (validation). %(raw)s") % {
                    'row': reader.line_num,
                    'raw': '; '.join(['%s: %s' % (i[0], ', '.join(i[1])) for i in e.message_dict.items()])})
            except Parameter.DoesNotExist:
                errLog.append(_("row %(row)d. %(raw)s") % {
                    'row': reader.line_num,
                    'raw': _('Parameter matching query does not exist')})
            except Exception, e:
                errLog.append(_("row %(row)d. %(raw)s") % {
                    'row': reader.line_num,
                    'raw': filter(lambda x: x in string.printable, e.__str__())})
            else:
                rowOKCount += 1
    except csv.Error, e:
        errLog.append(_("row %(row)d (csv). %(raw)s") % {'row': reader.line_num, 'raw': e})
    except UnicodeError:
        errLog.append(_("File, you are loading is not valid CSV."))
    except Exception, e:
        errLog.append(_("Import error: %s." % e))
    title = _('Import CSV for task %s') % task

    return TemplateResponse(request, 'task_import_log.html', {
        'task': task,
        'file': request.FILES['taskfile'],
        'errLog': errLog,
        'rowOKCount': rowOKCount,
        'rowALLCount': rowALLCount,
        'title': title,
    })


class AjaxTaskActionView(View):
    def post(self, request, task_pk):
        task = get_object_or_404(Task, pk=task_pk)
        annotate_exmo_perms(task, request.user)
        if request.user.has_perm(self.permission_required, task):
            try:
                self.action(task)
            except ValidationError as e:
                # Action was not sucessful, task was not saved in the db
                # We should return actual task status from db, not the one that was modified in action
                task = get_object_or_404(Task, pk=task_pk)
                annotate_exmo_perms(task, request.user)
                # Add error messages to the status (concatenate all errors).
                status_display = '%s [%s]' % (task.get_status_display(), ' '.join(e.messages))
                return JSONResponse(status_display=status_display, perms=str(task.perms))
        elif not request.user.has_perm('exmo2010.view_task', task):
            raise PermissionDenied
        return JSONResponse(status_display=task.get_status_display(), perms=str(task.perms))


class AjaxTaskCloseView(AjaxTaskActionView):
    permission_required = 'exmo2010.close_task'
    action = lambda self, task: task._set_ready(True)


class AjaxTaskOpenView(AjaxTaskActionView):
    permission_required = 'exmo2010.open_task'
    action = lambda self, task: task._set_open(True)


class AjaxTaskApproveView(AjaxTaskActionView):
    permission_required = 'exmo2010.approve_task'
    action = lambda self, task: task._set_approved(True)


class TaskMixin(LoginRequiredMixin):
    def get_success_url(self):
        url = reverse('exmo2010:tasks_by_monitoring', args=[self.monitoring.pk])
        return '%s?%s' % (url, self.request.GET.urlencode())


class TaskEditView(TaskMixin, UpdateView):
    ''' View for task editing and creation '''
    template_name = "exmo2010/task_form.html"

    def get_form_class(self):
        if self.object:
            # Existing task edit page
            form_class = modelform_factory(Task, widgets={'organization': HiddenInput})
        else:
            # New task page
            form_class = modelform_factory(Task, exclude=['status'])

        # Limit assigned user choices to active experts.
        _experts = User.objects.filter(groups__name__in=UserProfile.expert_groups, is_active=True)
        form_class.base_fields['user'].queryset = _experts.distinct()

        # Limit organizations choices to this monitoring.
        form_class.base_fields['organization'].queryset = self.monitoring.organization_set.all()
        return form_class

    def get_object(self):
        if 'task_pk' in self.kwargs:
            # Existing task edit page
            task = get_object_or_404(Task, pk=self.kwargs['task_pk'])
            self.monitoring = task.organization.monitoring
        else:
            # New task page
            task = None
            self.monitoring = get_object_or_404(Monitoring, pk=self.kwargs['monitoring_pk'])

        if not self.request.user.has_perm('exmo2010.admin_monitoring', self.monitoring):
            raise PermissionDenied
        return task


class TaskDeleteView(TaskMixin, DeleteView):
    template_name = "exmo2010/task_confirm_delete.html"

    def get_object(self):
        task = get_object_or_404(Task, pk=self.kwargs['task_pk'])
        self.monitoring = task.organization.monitoring
        if not self.request.user.has_perm('exmo2010.admin_monitoring', self.monitoring):
            raise PermissionDenied
        return task


def task_history(request, task_pk):
    task = Task.objects.get(pk=task_pk)
    history = TaskHistory.objects.filter(task=task_pk)

    return TemplateResponse(request, 'task_history.html', {
        'task': task,
        'history': history,
        'title': task.organization.name,
    })


@login_required
def tasks_by_monitoring(request, monitoring_pk):
    if not request.user.is_expert:
        raise PermissionDenied
    monitoring = get_object_or_404(Monitoring, pk=monitoring_pk)
    profile = request.user.profile
    if not request.user.has_perm('exmo2010.view_monitoring', monitoring):
        return HttpResponseForbidden(_('Forbidden'))
    title = _('Task list for %(monitoring)s') % {'monitoring': monitoring}
    task_list = []
    queryset = Task.objects.filter(organization__monitoring=monitoring).select_related()
    for task in queryset:
        if request.user.has_perm('exmo2010.view_task', task):
            task_list.append(task.pk)
    if not task_list and not request.user.has_perm('exmo2010.admin_monitoring', monitoring):
        return HttpResponseForbidden(_('Forbidden'))
    queryset = Task.objects.filter(pk__in=task_list).extra(
        select={'complete_sql': Task.complete_sql_extra()}).select_related()
    if request.user.has_perm('exmo2010.admin_monitoring', monitoring):
        users = User.objects.filter(task__organization__monitoring=monitoring).distinct()
        UserChoice = [(u.username, u.profile.legal_name) for u in users]
        headers = (
            (_('organization'), 'organization__name', 'organization__name', None, None),
            (_('expert'), 'user__username', 'user__username', None, UserChoice),
            (_('status'), 'status', 'status', int, Task.TASK_STATUS),
            (_('complete, %'), None, None, None, None),
        )
    elif profile.is_expertB and not profile.is_expertA:
        filter1 = request.GET.get('filter1')
        if filter1:
            try:
                int(filter1)
            except ValueError:
                q = QueryDict('')
                request.GET = q
        headers = (
            (_('organization'), 'organization__name', 'organization__name', None, None),
            (_('status'), 'status', 'status', int, Task.TASK_STATUS),
            (_('complete, %'), None, None, None, None),
        )
    else:
        headers = (
            (_('organization'), 'organization__name', 'organization__name', None, None),
            (_('status'), 'status', 'status', int, Task.TASK_STATUS),
            (_('complete, %'), None, None, None, None),
        )

    return table(
        request,
        headers,
        queryset = queryset,
        paginate_by = 50,
        extra_context = {
            'monitoring': annotate_exmo_perms(monitoring, request.user),
            'title': title,
            'invcodeform': SettingsInvCodeForm(),
        },
        template_name="task_list.html",
    )


@login_required
def task_mass_assign_tasks(request, monitoring_pk):
    monitoring = get_object_or_404(Monitoring, pk = monitoring_pk)
    if not request.user.has_perm('exmo2010.admin_monitoring', monitoring):
        return HttpResponseForbidden(_('Forbidden'))
    organizations = Organization.objects.filter(monitoring = monitoring)
    title = _('Mass assign tasks')
    groups = []
    for group_name in ['expertsA','expertsB']:
        group, created = Group.objects.get_or_create(name = group_name)
        groups.append(group)
    users = User.objects.filter(is_active = True).filter(groups__in = groups)
    log = []
    if request.method == 'POST' and request.POST.has_key('organizations') and request.POST.has_key('users'):
        for organization_id in request.POST.getlist('organizations'):
            for user_id in request.POST.getlist('users'):
                try:
                    user = User.objects.get(pk = (user_id))
                    organization = Organization.objects.get(pk = int(organization_id))
                    task = Task(
                        user = user,
                        organization = organization,
                        status = Task.TASK_OPEN,
                    )
                    task.full_clean()
                    task.save()
                except ValidationError, e:
                    log.append('; '.join(['%s: %s' % (i[0], ', '.join(i[1])) for i in e.message_dict.items()]))
                except Exception, e:
                    log.append(e)
                else:
                    log.append('%s: %s' % (user.userprofile.legal_name, organization.name))

    return TemplateResponse(request, 'mass_assign_tasks.html', {
        'organizations': organizations,
        'users': users,
        'monitoring': monitoring,
        'log': log,
        'title': title,
    })
