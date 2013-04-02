# This file is part of EXMO2010 software.
# Copyright 2010, 2011 Al Nikolov
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
import xlwt
import xlrd
from django.shortcuts import get_object_or_404, render_to_response
from django.views.generic.create_update import update_object, delete_object
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.http import HttpResponse
from django.template import RequestContext
from django.http import HttpResponseForbidden
from django.core.urlresolvers import reverse
from reversion import revision
from exmo2010.forms import TaskForm, SettingsInvCodeForm
from exmo2010.models import Monitoring, Claim
from exmo2010.models import Organization, Parameter, Score, Task
from exmo2010.view.breadcrumbs import breadcrumbs
from exmo2010.view.helpers import table
from exmo2010.utils import UnicodeReader, UnicodeWriter


def task_export(request, id):
    task = get_object_or_404(Task, pk = id)
    if not request.user.has_perm('exmo2010.view_task', task):
        return HttpResponseForbidden(_('Forbidden'))
    parameters = Parameter.objects.filter(monitoring=task.organization.monitoring).exclude(exclude=task.organization)
    scores = Score.objects.filter(task=id, revision=Score.REVISION_DEFAULT)
    wbk = xlwt.Workbook()
    sheet = wbk.add_sheet('Task')

    # indexing is zero based, row then column

    table_head = [
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
    ]

    for i, c in enumerate(table_head):
        sheet.write(0, i, c)

    for i, p in enumerate(parameters):
        out = (
            p.code,
            p.name,
        )
        try:
            s = scores.get(parameter = p)
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
                out += ('', '')
            out += (s.comment,)

        for e, c in enumerate(out):
            sheet.write(i + 1, e, c)

    response = HttpResponse(mimetype="application/ms-excel")
    response['Content-Disposition'] = 'attachment; filename=task-%s.xls' % id
    wbk.save(response)
    return response



import re
@revision.create_on_success
@login_required
def task_import(request, id):
    task = get_object_or_404(Task, pk = id)
    if not request.user.has_perm('exmo2010.fill_task', task):
        return HttpResponseForbidden(_('Forbidden'))
    if not request.FILES.has_key('taskfile'):
        return HttpResponseRedirect(reverse('exmo2010:score_list_by_task', args=[id]))

    workbook = xlrd.open_workbook(request.FILES['taskfile'].temporary_file_path())
    worksheet = workbook.sheet_by_index(0)
    num_rows = worksheet.nrows - 1
    num_cells = worksheet.ncols - 1
    curr_row = -1

    reader = []

    while curr_row < num_rows:
        curr_row += 1
        curr_cell = -1
        row = []
        while curr_cell < num_cells:
            curr_cell += 1
            cell_value = worksheet.cell_value(curr_row, curr_cell)
            if isinstance(cell_value, float) or isinstance(cell_value, int):
                cell_value = str(cell_value)
            row.append(cell_value)

        reader.append(row)

    errLog = []
    rowOKCount = 0
    rowALLCount = 0

    def to_int(val):
        if val == "0.0":
            return int(0)
        elif val == '':
            return int(0)
        elif val == 'None':
            return int(0)
        else:
            return int(float(val))

    try:
        for i, row in enumerate(reader):
            rowALLCount += 1
            if row[0].startswith('#'):
                errLog.append(_("row %d. Starts with '#'. Skipped") % i)
                continue
            try:
                code = re.match('^(\d+)$', row[0])
                if not code:
                  errLog.append(_("row %(row)d (csv). Not a code: %(raw)s") % {'row': i, 'raw': row[0]})
                  continue
                if (
                    row[2]  == '' and
                    row[3]  == '' and
                    row[4]  == '' and
                    row[5]  == '' and
                    row[6]  == '' and
                    row[7]  == '' and
                    row[8]  == '' and
                    row[9]  == '' and
                    row[10] == '' and
                    row[11] == '' and
                    row[12] == '' and
                    row[13] == '' and
                    row[14] == '' and
                    row[15] == ''
                  ):
                    errLog.append(_("row %(row)d (csv). Empty score: %(raw)s") % {'row': i, 'raw': row[0]})
                    continue
                parameter = Parameter.objects.get(code=code.group(1), monitoring = task.organization.monitoring)
                try:
                    score = Score.objects.get(task = task, parameter = parameter)
                except Score.DoesNotExist:
                    score = Score()

                score.task              = task
                score.parameter         = parameter
                score.found             = to_int(row[2])
                score.complete          = to_int(row[3])
                score.completeComment   = row[4]
                score.topical           = to_int(row[5])
                score.topicalComment    = row[6]
                score.accessible        = to_int(row[7])
                score.accessibleComment = row[8]
                score.hypertext         = to_int(row[9])
                score.hypertextComment  = row[10]
                score.document          = to_int(row[11])
                score.documentComment   = row[12]
                score.image             = to_int(row[13])
                score.imageComment      = row[14]
                score.comment           = to_int(row[15])
                score.full_clean()
                score.save()
            except ValidationError, e:
                errLog.append(_("row %(row)d (validation). %(raw)s") % {
                    'row': i,
                    'raw': '; '.join(['%s: %s' % (i[0], ', '.join(i[1])) for i in e.message_dict.items()])})
            except Parameter.DoesNotExist:
                errLog.append(_("row %(row)d. %(raw)s") % {
                    'row': i,
                    'raw': _('Parameter matching query does not exist')})
            except Exception, e:
                errLog.append(_("row %(row)d. %(raw)s") % {
                    'row': i,
                    'raw': e})
            else:
                rowOKCount += 1
    except csv.Error, e:
        errLog.append(_("row %(row)d (csv). %(raw)s") % {'row': 0, 'raw': e})
    title = _('Import CSV for task %s') % task

    crumbs = ['Home', 'Monitoring', 'Organization', 'ScoreList']
    breadcrumbs(request, crumbs, task)
    current_title = _('Import task')

    return render_to_response(
        'exmo2010/task_import_log.html',
        {
            'task': task,
            'file': request.FILES['taskfile'],
            'errLog': errLog,
            'rowOKCount': rowOKCount,
            'rowALLCount': rowALLCount,
            'current_title': current_title,
            'title': title,
        },
        context_instance=RequestContext(request),
    )



def tasks(request):
    return HttpResponseRedirect(reverse('exmo2010:monitoring_list'))



def tasks_by_monitoring_and_organization(request, monitoring_id, organization_id):
    '''We have 3 generic group: experts, customers, organizations.
    Superusers: all tasks
    Experts: only own tasks
    Customers: all approved tasks
    organizations: all approved tasks of organizations that belongs to user
    Also for every ogranization we can have group'''
    monitoring = get_object_or_404(Monitoring, pk = monitoring_id)
    organization = get_object_or_404(Organization, pk = organization_id)
    user = request.user
    profile = None
    if user.is_active: profile = user.profile
    if not user.has_perm('exmo2010.view_monitoring', monitoring):
        return HttpResponseForbidden(_('Forbidden'))
    title = _('Task list for %s') % organization.name
    queryset = Task.objects.filter(organization = organization)
    # Or, filtered by user
    if user.has_perm('exmo2010.admin_monitoring', monitoring):
      headers = (
                (_('organization'), 'organization__name', 'organization__name', None, None),
                (_('expert'), 'user__username', 'user__username', None, None),
                (_('status'), 'status', 'status', int, Task.TASK_STATUS),
                (_('complete, %'), None, None, None, None),
                (_('openness, %'), None, None, None, None),
              )
    elif profile and profile.is_expert:
    # Or, without Expert
      headers = (
                (_('organization'), 'organization__name', 'organization__name', None, None),
                (_('status'), 'status', 'status', int, Task.TASK_STATUS),
                (_('complete, %'), None, None, None, None),
                (_('openness, %'), None, None, None, None)
              )
    else:
      queryset = Task.approved_tasks.all()
      queryset = queryset.filter(organization = organization)
      headers = (
                (_('organization'), 'organization__name', 'organization__name', None, None),
                (_('openness, %'), None, None, None, None)
              )
    task_list = []
    for task in queryset:
        if user.has_perm('exmo2010.view_task', task): task_list.append(task.pk)
    queryset = Task.objects.filter(pk__in = task_list)

    crumbs = ['Home', 'Monitoring', 'Organization']
    breadcrumbs(request, crumbs, monitoring)
    current_title = _('Organization')

    return table(request, headers, queryset=queryset, paginate_by=15,
                 extra_context={
                     'monitoring': monitoring,
                     'organization': organization,
                     'current_title': current_title,
                     'title': title,
                 })



@revision.create_on_success
@login_required
def task_add(request, monitoring_id, organization_id=None):
    monitoring = get_object_or_404(Monitoring, pk = monitoring_id)
    if organization_id:
        organization = get_object_or_404(Organization, pk = organization_id)
        redirect = '%s?%s' % (reverse('exmo2010:tasks_by_monitoring_and_organization', args=[monitoring.pk, organization.pk]), request.GET.urlencode())
        title = _('Add new task for %s') % organization.name
    else:
        organization = None
        redirect = '%s?%s' % (reverse('exmo2010:tasks_by_monitoring', args=[monitoring.pk]), request.GET.urlencode())
        title = _('Add new task for %s') % monitoring

    redirect = redirect.replace("%","%%")
    current_title = _('Add task')
    if request.user.has_perm('exmo2010.admin_monitoring', monitoring):
        if request.method == 'GET':
            form = TaskForm(initial={'organization': organization}, monitoring=monitoring)

            crumbs = ['Home', 'Monitoring', 'Organization']
            breadcrumbs(request, crumbs, monitoring)

            return render_to_response(
                'exmo2010/task_form.html',
                {
                    'monitoring': monitoring,
                    'organization': organization,
                    'current_title': current_title,
                    'title': title,
                    'form': form
                },
                context_instance=RequestContext(request),
            )
        if request.method == 'POST':
            form = TaskForm(request.POST, monitoring=monitoring)
            if form.is_valid():
                form.save()
                return HttpResponseRedirect(redirect)
            else:

                crumbs = ['Home', 'Monitoring', 'Organization']
                breadcrumbs(request, crumbs, monitoring)

                return render_to_response(
                    'exmo2010/task_form.html',
                    {
                        'monitoring': monitoring,
                        'organization': organization,
                        'current_title': current_title,
                        'title': title,
                        'form': form
                    },
                    context_instance=RequestContext(request),
                )
    else: return HttpResponseForbidden(_('Forbidden'))



@revision.create_on_success
@login_required
def task_manager(request, task_id, method, monitoring_id=None, organization_id=None):
    task = get_object_or_404(Task, pk=task_id)
    organization = task.organization
    monitoring = organization.monitoring
    organization_from_get = request.GET.get('organization', '')
    if organization_id or organization_from_get:
        q = request.GET.copy()
        if organization_from_get:
            q.pop('organization')
        redirect = '%s?%s' % (
        reverse('exmo2010:tasks_by_monitoring_and_organization', args=[monitoring.pk, organization.pk]), q.urlencode())
    else:
        redirect = '%s?%s' % (reverse('exmo2010:tasks_by_monitoring', args=[monitoring.pk]), request.GET.urlencode())
    redirect = redirect.replace("%", "%%")
    valid_method = [
        'delete', 'approve', 'close',
        'open', 'check', 'update', 'get',
        ]
    if method not in valid_method:
        HttpResponseForbidden(_('Forbidden'))
    current_title = _('Edit task')
    if method == 'delete':
        title = _('Delete task %s') % task
        if request.user.has_perm('exmo2010.admin_monitoring', monitoring):

            crumbs = ['Home', 'Monitoring', 'Organization']
            breadcrumbs(request, crumbs, task)
            current_title = _('Delete task')

            return delete_object(
                request,
                model=Task,
                object_id=task_id,
                post_delete_redirect=redirect,
                extra_context={
                    'monitoring': monitoring,
                    'organization': organization,
                    'current_title': current_title,
                    'title': title,
                    'deleted_objects': Score.objects.filter(task=task),
                }
            )
        else: return HttpResponseForbidden(_('Forbidden'))
    elif method == 'close':
        title = _('Close task %s') % task
        if request.user.has_perm('exmo2010.close_task', task):
            if task.open:
                try:
                    revision.comment = _('Task ready')
                    task.ready = True
                except ValidationError, e:
                    return HttpResponse('%s' % e.message_dict.get('__all__')[0])
            else:
                return HttpResponse(_('Already closed'))
        else: return HttpResponseForbidden(_('Forbidden'))
    elif method == 'approve':
        title = _('Approve task for %s') % task
        if request.user.has_perm('exmo2010.approve_task', task):
            if not task.approved:
                try:
                    revision.comment = _('Task approved')
                    task.approved = True
                except ValidationError, e:
                    return HttpResponse('%s' % e.message_dict.get('__all__')[0])
            else: return HttpResponse(_('Already approved'))
        else: return HttpResponseForbidden(_('Forbidden'))
    elif method == 'open':
        title = _('Open task %s') % task
        if request.user.has_perm('exmo2010.open_task', task):
            if not task.open:
                try:
                    revision.comment = _('Task openned')
                    task.open = True
                except ValidationError, e:
                    return HttpResponse('%s' % e.message_dict.get('__all__')[0])
            else: return HttpResponse(_('Already open'))
        else: return HttpResponseForbidden(_('Forbidden'))
    elif method == 'check':
        title = _('Check task %s') % task
        if request.user.has_perm('exmo2010.check_task', task):
            if task.ready:
                try:
                    revision.comment = _('Task on check')
                    task.checked = True
                except ValidationError, e:
                    return HttpResponse('%s' % e.message_dict.get('__all__')[0])
            else: return HttpResponse(_('Already on check'))
        else: return HttpResponseForbidden(_('Forbidden'))
    elif method == 'update': #update
        title = _('Edit task %s') % task
        if request.user.has_perm('exmo2010.admin_monitoring', monitoring):
            revision.comment = _('Task updated')

            crumbs = ['Home', 'Monitoring', 'Organization']
            breadcrumbs(request, crumbs, task)

            return update_object(
                request,
                form_class=TaskForm,
                object_id=task.pk,
                post_save_redirect=redirect,
                extra_context={
                    'monitoring': monitoring,
                    'organization': organization,
                    'current_title': current_title,
                    'title': title,
                }
            )
        else: return HttpResponseForbidden(_('Forbidden'))
    return render_to_response(
      'exmo2010/ajax/task_status.html', {
        'object': task,
      }, context_instance=RequestContext(request))




def tasks_by_monitoring(request, monitorgin_id):
    monitoring = get_object_or_404(Monitoring, pk=monitorgin_id)
    profile = None
    if request.user.is_active:
        profile = request.user.profile
    if not request.user.has_perm('exmo2010.view_monitoring', monitoring):
        return HttpResponseForbidden(_('Forbidden'))
    title = _('Task list for %(monitoring)s') % {'monitoring': monitoring}
    task_list = []
    queryset = Task.objects.filter(organization__monitoring=monitoring).\
    select_related()
    for task in queryset:
        if request.user.has_perm('exmo2010.view_task', task):
            task_list.append(task.pk)
    if not task_list and not \
    request.user.has_perm('exmo2010.admin_monitoring', monitoring):
        return HttpResponseForbidden(_('Forbidden'))
    queryset = Task.objects.filter(pk__in=task_list)
    if request.user.has_perm('exmo2010.admin_monitoring', monitoring):
        users = User.objects.filter(task__organization__monitoring = monitoring).distinct()
        UserChoice = [(u.username, u.profile.legal_name) for u in users]
        headers = (
            (_('organization'), 'organization__name', 'organization__name',
             None, None),
            (_('expert'), 'user__username', 'user__username', None, UserChoice),
            (_('status'), 'status', 'status', int, Task.TASK_STATUS),
            (_('complete, %'), None, None, None, None),
            )
    elif profile and profile.is_expert:
        headers = (
            (_('organization'), 'organization__name', 'organization__name',
             None, None),
             (_('status'), 'status', 'status', int, Task.TASK_STATUS),
             (_('complete, %'), None, None, None, None),
            )
    else:
        headers = (
            (_('organization'), 'organization__name', 'organization__name',
             None, None),
            )

    crumbs = ['Home', 'Monitoring']
    breadcrumbs(request, crumbs)

    if request.expert:
        current_title = _('Monitoring cycle')
    else:
        current_title = _('Rating') if monitoring.status == 5 else _('Tasks')

    return table(
        request,
        headers,
        queryset = queryset,
        paginate_by = 50,
        extra_context = {
            'monitoring': monitoring,
            'current_title': current_title,
            'title': title,
            'invcodeform': SettingsInvCodeForm(),
            },
        template_name = "exmo2010/task_list.html",
        )


@login_required
def task_mass_assign_tasks(request, id):
    monitoring = get_object_or_404(Monitoring, pk = id)
    if not request.user.has_perm('exmo2010.admin_monitoring', monitoring):
        return HttpResponseForbidden(_('Forbidden'))
    organizations = Organization.objects.filter(monitoring = monitoring)
    title = _('Mass assign tasks')
    groups = []
    for group_name in ['expertsA','expertsB','expertsB_manager']:
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

    crumbs = ['Home', 'Monitoring']
    breadcrumbs(request, crumbs)

    if request.expert:
        current_title = _('Monitoring cycle')
    else:
        current_title = _('Rating') if monitoring.status == 5 else _('Tasks')

    return render_to_response(
        'exmo2010/mass_assign_tasks.html', {
            'organizations': organizations,
            'users': users,
            'monitoring': monitoring,
            'log': log,
            'current_title': current_title,
            'title': title,
        }, context_instance=RequestContext(request))
