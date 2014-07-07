# -*- coding: utf-8 -*-
# This file is part of EXMO2010 software.
# Copyright 2010, 2011 Al Nikolov
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
from django.contrib import admin
from modeltranslation.admin import TranslationAdmin, TabbedTranslationAdmin
from reversion.admin import VersionAdmin

from . import models


def register(model):
    def wrapper(cls):
        admin.site.register(model, cls)
        return cls
    return wrapper


admin.site.register(models.OpennessExpression)


@register(models.Monitoring)
class MonitoringAdmin(TranslationAdmin, VersionAdmin):
    list_display = ('name',)


@register(models.Organization)
class OrganizationAdmin(TranslationAdmin, VersionAdmin):
    list_display = ('pk', 'name', 'inv_code')
    search_fields = ('name', 'inv_code')
    list_filter = ('monitoring',)
    readonly_fields = ('inv_code',)


@register(models.Parameter)
class ParameterAdmin(TabbedTranslationAdmin, VersionAdmin):
    class Media:
        css = {"all": ("exmo2010/css/selector.css",)}

    raw_id_fields = ('exclude',)
    list_display = search_fields = ('code', 'name',)
    list_filter = ('monitoring', 'npa')


@register(models.StaticPage)
class StaticPageAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    list_display = search_fields = ('id', 'description')


@register(models.LicenseTextFragments)
class LicenseTextFragmentsAdmin(TabbedTranslationAdmin, admin.ModelAdmin):
    list_display = ('id', 'page_footer', 'csv_footer', 'json_name', 'json_url', 'json_rightsholder', 'json_source')


@register(models.ObserversGroup)
class ObserversGroupAdmin(admin.ModelAdmin):
    list_display = search_fields = ('name',)
    raw_id_fields = ('organizations', 'users')
    list_filter = ('monitoring',)
