# This file is part of EXMO2010 software.
# Copyright 2010 Institute for Information Freedom Development
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
from django import template
from exmo.exmo2010.models import Organization, Task

def monitoring_stats(context, monitoring):
    approved_organizations = Organization.objects.filter(type = monitoring.type, task__status = Task.TASK_APPROVED).distinct()
    approved_organizations_pk = [o.pk for o in approved_organizations]
    organization_all_count = Organization.objects.filter(type = monitoring.type).distinct().count()
    organization_ready_count = Organization.objects.filter(type = monitoring.type, task__status = Task.TASK_READY).exclude(pk__in = approved_organizations_pk).distinct().count()
    organization_approved_count = approved_organizations.count()
    organization_with_task_count = Organization.objects.filter(type = monitoring.type, task__status__isnull = False).distinct().count()
    return {
            'organization_all_count': organization_all_count,
            'organization_ready_count': organization_ready_count,
            'organization_approved_count': organization_approved_count,
            'organization_with_task_count': organization_with_task_count,
            'monitoring': monitoring,
    }

register = template.Library()
register.inclusion_tag('exmo2010/monitoring_stats.html', takes_context=True)(monitoring_stats)