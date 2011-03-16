# This file is part of EXMO2010 software.
# Copyright 2010-2011, 2011 Al Nikolov
# Copyright 2010-2011, 2011 Institute for Information Freedom Development
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
import exmo.exmo2010.models
from django.contrib import admin
from reversion.admin import VersionAdmin
from django.db import models
from django.contrib.auth.admin import UserAdmin

UserAdmin.filter_horizontal = ('user_permissions', 'groups')

class ParameterAdmin(admin.ModelAdmin):
    search_fields = ('name', )
    formfield_overrides = {
        models.ManyToManyField: {
            'widget': admin.widgets.FilteredSelectMultiple('',
                                                           is_stacked=False)
        },
    }

class ParameterMonitoringPropertyInline(admin.StackedInline):
  model = exmo.exmo2010.models.ParameterMonitoringProperty
  max_num = 300

class TaskAdmin(VersionAdmin):
    pass

class ScoreAdmin(VersionAdmin):
    pass

class OrganizationTypeAdmin(admin.ModelAdmin):
  list_display = ('pk', 'name')

class OrganizationAdmin(admin.ModelAdmin):
  list_display = ('pk', 'name')
  search_fields = ('name', )

class FederalAdmin(admin.ModelAdmin):
  list_display = ('pk', 'name')

class MonitoringAdmin(admin.ModelAdmin):
  list_display = ('type', 'name')
  inlines = ParameterMonitoringPropertyInline,

class UserProfileAdmin(admin.ModelAdmin):
    search_fields = ('user__username', )
    formfield_overrides = {
        models.ManyToManyField: {
            'widget': admin.widgets.FilteredSelectMultiple('',
                                                           is_stacked=False)
        },
    }

admin.site.register(exmo.exmo2010.models.Organization, OrganizationAdmin)
admin.site.register(exmo.exmo2010.models.Category)
admin.site.register(exmo.exmo2010.models.Subcategory)
admin.site.register(exmo.exmo2010.models.Parameter, ParameterAdmin)
admin.site.register(exmo.exmo2010.models.ParameterType)
admin.site.register(exmo.exmo2010.models.OrganizationType, OrganizationTypeAdmin)
admin.site.register(exmo.exmo2010.models.Score, ScoreAdmin)
admin.site.register(exmo.exmo2010.models.Entity)
admin.site.register(exmo.exmo2010.models.Federal, FederalAdmin)
admin.site.register(exmo.exmo2010.models.Task, TaskAdmin)
admin.site.register(exmo.exmo2010.models.Monitoring, MonitoringAdmin)
admin.site.register(exmo.exmo2010.models.Claim)
admin.site.register(exmo.exmo2010.models.UserProfile, UserProfileAdmin)
admin.site.register(exmo.exmo2010.models.OpennessExpression)
