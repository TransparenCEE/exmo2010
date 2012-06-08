# This file is part of EXMO2010 software.
# Copyright 2010, 2011 Al Nikolov
# Copyright 2010, 2011, 2012 Institute for Information Freedom Development
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
from exmo2010.view.helpers import table
from django.shortcuts import get_object_or_404
from django.views.generic.create_update import update_object, create_object, delete_object
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _
from exmo2010.models import Organization, Task
from exmo2010.models import Monitoring
from django.db.models import Q
from django.db.models import Count
from django.views.decorators.csrf import csrf_protect
from django.http import HttpResponseForbidden
from django.core.urlresolvers import reverse
from exmo2010.forms import OrganizationForm, CORE_MEDIA


def organization_list(request, id):
    monitoring = get_object_or_404(Monitoring, pk = id)
    if not request.user.has_perm('exmo2010.view_monitoring', monitoring): return HttpResponseForbidden(_('Forbidden'))
    title = _('Organizations for monitoring %(name)s') % {'name': monitoring}
    if request.user.has_perm('exmo2010.admin_monitoring', monitoring):
        queryset = Organization.objects.filter(monitoring = monitoring).extra(
            select = {
                'task__count':'SELECT count(*) FROM %s WHERE organization_id = %s.id' % (Task._meta.db_table, Organization._meta.db_table),
                }
            )
        headers = (
                (_('organization'), 'name', 'name', None, None),
                (_('tasks'), 'task__count', None, None, None),
                )
    else:
        org_list = []
        for task in Task.objects.filter(organization__monitoring = monitoring).select_related():
            if request.user.has_perm('exmo2010.view_task', task): org_list.append(task.organization.pk)
        org_list = list(set(org_list))
        if not org_list: return HttpResponseForbidden(_('Forbidden'))
        queryset = Organization.objects.filter(pk__in = org_list)
        headers = (
                (_('organization'), 'name', 'name', None, None),
                )
    return table(
        request,
        headers,
        queryset = queryset,
        paginate_by = 50,
        extra_context = {
            'title': title,
            'monitoring': monitoring,
        },
    )



@login_required
def organization_manager(request, monitoring_id, id, method):
    monitoring = get_object_or_404(Monitoring, pk = monitoring_id)
    if not request.user.has_perm('exmo2010.admin_monitoring', monitoring):
        return HttpResponseForbidden(_('Forbidden'))
    redirect = '%s?%s' % (reverse('exmo2010:organization_list', args=[monitoring.pk]), request.GET.urlencode())
    redirect = redirect.replace("%","%%")
    if method == 'add':
        title = _('Add new organization for %s') % monitoring
        return create_object(request, form_class = OrganizationForm, post_save_redirect = redirect, extra_context = {'title': title, 'monitoring': monitoring,})
    elif method == 'delete':
        organization = get_object_or_404(Organization, pk = id)
        title = _('Delete organization %s') % monitoring
        return delete_object(
            request,
            model = Organization,
            object_id = id,
            post_delete_redirect = redirect,
            extra_context = {
                'title': title,
                'monitoring': monitoring,
                'deleted_objects': Task.objects.filter(organization = organization),
                }
            )
    else: #update
        organization = get_object_or_404(Organization, pk = id)
        title = _('Edit organization %s') % monitoring
        return update_object(
            request,
            form_class = OrganizationForm,
            object_id = id,
            post_save_redirect = redirect,
            extra_context = {
                'title': title,
                'monitoring': monitoring,
                }
            )
