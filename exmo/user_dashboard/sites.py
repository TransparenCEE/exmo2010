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

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.translation import ugettext as _

class DashboardSite(object):
    def __init__(self, name = None, app_name = 'user_dashboard'):
        self._registry = {}
        if name:
            self.name = name
        else:
            self.name = 'user_dashboard'
        self.app_name = app_name

    def get_urls(self):
        from django.conf.urls.defaults import patterns, url, include
        urlpatterns = patterns('',
            url(r'^$',
                self.index,
                name='index'),
        )
        return urlpatterns

    def index(self, request, extra_context=None):
        context = {
            'title': _('Dashboard'),
            'app_list': None,
            'root_path': None,
            'user_dashboard': True,
        }
        return render_to_response('admin/index.html', context,
            context_instance=RequestContext(request)
        )

    @property
    def urls(self):
        return self.get_urls(), self.app_name, self.name

site = DashboardSite()