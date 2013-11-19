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
from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.forms.widgets import Textarea
from django.utils import formats
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _

DATETIME_INPUT_FORMATS = formats.get_format('DATETIME_INPUT_FORMATS') + ('%d.%m.%Y %H:%M:%S',)

# основные JS ресурсы для форм с виджетами из админки
CORE_JS = (
    settings.STATIC_URL + 'admin/js/core.js',
    settings.STATIC_URL + 'admin/js/admin/RelatedObjectLookups.js',
    settings.STATIC_URL + 'exmo2010/js/jquery/jquery.min.js',
    settings.STATIC_URL + 'admin/js/jquery.init.js',
    settings.STATIC_URL + 'admin/js/actions.min.js',
)

CORE_MEDIA = forms.Media(js=CORE_JS)


def add_required_label_tag(original_function):
    """Adds the 'required' CSS class and an asterisks to required field labels."""
    def required_label_tag(self, contents=None, attrs=None):
        contents = contents or escape(self.label)
        if self.field.required:
            if not self.label.endswith("*"):
                self.label += "*"
                contents += "*"
            attrs = {'class': 'required'}
        return original_function(self, contents, attrs)
    return required_label_tag


def decorate_bound_field():
    from django.forms.forms import BoundField
    BoundField.label_tag = add_required_label_tag(BoundField.label_tag)
decorate_bound_field()


class HorizRadioRenderer(forms.RadioSelect.renderer):
    """ this overrides widget method to put radio buttons horizontally
        instead of vertically.
    """
    def render(self):
        """Outputs radios"""
        return mark_safe(u'\n'.join([u'%s\n' % w for w in self]))


class EmailReadonlyWidget(forms.Widget):
    def render(self, name, value=" ", attrs=None):
        html = '<p id="id_%(name)s" name="%(name)s">%(value)s</p>' % \
               {'name': name, 'value': value}
        return mark_safe(html)


class TagAutocomplete(Textarea):
    input_type = 'text'

    def render(self, name, value, attrs=None):
        json_view = reverse('tagging_autocomplete-list')
        html = super(TagAutocomplete, self).render(name, value, attrs)
        js = u'<script type="text/javascript">jQuery().ready(function() { ' \
             u'jQuery("#%s").autocomplete("%s", { multiple: true }); });</script>' % (attrs['id'], json_view)
        return mark_safe("\n".join([html, js]))

    class Media:
        js_base_url = getattr(settings,
                              'TAGGING_AUTOCOMPLETE_JS_BASE_URL',
                              '%s/jquery-autocomplete' % settings.MEDIA_URL)
        css = {
            'all': ('%s/jquery.autocomplete.css' % js_base_url,)
        }
        js = (
            '%sadmin/js/jquery.js' % settings.STATIC_URL,
            '%s/jquery.autocomplete.js' % js_base_url,
        )


class FeedbackForm(forms.Form):
    email = forms.EmailField(label=_("E-mail"), required=True)
    comment = forms.CharField(widget=forms.Textarea, label=_('Your problem'), required=True)


class CertificateOrderForm(forms.Form):
    CERTIFICATE_FOR_CHOICES = (
        (0, _('to organization')),
        (1, _('to employee')),
    )

    DELIVERY_METHOD_CHOICES = (
        (0, _('by email')),
        (1, _('by post')),
    )

    task_id = forms.IntegerField(required=False)
    certificate_for = forms.ChoiceField(label=_('Certificate for'), choices=CERTIFICATE_FOR_CHOICES,
                                        widget=forms.RadioSelect(), initial=0, required=False)
    delivery_method = forms.ChoiceField(label=_('Send'), choices=DELIVERY_METHOD_CHOICES, widget=forms.RadioSelect(),
                                        initial=0, required=False)
    name = forms.CharField(label=_('Name'), max_length=100, required=False)
    wishes = forms.CharField(label=_('Wishes'), widget=Textarea(), required=False)
    email = forms.EmailField(label=_('Email'), max_length=100, required=False)
    for_whom = forms.CharField(label=_('For whom'), max_length=100, required=False)
    zip_code = forms.CharField(label=_('Zip code'), max_length=6, min_length=6, required=False)
    address = forms.CharField(label=_('Address'), widget=Textarea(), required=False)
