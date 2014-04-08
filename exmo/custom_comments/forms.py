# -*- coding: utf-8 -*-
# This file is part of EXMO2010 software.
# Copyright 2010, 2011, 2013 Al Nikolov
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
from ckeditor.widgets import CKEditorWidget
from django import forms
from django.contrib.comments.forms import CommentForm, COMMENT_MAX_LENGTH
from django.forms.widgets import HiddenInput
from django.utils.translation import ugettext_lazy as _

from core.utils import urlize, clean_message, sanitize_field
from custom_comments.models import CommentExmo


class CustomCommentForm(CommentForm):
    status = forms.ChoiceField(choices=CommentExmo.STATUSES, label=_('status'), widget=HiddenInput(), initial=0)
    comment = forms.CharField(label=_('Comment'), widget=CKEditorWidget(config_name='simplified'), max_length=COMMENT_MAX_LENGTH)

    def check_for_duplicate_comment(self, new):
        """
        Проверяет дубликаты комментариев.
        В оргинальной функции возвращает старый коментарий,
        если он повторяется. Переопределена, чтобы пользователи могли
        оставлять повторяющиеся комментарии.

        """
        return new

    def get_comment_model(self):
        return CommentExmo

    def get_comment_create_data(self):
        data = super(CustomCommentForm, self).get_comment_create_data()
        data['comment'] = clean_message(data['comment'])
        return data

    def clean_comment(self):
        data = self.cleaned_data['comment']
        data = sanitize_field(data)
        data = urlize(data)
        return data
