# -*- coding: utf-8 -*-
# This file is part of EXMO2010 software.
# Copyright 2013 Al Nikolov
# Copyright 2013-2014 Foundation "Institute for Information Freedom Development"
# Copyright 2016 IRSI LTD
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
from django.contrib.auth.models import User
from django.core import mail
from django.core.urlresolvers import reverse
from core.test_utils import TestCase
from model_mommy import mommy
from nose_parameterized import parameterized

from exmo2010.models import (
    Monitoring, Organization, Score, Clarification, OrgUser,
    ObserversGroup, Task, MONITORING_RATE)


class ClarificationCreateAccessTestCase(TestCase):
    # exmo2010:clarification_create

    # Should allow only expertA to create clarification

    def setUp(self):
        # GIVEN organization in RATE monitoring
        org = mommy.make(Organization, monitoring__status=MONITORING_RATE)

        # AND user without any permissions
        User.objects.create_user('user', 'user@svobodainfo.org', 'password')
        # AND expert B
        expertB = User.objects.create_user('expertB', 'expertB@svobodainfo.org', 'password')
        expertB.profile.is_expertB = True
        # AND expert A
        expertA = User.objects.create_user('expertA', 'expertA@svobodainfo.org', 'password')
        expertA.profile.is_expertA = True
        # AND organization representative
        orguser = User.objects.create_user('orguser', 'orguser@svobodainfo.org', 'password')
        mommy.make(OrgUser, organization=org, userprofile=orguser.profile)
        # AND observer user
        observer = User.objects.create_user('observer', 'observer@svobodainfo.org', 'password')
        # AND observers group for rate monitoring
        obs_group = mommy.make(ObserversGroup, monitoring=org.monitoring)
        obs_group.organizations = [org]
        obs_group.users = [observer]

        # AND score for expertB task
        score = mommy.make(Score, task__organization=org, task__user=expertB)
        # AND clarification in that score
        self.clarification = mommy.make(Clarification, score=score)

        self.url = reverse('exmo2010:clarification_create', args=[score.pk])

    def test_allow_expertA_clarification_creation(self):
        self.client.login(username='expertA', password='password')

        # WHEN expertA submits clarification form
        response = self.client.post(self.url, {'clarification-comment': 'lol'}, follow=True)

        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)

        # THEN new clarification should get created in the database (2 clarification should exist)
        self.assertEqual(Clarification.objects.count(), 2)

    @parameterized.expand([
        ('user',),
        ('org',),
        ('observer',),
        ('expertB',),
    ])
    def test_forbid_unauthorized_clarification_creation(self, username):
        self.client.login(username=username, password='password')

        # WHEN unauthorized user forges and POSTs clarification form
        self.client.post(self.url, {'clarification-comment': 'lol'})

        # THEN clarification should not get created in the database (only one clarification exist)
        self.assertEqual(Clarification.objects.count(), 1)


class ClarificationAnswerAccessTestCase(TestCase):
    # exmo2010:clarification_answer

    # Should allow only expertB to answer clarification

    def setUp(self):
        # GIVEN organization in MONITORING_RATE monitoring
        org = mommy.make(Organization, monitoring__status=MONITORING_RATE)

        # AND user without any permissions
        User.objects.create_user('user', 'user@svobodainfo.org', 'password')
        # AND superuser
        User.objects.create_superuser('admin', 'admin@svobodainfo.org', 'password')
        # AND expert B
        expertB = User.objects.create_user('expertB', 'expertB@svobodainfo.org', 'password')
        expertB.profile.is_expertB = True
        # AND expert A
        expertA = User.objects.create_user('expertA', 'expertA@svobodainfo.org', 'password')
        expertA.profile.is_expertA = True
        # AND organization representative
        orguser = User.objects.create_user('orguser', 'orguser@svobodainfo.org', 'password')
        mommy.make(OrgUser, organization=org, userprofile=orguser.profile)
        # AND observer user
        observer = User.objects.create_user('observer', 'observer@svobodainfo.org', 'password')
        # AND observers group for rate monitoring
        obs_group = mommy.make(ObserversGroup, monitoring=org.monitoring)
        obs_group.organizations = [org]
        obs_group.users = [observer]

        # AND score for expertB task
        score = mommy.make(Score, task__organization=org, task__user=expertB)
        # AND clarification in that score
        self.clarification = mommy.make(Clarification, score=score)

        answer_field = '%s-answer' % self.clarification.answer_form().prefix
        self.answer_data = {answer_field: 'lol'}

        self.url = reverse('exmo2010:clarification_answer', args=[self.clarification.pk])

    @parameterized.expand([
        ('user',),
        ('org',),
        ('observer',),
        ('expertA',),
    ])
    def test_forbid_unauthorized_clarification_answer(self, username):
        self.client.login(username=username, password='password')

        # WHEN unauthorized user forges and POSTs clarification form with answer to existing clarification
        self.client.post(self.url, self.answer_data)

        # THEN clarification answer should not change in the database
        self.assertEqual(Clarification.objects.get(pk=self.clarification.pk).answer, '')

    def test_allow_expertB_clarification_answer(self):
        self.client.login(username='expertB', password='password')

        # WHEN expertB submits clarification form with answer to existing clarification
        response = self.client.post(self.url, self.answer_data, follow=True)

        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)

        # THEN clarification answer should change in the database
        self.assertEqual(Clarification.objects.get(pk=self.clarification.pk).answer, u'<p>lol</p>')


class ClarificationEmailNotifyTestCase(TestCase):
    # Should send email notification when clarification is created

    def setUp(self):
        # GIVEN MONITORING_RATE monitoring
        monitoring = mommy.make(Monitoring, status=MONITORING_RATE)

        # AND organization
        organization = mommy.make(Organization, monitoring=monitoring)

        # AND superuser with Email address
        User.objects.create_superuser('admin1', 'admin@ya.ru', 'password')
        # AND superuser without Email address
        User.objects.create_superuser('admin2', None, 'password')
        # AND 2 expert B
        expertB1 = User.objects.create_user('expertB1', 'expertB1@ya.ru', 'password')
        expertB1.profile.is_expertB = True
        expertB2 = User.objects.create_user('expertB2', 'expertB2@ya.ru', 'password')
        expertB2.profile.is_expertB = True
        # AND expert A
        expertA = User.objects.create_user('expertA', 'expertA@ya.ru', 'password')
        expertA.profile.is_expertA = True
        # AND organization representative
        org_user = User.objects.create_user('org', 'org@ya.ru', 'password')
        mommy.make(OrgUser, organization=organization, userprofile=org_user.profile)

        # AND task for expertB1
        task = mommy.make(Task, organization=organization, user=expertB1)

        # AND score fot this task
        self.score = mommy.make(Score, task=task, parameter__monitoring=monitoring)

        # AND i logged in as expertA
        self.client.login(username='expertA', password='password')

        # NOTE: pop message about task assignment to expertB1
        # TODO: get rid of this automatic email on Task creation, move to the view
        mail.outbox.pop()

    def test_notification_on_create(self):
        url = reverse('exmo2010:clarification_create', args=[self.score.pk])

        # WHEN i post new clarification
        response = self.client.post(url, data={'clarification-comment': 'asd'}, follow=True)

        # THEN response status_code is 200 (OK)
        self.assertEqual(response.status_code, 200)

        # AND there should be 2 email messages in the outbox
        self.assertEqual(len(mail.outbox), 2)

        # AND both notifiee should get the email
        self.assertEqual(set(tuple(m.to) for m in mail.outbox), set([('expertB1@ya.ru',), ('expertA@ya.ru',)]))
