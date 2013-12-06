# -*- coding: utf-8 -*-
# This file is part of EXMO2010 software.
# Copyright 2010, 2011б 2013 Al Nikolov
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
from django import forms

from exmo2010.models import Organization, InviteOrgs
from monitorings.views import replace_string


class OrganizationForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(OrganizationForm, self).__init__(*args, **kwargs)
        self.prefix = 'org'

    def save(self, *args, **kwargs):
        """
        Validate email and phone fields before saving the form.

        """
        for name in ['email', 'phone']:
            cell = getattr(self.instance, name)
            cell = replace_string(cell)
            setattr(self.instance, name, cell)

        return super(OrganizationForm, self).save(*args, **kwargs)

    class Meta:
        model = Organization
        exclude = ('keywords', 'comments', 'inv_code', 'inv_status')
        widgets = {
            'monitoring': forms.HiddenInput,
        }


class InviteOrgsForm(forms.ModelForm):

    class Meta:
        model = InviteOrgs
        exclude = ('timestamp',)
        widgets = {
            'monitoring': forms.HiddenInput,
            'subject': forms.TextInput,
        }
