# -*- coding: utf-8 -*-
# This file is part of EXMO2010 software.
# Copyright 2013 Al Nikolov
# Copyright 2013 Foundation "Institute for Information Freedom Development"
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

import json
import re

from django.core import mail
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.client import Client
from model_mommy import mommy

from exmo2010.models import (
    Monitoring, User, Organization, TaskHistory, Task, Score,
    Parameter, MONITORING_INTERACTION, MONITORING_RATE)


class TaskAssignSideEffectsTestCase(TestCase):
    # Scenario: Should notify user and create TaskHistory on Task creation/assign

    def setUp(self):
        self.client = Client()
        # GIVEN INTERACTION monitoring without tasks
        self.monitoring = mommy.make(Monitoring, status=MONITORING_INTERACTION)
        self.monitoring_id = self.monitoring.pk
        # AND there is 2 organizations in this monitoring
        self.organization1 = mommy.make(Organization, monitoring=self.monitoring)
        self.organization2 = mommy.make(Organization, monitoring=self.monitoring)
        # AND i am logged-in as expertA
        usr = User.objects.create_user('expA', 'usr@svobodainfo.org', 'password')
        usr.profile.is_expertA = True
        self.client.login(username='expA', password='password')
        # AND there is 2 active expertsB
        self.expertB1 = mommy.make_recipe('exmo2010.active_user')
        self.expertB1.profile.is_expertB = True
        self.expertB2 = mommy.make_recipe('exmo2010.active_user')
        self.expertB2.profile.is_expertB = True

    def test_mass_assign_tasks(self):
        # WHEN I mass-asign Tasks for 2 organizations to 2 users
        url = reverse('exmo2010:task_mass_assign_tasks', args=[self.monitoring_id])
        self.client.post(
            url,
            {
                'organizations': [self.organization1.pk, self.organization2.pk],
                'users': [self.expertB1.pk, self.expertB2.pk]
            })

        # THEN there should be 2x2 Tasks for each user/org pair
        self.assertEqual(Task.objects.count(), 4)
        # AND Every Task should have corresponding TaskHistory
        self.assertEqual(TaskHistory.objects.count(), 4)
        # AND Every expertB should receive 2 Email notifications about her new assigned Tasks
        self.assertEqual(len(mail.outbox), 4)

    def test_add_single_task(self):
        # WHEN I create new task
        url = reverse('exmo2010:task_add', args=[self.monitoring_id])
        res = self.client.post(url, {
            'organization': self.organization1.pk,
            'user': self.expertB1.pk,
            'status': Task.TASK_OPEN
        })

        # THEN There should be one Task and one TaskHistory
        self.assertEqual(Task.objects.count(), 1)
        self.assertEqual(TaskHistory.objects.count(), 1)
        # AND TaskHistory should have correct params for Task
        task = Task.objects.all()[0]
        history = TaskHistory.objects.all()[0]
        self.assertEqual(history.task_id, task.pk)
        self.assertEqual(history.user, task.user)
        self.assertEqual(history.status, task.organization.monitoring.status)
        # AND expertB should receive Email notification about her new assigned Task
        self.assertEqual(len(mail.outbox), 1)


class ExpertBTaskAjaxActionsTestCase(TestCase):
    # Should allow expertB to close and open only own Tasks using ajax actions

    def setUp(self):
        self.client = Client()
        # GIVEN MONITORING_RATE monitoring
        self.monitoring = mommy.make(Monitoring, status=MONITORING_RATE)
        # AND there are 4 organizations in this monitoring (for every task)
        organization1 = mommy.make(Organization, monitoring=self.monitoring)
        organization2 = mommy.make(Organization, monitoring=self.monitoring)
        organization3 = mommy.make(Organization, monitoring=self.monitoring)
        organization4 = mommy.make(Organization, monitoring=self.monitoring)
        # AND one parameter with only 'accessible' attribute
        parameter = mommy.make(
            Parameter,
            monitoring = self.monitoring,
            complete = False,
            accessible = True,
            topical = False,
            hypertext = False,
            document = False,
            image = False,
            npa = False
        )
        # AND i am logged-in as expertB_1
        self.expertB_1 = User.objects.create_user('expertB_1', 'usr@svobodainfo.org', 'password')
        self.expertB_1.profile.is_expertB = True
        self.client.login(username='expertB_1', password='password')
        # AND there is an open task assigned to me (expertB_1), which have no score (incomplete)
        self.incomplete_task_b1 = mommy.make(
            Task,
            organization=organization1,
            status=Task.TASK_OPEN,
            user=self.expertB_1
        )
        # AND there is an open task assigned to me (expertB_1), which have complete score
        self.complete_task_b1 = mommy.make(
            Task,
            organization=organization2,
            status=Task.TASK_OPEN,
            user=self.expertB_1
        )
        score = mommy.make(Score, task=self.complete_task_b1, parameter=parameter, found=1, accessible=1)

        # AND there is a closed task assigned to me (expertB_1)
        self.closed_task_b1 = mommy.make(
            Task,
            organization=organization3,
            status=Task.TASK_CLOSED,
            user=self.expertB_1
        )

        # AND there is approved task assigned to me (expertB_1)
        self.approved_task_b1 = mommy.make(
            Task,
            organization=organization4,
            status=Task.TASK_APPROVED,
            user=self.expertB_1
        )

        # AND there is another expertB with assigned open task
        self.expertB2 = mommy.make_recipe('exmo2010.active_user')
        self.expertB2.profile.is_expertB = True
        self.task_b2 = mommy.make(Task, organization=organization1, status=Task.TASK_OPEN, user=self.expertB2)

    def test_forbid_unowned_tasks_actions(self):
        # WHEN I try to close Task that is not assigned to me
        url = reverse('exmo2010:ajax_task_open', args=[self.task_b2.pk])
        res = self.client.post(url)
        # THEN response status_code should be 403 (forbidden)
        self.assertEqual(res.status_code, 403)

    def test_allow_close_complete_task_action(self):
        # WHEN I try to close opened Task that is assigned to me and have complete score
        url = reverse('exmo2010:ajax_task_close', args=[self.complete_task_b1.pk])
        res = self.client.post(url)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(res.status_code, 200)
        # AND new status_display "ready" should be in the ajax response
        res = json.loads(res.content)
        ready_status_display = dict(Task.TASK_STATUS).get(Task.TASK_READY)
        self.assertEqual(res['status_display'], ready_status_display)
        # AND new permitted actions should be in the ajax response ('open_task', 'view_task')
        self.assertEqual(set(['open_task', 'view_task']), set(res['perms'].split()))

    def test_forbid_close_incomplete_task_action(self):
        # WHEN I try to close opened Task that is assigned to me but does not have complete score
        url = reverse('exmo2010:ajax_task_close', args=[self.incomplete_task_b1.pk])
        res = self.client.post(url)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(res.status_code, 200)
        # AND ajax response status_display should be same old status "open" plus error message
        res = json.loads(res.content)
        open_status_display = dict(Task.TASK_STATUS).get(Task.TASK_OPEN)
        res_pattern = re.compile(r'^%s \[.+\]$' % open_status_display)
        self.assertTrue(res_pattern.match(res['status_display']))
        # AND ajax response permitted actions should be same as before ('close_task', 'fill_task', 'view_task')
        self.assertEqual(set(['close_task', 'fill_task', 'view_task']), set(res['perms'].split()))

    def test_allow_open_closed_task_action(self):
        # WHEN I try to open closed Task that is assigned to me
        url = reverse('exmo2010:ajax_task_open', args=[self.closed_task_b1.pk])
        res = self.client.post(url)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(res.status_code, 200)
        # AND new status_display "open" should be in the ajax response
        res = json.loads(res.content)
        open_status_display = dict(Task.TASK_STATUS).get(Task.TASK_OPEN)
        self.assertEqual(res['status_display'], open_status_display)
        # AND new permitted actions should be in the ajax response ('close_task', 'fill_task', 'view_task')
        self.assertEqual(set(['close_task', 'fill_task', 'view_task']), set(res['perms'].split()))

    def test_forbid_open_approved_task_action(self):
        # WHEN I try to open approved Task that is assigned to me
        url = reverse('exmo2010:ajax_task_open', args=[self.approved_task_b1.pk])
        res = self.client.post(url)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(res.status_code, 200)
        # AND ajax response status_display should be same old status "approved"
        res = json.loads(res.content)
        approved_status_display = dict(Task.TASK_STATUS).get(Task.TASK_APPROVED)
        self.assertEqual(res['status_display'], approved_status_display)
        # AND ajax response permitted actions should be same as before ('view_task')
        self.assertEqual('view_task', res['perms'])


class ExpertATaskAjaxActionsTestCase(TestCase):
    # Should allow expertA to approve and reopen Tasks using ajax actions

    def setUp(self):
        self.client = Client()
        # GIVEN MONITORING_RATE monitoring
        self.monitoring = mommy.make(Monitoring, status=MONITORING_RATE)
        # AND there are 3 organizations in this monitoring (for every task)
        organization1 = mommy.make(Organization, monitoring=self.monitoring)
        organization2 = mommy.make(Organization, monitoring=self.monitoring)
        organization3 = mommy.make(Organization, monitoring=self.monitoring)
        # AND one parameter with only 'accessible' attribute
        parameter = mommy.make(
            Parameter,
            monitoring = self.monitoring,
            complete = False,
            accessible = True,
            topical = False,
            hypertext = False,
            document = False,
            image = False,
            npa = False
        )
        # AND i am logged-in as expertA
        self.expertA = User.objects.create_user('expertA', 'usr1@svobodainfo.org', 'password')
        self.expertA.profile.is_expertA = True
        self.client.login(username='expertA', password='password')

        # AND expertB account
        self.expertB = User.objects.create_user('expertB', 'usr2@svobodainfo.org', 'password')
        self.expertB.profile.is_expertB = True

        # AND there is an open task assigned to expertB
        self.open_task = mommy.make(
            Task,
            organization=organization1,
            status=Task.TASK_OPEN,
            user=self.expertB
        )

        # AND there is closed task assigned to expertB, which have complete score
        self.closed_complete_task = mommy.make(
            Task,
            organization=organization2,
            status=Task.TASK_OPEN,
            user=self.expertB
        )
        score = mommy.make(Score, task=self.closed_complete_task, parameter=parameter, found=1, accessible=1)

        # AND there is approved task assigned to expertB
        self.approved_task = mommy.make(
            Task,
            organization=organization3,
            status=Task.TASK_APPROVED,
            user=self.expertB
        )

    def test_allow_open_approved_task_action(self):
        # WHEN I try to reopen approved Task
        url = reverse('exmo2010:ajax_task_open', args=[self.approved_task.pk])
        res = self.client.post(url)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(res.status_code, 200)
        # AND new status_display "open" should be in the ajax response
        res = json.loads(res.content)
        open_status_display = dict(Task.TASK_STATUS).get(Task.TASK_OPEN)
        self.assertEqual(res['status_display'], open_status_display)
        # AND new permitted actions should be in the ajax response ('close_task', 'fill_task', 'view_task')
        self.assertEqual(set(['close_task', 'fill_task', 'view_task']), set(res['perms'].split()))

    def test_allow_approve_complete_task_action(self):
        # WHEN I try to approve closed complete Task
        url = reverse('exmo2010:ajax_task_approve', args=[self.closed_complete_task.pk])
        res = self.client.post(url)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(res.status_code, 200)
        # AND new status_display "approved" should be in the ajax response
        res = json.loads(res.content)
        approved_status_display = dict(Task.TASK_STATUS).get(Task.TASK_APPROVED)
        self.assertEqual(res['status_display'], approved_status_display)
        # AND new permitted actions should be in the ajax response ('open_task', 'fill_task', 'view_task')
        self.assertEqual(set(['open_task', 'fill_task', 'view_task']), set(res['perms'].split()))

    def test_forbid_approve_open_task_action(self):
        # WHEN I try to approve opened Task
        url = reverse('exmo2010:ajax_task_approve', args=[self.open_task.pk])
        res = self.client.post(url)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(res.status_code, 200)
        # AND ajax response status_display should be same old status "open" plus error message
        res = json.loads(res.content)
        open_status_display = dict(Task.TASK_STATUS).get(Task.TASK_OPEN)
        res_pattern = re.compile(r'^%s \[.+\]$' % open_status_display)
        self.assertTrue(res_pattern.match(res['status_display']))
        # AND ajax response  permitted actions should be same as before ('close_task', 'fill_task', 'view_task')
        self.assertEqual(set(['close_task', 'fill_task', 'view_task']), set(res['perms'].split()))


class TaskDeletionTestCase(TestCase):
    # SHOULD delete Task after expertA confirmation on deletion page

    def setUp(self):
        self.client = Client()
        # GIVEN monitoring with organization
        self.monitoring = mommy.make(Monitoring)
        organization = mommy.make(Organization, monitoring=self.monitoring)
        # AND there is a task for this organization
        self.task = mommy.make(Task, organization=organization)

        # AND i am logged-in as expertA
        expertA = User.objects.create_user('expertA', 'usr1@svobodainfo.org', 'password')
        expertA.profile.is_expertA = True
        self.client.login(username='expertA', password='password')

    def test_delete_task(self):
        # WHEN I post task deletion confirmation
        url = reverse('exmo2010:task_delete', args=[self.task.pk])
        response = self.client.post(url, follow=True)

        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)

        # AND task should get deleted from database
        self.assertEqual(0, Task.objects.filter(pk=self.task.pk).count())


class TaskEditTestCase(TestCase):
    # SHOULD update Task after expertA edits it on edit page

    def setUp(self):
        self.client = Client()
        # GIVEN 2 expertB accounts
        self.expertB1 = User.objects.create_user('expertB1', 'expertB1@svobodainfo.org', 'password')
        self.expertB1.profile.is_expertB = True
        self.expertB2 = User.objects.create_user('expertB2', 'expertB2@svobodainfo.org', 'password')
        self.expertB2.profile.is_expertB = True

        # AND monitoring with organization
        self.monitoring = mommy.make(Monitoring)
        organization = mommy.make(Organization, monitoring=self.monitoring)
        # AND task for this organization assigned to expertB1
        self.task = mommy.make(Task, organization=organization, user=self.expertB1)

        # AND i am logged-in as expertA
        expertA = User.objects.create_user('expertA', 'usr1@svobodainfo.org', 'password')
        expertA.profile.is_expertA = True
        self.client.login(username='expertA', password='password')

    def test_update_task(self):
        # WHEN I get task edit page
        url = reverse('exmo2010:task_update', args=[self.task.pk])
        response = self.client.get(url)

        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)

        # WHEN I post task edit form with user changed to expertB2
        formdata = dict(response.context['form'].initial, user=self.expertB2.pk)
        response = self.client.post(url, follow=True, data=formdata)

        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)

        # AND assigned expertB user of this task should get changed to expertB2 in database
        self.assertEqual(self.expertB2.pk, Task.objects.filter(pk=self.task.pk).get().user.pk)
