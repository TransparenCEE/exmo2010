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
from datetime import datetime
from django.db import models
from django.utils.translation import ugettext as _
from django.contrib.comments.models import Comment


class CommentExmo(Comment):
    """
    Кастомная модель комментария, добавлено поле "status".

    """
    OPEN = 0
    ANSWERED = 1
    NOT_ANSWERED = 2

    STATUSES = (
        (OPEN, _('Comment is open')),
        (ANSWERED, _('Comment is closed and answered')),
        (NOT_ANSWERED, _('Comment is closed and not answered')),
    )

    status = models.PositiveIntegerField(choices=STATUSES, default=OPEN, verbose_name=_('status'))
    answered_date = models.DateTimeField(default=datetime.min)
    posted_by_expert = models.BooleanField(default=False, verbose_name=_('posted by expert'))
