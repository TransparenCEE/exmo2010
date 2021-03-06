# -*- coding: utf-8 -*-
# This file is part of EXMO2010 software.
# Copyright 2013 Al Nikolov
# Copyright 2013-2014 Foundation "Institute for Information Freedom Development"
# Copyright 2014-2016 IRSI LTD
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

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from core.test_utils import TestCase
from mock import MagicMock, Mock
from model_mommy import mommy
from nose_parameterized import parameterized

from .views import TaskHistoryView
from core.test_utils import OptimizedTestCase
from exmo2010.models import (
    Monitoring, ObserversGroup, Organization, TaskHistory, Task, Score, OrgUser,
    Parameter, MONITORING_INTERACTION, MONITORING_RATE)


class TaskAssignSideEffectsTestCase(TestCase):
    # Scenario: when task is created/assigned SHOULD create TaskHistory
    # and notify expertB if he has email

    def setUp(self):
        # GIVEN INTERACTION monitoring without tasks
        self.monitoring = mommy.make(Monitoring, status=MONITORING_INTERACTION)
        self.monitoring_id = self.monitoring.pk
        # AND there is 2 organizations in this monitoring
        self.organization1 = mommy.make(Organization, monitoring=self.monitoring)
        self.organization2 = mommy.make(Organization, monitoring=self.monitoring)
        # AND i am logged-in as expert A
        usr = User.objects.create_user('expertA', 'expertA@svobodainfo.org', 'password')
        usr.profile.is_expertA = True
        self.client.login(username='expertA', password='password')
        # AND there is 2 active experts B
        self.expertB1 = User.objects.create_user('expertB1', 'expertB1@svobodainfo.org', 'password')
        self.expertB1.profile.is_expertB = True
        self.expertB2 = User.objects.create_user('expertB2', 'expertB1@svobodainfo.org', 'password')
        self.expertB2.profile.is_expertB = True
        # AND expert B account without email
        self.expertB3 = User.objects.create_user('expertB3', '', 'password')
        self.expertB3.profile.is_expertB = True

    def test_mass_assign_tasks(self):
        # WHEN I mass-asign Tasks for 2 organizations to 1 user
        url = reverse('exmo2010:mass_assign_tasks', args=[self.monitoring_id])
        self.client.post(url, {
            'organizations': [self.organization1.pk, self.organization2.pk],
            'expert': self.expertB1.pk,
        })

        # THEN there should be 2 Tasks for user
        self.assertEqual(Task.objects.count(), 2)
        # AND Every Task should have corresponding TaskHistory
        self.assertEqual(TaskHistory.objects.count(), 2)
        # AND expertB should receive 2 Email notifications about her new assigned Tasks
        self.assertEqual(len(mail.outbox), 2)

    def test_add_single_task(self):
        # WHEN I create new task
        url = reverse('exmo2010:task_add', args=[self.monitoring_id])
        response = self.client.post(url, {
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

    def test_assign_with_empty_email(self):
        # WHEN I get task add page
        url = reverse('exmo2010:task_add', args=[self.monitoring.pk])
        # AND I post task add form with user assigned to expert B
        data = {
            'organization': self.organization1.pk,
            'user': self.expertB3.pk,
        }
        response = self.client.post(url, data=data, follow=True)

        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)
        # AND assigned expert B user of this task should get changed to expertB in database
        self.assertEqual(self.expertB3.pk, Task.objects.all().get().user.pk)
        # AND expert B shouldn't receive Email notification about her new assigned Task
        self.assertEqual(len(mail.outbox), 0)


class ExpertBTaskAjaxActionsTestCase(TestCase):
    # Should allow expertB to close and open only own Tasks using ajax actions

    def setUp(self):
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
        response = self.client.post(url)
        # THEN response status_code should be 403 (forbidden)
        self.assertEqual(response.status_code, 403)

    def test_allow_close_complete_task_action(self):
        # WHEN I try to close opened Task that is assigned to me and have complete score
        url = reverse('exmo2010:ajax_task_close', args=[self.complete_task_b1.pk])
        response = self.client.post(url)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)
        # AND new status_display "ready" should be in the ajax response
        response = json.loads(response.content)
        ready_status_display = dict(Task.TASK_STATUS).get(Task.TASK_READY)
        self.assertEqual(response['status_display'], ready_status_display)
        # AND new permitted actions should be in the ajax response ('open_task', 'view_task', 'view_openness')
        self.assertEqual(set(['open_task', 'view_task', 'view_openness']), set(response['perms'].split()))

    def test_forbid_close_incomplete_task_action(self):
        # WHEN I try to close opened Task that is assigned to me but does not have complete score
        url = reverse('exmo2010:ajax_task_close', args=[self.incomplete_task_b1.pk])
        response = self.client.post(url)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)
        # AND ajax response status_display should be same old status "open" plus error message
        response = json.loads(response.content)
        open_status_display = dict(Task.TASK_STATUS).get(Task.TASK_OPEN)
        res_pattern = re.compile(r'^%s \[.+\]$' % unicode(open_status_display))
        self.assertTrue(res_pattern.match(response['status_display']))
        # AND ajax response permitted actions should be same as before ('close_task', 'fill_task', 'view_task', 'view_openness')
        self.assertEqual(set(['close_task', 'fill_task', 'view_task', 'view_openness']), set(response['perms'].split()))

    def test_allow_open_closed_task_action(self):
        # WHEN I try to open closed Task that is assigned to me
        url = reverse('exmo2010:ajax_task_open', args=[self.closed_task_b1.pk])
        response = self.client.post(url)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)
        # AND new status_display "open" should be in the ajax response
        response = json.loads(response.content)
        open_status_display = dict(Task.TASK_STATUS).get(Task.TASK_OPEN)
        self.assertEqual(response['status_display'], open_status_display)
        # AND new permitted actions should be in the ajax response ('close_task', 'fill_task', 'view_task', 'view_openness')
        self.assertEqual(set(['close_task', 'fill_task', 'view_task', 'view_openness']), set(response['perms'].split()))

    def test_forbid_open_approved_task_action(self):
        # WHEN I try to open approved Task that is assigned to me
        url = reverse('exmo2010:ajax_task_open', args=[self.approved_task_b1.pk])
        response = self.client.post(url)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)
        # AND ajax response status_display should be same old status "approved"
        response = json.loads(response.content)
        approved_status_display = dict(Task.TASK_STATUS).get(Task.TASK_APPROVED)
        self.assertEqual(response['status_display'], approved_status_display)
        # AND ajax response permitted actions should be same as before ('view_task', 'view_openness')
        self.assertEqual(set(['view_task', 'view_openness']), set(response['perms'].split()))


class ExpertATaskAjaxActionsTestCase(TestCase):
    # Should allow expertA to approve closed complete tasks using ajax actions.
    # And allow to reopen approved tasks.
    # And forbid to approve opened task.

    def setUp(self):
        # GIVEN MONITORING_RATE monitoring
        monitoring = mommy.make(Monitoring, status=MONITORING_RATE)

        # AND parameter with only 'accessible' attribute
        parameter = mommy.make(
            Parameter, monitoring=monitoring, accessible=True,
            complete=False, topical=False, hypertext=False, document=False, image=False)

        # AND opened task
        self.open_task = mommy.make(Task, organization__monitoring=monitoring, status=Task.TASK_OPEN)

        # AND approved task
        self.approved_task = mommy.make(Task, organization__monitoring=monitoring, status=Task.TASK_APPROVED)

        # AND closed task which have complete score
        self.closed_complete_task = mommy.make(Task, organization__monitoring=monitoring, status=Task.TASK_OPEN)
        mommy.make(Score, task=self.closed_complete_task, parameter=parameter, found=1, accessible=1)

        # AND i am logged-in as expertA
        self.expertA = User.objects.create_user('expertA', 'usr1@svobodainfo.org', 'password')
        self.expertA.profile.is_expertA = True
        self.client.login(username='expertA', password='password')

    def test_allow_open_approved_task_action(self):
        # WHEN I try to reopen approved Task
        response = self.client.post(reverse('exmo2010:ajax_task_open', args=[self.approved_task.pk]))

        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)

        # AND new status_display "open" should be in the ajax response
        response = json.loads(response.content)
        open_status_display = dict(Task.TASK_STATUS).get(Task.TASK_OPEN)
        self.assertEqual(response['status_display'], unicode(open_status_display))

        # AND new permitted actions should be in the ajax response
        # ('close_task', 'fill_task', 'view_task', 'view_openness', 'view_comments')
        expected_perms = ['close_task', 'fill_task', 'view_task', 'view_openness', 'view_comments']
        self.assertEqual(set(expected_perms), set(response['perms'].split()))

    def test_allow_approve_complete_task_action(self):
        # WHEN I try to approve closed complete Task
        response = self.client.post(reverse('exmo2010:ajax_task_approve', args=[self.closed_complete_task.pk]))

        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)

        # AND new status_display "approved" should be in the ajax response
        response = json.loads(response.content)
        approved_status_display = dict(Task.TASK_STATUS).get(Task.TASK_APPROVED)
        self.assertEqual(response['status_display'], unicode(approved_status_display))

        # AND new permitted actions should be in the ajax response
        # ('open_task', 'fill_task', 'view_task', 'view_openness', 'view_comments')
        expected_perms = ['open_task', 'fill_task', 'view_task', 'view_openness', 'view_comments']
        self.assertEqual(set(expected_perms), set(response['perms'].split()))

    def test_forbid_approve_open_task_action(self):
        # WHEN I try to approve opened Task
        response = self.client.post(reverse('exmo2010:ajax_task_approve', args=[self.open_task.pk]))

        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)

        # AND ajax response status_display should be same old status "open" plus error message
        response = json.loads(response.content)
        open_status_display = dict(Task.TASK_STATUS).get(Task.TASK_OPEN)
        res_pattern = re.compile(r'^%s \[.+\]$' % unicode(open_status_display))
        self.assertTrue(res_pattern.match(response['status_display']))

        # AND ajax response  permitted actions should be same as before
        # ('close_task', 'fill_task', 'view_task', 'view_openness', 'view_comments')
        expected_perms = ['close_task', 'fill_task', 'view_task', 'view_openness', 'view_comments']
        self.assertEqual(set(expected_perms), set(response['perms'].split()))


class TaskDeletionTestCase(TestCase):
    # SHOULD delete Task after expertA confirmation on deletion page

    def setUp(self):
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
    # exmo2010:task_update

    # SHOULD update Task after expertA edits it on edit page

    def setUp(self):
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


class ReassignTaskTestCase(TestCase):
    # Scenario: SHOULD allow only expertA to reassign task

    def setUp(self):
        # GIVEN two experts B
        self.expertB_1 = User.objects.create_user('expertB_1', 'expertB_1@svobodainfo.org', 'password')
        self.expertB_1.profile.is_expertB = True
        self.expertB_2 = User.objects.create_user('expertB_2', 'expertB_2@svobodainfo.org', 'password')
        self.expertB_2.profile.is_expertB = True
        # AND interaction monitoring
        self.monitoring = mommy.make(Monitoring, status=MONITORING_INTERACTION)
        # AND organization in this monitoring
        self.organization = mommy.make(Organization, monitoring=self.monitoring)
        # AND opened task
        self.task = mommy.make(Task, organization=self.organization, user=self.expertB_1, status=Task.TASK_OPEN)

    def test_reassign_task(self):
        # WHEN I am logged-in as expertB_1
        self.client.login(username='expertB_1', password='password')
        # AND submit task update form
        url = reverse('exmo2010:task_update', args=[self.task.pk])
        data = {
            'organization': self.organization.pk,
            'status': Task.TASK_OPEN,
            'user': self.expertB_2.pk,
        }
        response = self.client.post(url, data)
        # THEN response status_code should be 403 (Forbidden)
        self.assertEqual(response.status_code, 403)
        # AND task should stay assigned to expertB_1
        task = Task.objects.get(pk=self.task.pk)
        self.assertEqual(task.user.username, self.expertB_1.username)


class TaskListAccessTestCase(TestCase):
    # exmo2010:tasks_by_monitoring

    # SHOULD forbid access to monitoring tasks list page for non-experts or expertB without
    # tasks in the monitoring.
    # AND allow expertA see all tasks, expertB - see only assigned tasks

    def setUp(self):
        # GIVEN INTERACTION monitoring
        monitoring = mommy.make(Monitoring, status=MONITORING_INTERACTION)
        # AND there is 2 organizations in this monitoring
        org1 = mommy.make(Organization, monitoring=monitoring)
        org2 = mommy.make(Organization, monitoring=monitoring)
        # AND expertA
        expertA = User.objects.create_user('expertA', 'usr@svobodainfo.org', 'password')
        expertA.profile.is_expertA = True

        # AND expertB without tasks (expertB_free)
        expertB_free = User.objects.create_user('expertB_free', 'usr@svobodainfo.org', 'password')
        expertB_free.profile.is_expertB = True

        # AND 2 expertB with task in this Monitoring
        expertB_engaged1 = User.objects.create_user('expertB_engaged1', 'usr@svobodainfo.org', 'password')
        expertB_engaged1.profile.is_expertB = True
        self.task1 = mommy.make(Task, organization=org1, user=expertB_engaged1)

        expertB_engaged2 = User.objects.create_user('expertB_engaged2', 'usr@svobodainfo.org', 'password')
        expertB_engaged2.profile.is_expertB = True
        mommy.make(Task, organization=org2, user=expertB_engaged2)

        # AND org repersentative, with Organization from this monitoring
        org_user = User.objects.create_user('org_user', 'usr@svobodainfo.org', 'password')
        mommy.make(OrgUser, organization=org1, userprofile=org_user.profile)

        # AND just registered user
        user = User.objects.create_user('user', 'usr@svobodainfo.org', 'password')

        self.url = reverse('exmo2010:tasks_by_monitoring', args=[monitoring.pk])

    @parameterized.expand([
        ('org_user',),
        ('user',),
        ('expertB_free',),
    ])
    def test_forbid_unrelated_user_access_task_list(self, username):
        # WHEN i log in as unrelated user
        self.client.login(username=username, password='password')

        # AND i request task list page
        response = self.client.get(self.url)

        # THEN response status_code is 403
        self.assertEqual(response.status_code, 403)

    def test_redirect_anonymous_to_login(self):
        # WHEN AnonymousUser request task list page
        response = self.client.get(self.url, follow=True)
        # THEN response redirects to login page
        self.assertRedirects(response, settings.LOGIN_URL + '?next=' + self.url)

    def test_allow_expertA_see_full_task_list(self):
        # WHEN i log in as expertA
        self.client.login(username='expertA', password='password')

        # AND i request task list page
        response = self.client.get(self.url)

        # THEN response context contains 2 tasks in the list
        self.assertEqual(len(response.context['object_list']), 2)

    def test_allow_expertB_see_only_assigned_task_list(self):
        # WHEN i log in as expertB (with a task in this Monitoring)
        self.client.login(username='expertB_engaged1', password='password')

        # AND i request task list page
        response = self.client.get(self.url)

        # THEN response context contains list of only 1 task, and it is assigned to me
        pks = [task.pk for task in response.context['object_list']]
        self.assertEqual(pks, [self.task1.pk])


class TaskCompletenessTestCase(TestCase):
    # SHOULD calculate completeness

    def setUp(self):
        # GIVEN monitoring
        self.monitoring = mommy.make(Monitoring)
        # AND parameter with only 'accessible' attribute
        self.parameter = mommy.make(
            Parameter, monitoring=self.monitoring, accessible=True,
            complete=False, topical=False, hypertext=False, document=False, image=False)
        # AND task which have 100% complete score ('found' and 'accessible' are non-null)
        self.task = mommy.make(Task, organization__monitoring=self.monitoring)
        mommy.make(Score, task=self.task, parameter=self.parameter, found=1, accessible=1)
        # AND parameter edit page url
        self.url = reverse('exmo2010:parameter_update', args=[self.task.pk, self.parameter.pk])
        # AND expert A account
        expertA = User.objects.create_user('expertA', 'usr1@svobodainfo.org', 'password')
        expertA.profile.is_expertA = True
        # AND I am logged-in as expert A
        self.client.login(username='expertA', password='password')

    def test_add_new_criterion_and_delete_it(self):
        # WHEN I check task completeness
        # THEN task completeness should be 100%
        self.assertEqual(self.task.completeness, 100)

        # WHEN I add 'topical' criterion to parameter
        data = self.parameter.__dict__
        data['monitoring'] = self.monitoring.pk
        data['topical'] = True
        response = self.client.post(self.url, data, follow=True)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)
        # AND task completeness should be 0%
        self.assertEqual(self.task.completeness, 0)

        # WHEN I delete 'topical' criterion without score changing
        data['topical'] = False
        response = self.client.post(self.url, data, follow=True)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)
        # AND task completeness should be 100%, because all currently relevant criteria was initially rated
        self.assertEqual(self.task.completeness, 100)

    def test_delete_criterion_and_add_it(self):
        # WHEN I check task completeness
        # THEN task completeness should be 100%
        self.assertEqual(self.task.completeness, 100)

        # WHEN I delete 'accessible' criterion
        data = self.parameter.__dict__
        data['monitoring'] = self.monitoring.pk
        data['accessible'] = False
        response = self.client.post(self.url, data, follow=True)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)
        # AND task completeness should be 100%
        self.assertEqual(self.task.completeness, 100)

        # WHEN I add 'accessible' criterion to parameter
        data['accessible'] = True
        response = self.client.post(self.url, data, follow=True)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)
        # AND task completeness should be 100%, because 'accessible' criterion was initially rated
        self.assertEqual(self.task.completeness, 100)


class TaskHistoryAccessTestCase(OptimizedTestCase):
    # exmo2010:task_history

    # Should always redirect anonymous to login page.
    # Should forbid all post requests.
    # Should allow to get page admin and expert A only.

    @classmethod
    def setUpClass(cls):
        super(TaskHistoryAccessTestCase, cls).setUpClass()

        cls.users = {}
        # GIVEN monitoring with organization and task
        cls.monitoring = mommy.make(Monitoring)
        organization = mommy.make(Organization, monitoring=cls.monitoring)
        cls.task = mommy.make(Task, organization__monitoring=cls.monitoring)
        # AND anonymous user
        cls.users['anonymous'] = AnonymousUser()
        # AND user without any permissions
        cls.users['user'] = User.objects.create_user('user', 'usr@svobodainfo.org', 'password')
        # AND superuser
        cls.users['admin'] = User.objects.create_superuser('admin', 'usr@svobodainfo.org', 'password')
        # AND expert B
        expertB = User.objects.create_user('expertB', 'usr@svobodainfo.org', 'password')
        expertB.profile.is_expertB = True
        cls.users['expertB'] = expertB
        # AND expert A
        expertA = User.objects.create_user('expertA', 'usr@svobodainfo.org', 'password')
        expertA.profile.is_expertA = True
        cls.users['expertA'] = expertA
        # AND organization representative
        orguser = User.objects.create_user('orguser', 'usr@svobodainfo.org', 'password')
        mommy.make(OrgUser, organization=organization, userprofile=orguser.profile)
        cls.users['orguser'] = orguser
        # AND translator
        translator = User.objects.create_user('translator', 'usr@svobodainfo.org', 'password')
        translator.profile.is_translator = True
        cls.users['translator'] = translator
        # AND observer user
        observer = User.objects.create_user('observer', 'usr@svobodainfo.org', 'password')
        # AND observers group for monitoring
        obs_group = mommy.make(ObserversGroup, monitoring=cls.monitoring)
        obs_group.organizations = [organization]
        obs_group.users = [observer]
        cls.users['observer'] = observer
        # AND page url
        cls.url = reverse('exmo2010:task_history', args=[cls.task.id])

    @parameterized.expand(zip(['GET', 'POST']))
    def test_redirect_anonymous(self, method, *args):
        # WHEN anonymous user send request to history page
        request = MagicMock(user=self.users['anonymous'], method=method)
        request.get_full_path.return_value = self.url
        response = TaskHistoryView.as_view()(request, task_pk=self.task.id)
        # THEN response status_code should be 302 (redirect)
        self.assertEqual(response.status_code, 302)
        # AND response redirects to login page
        self.assertEqual(response['Location'], '{}?next={}'.format(settings.LOGIN_URL, self.url))

    @parameterized.expand(zip(['expertB', 'orguser', 'translator', 'observer', 'user']))
    def test_forbid_get(self, username, *args):
        # WHEN authenticated user get history page
        request = Mock(user=self.users[username], method='GET')
        # THEN response should raise PermissionDenied exception
        self.assertRaises(PermissionDenied, TaskHistoryView.as_view(), request, self.task.id)

    @parameterized.expand(zip(['admin', 'expertA']))
    def test_allow_get(self, username, *args):
        # WHEN admin or expert A get history page
        request = Mock(user=self.users[username], method='GET')
        response = TaskHistoryView.as_view()(request, task_pk=self.task.id)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)

    @parameterized.expand(zip(['admin', 'expertA', 'expertB', 'orguser', 'translator', 'observer', 'user']))
    def test_forbid_post(self, username, *args):
        # WHEN authenticated user post to history page
        request = Mock(user=self.users[username], method='POST')
        response = TaskHistoryView.as_view()(request, task_pk=self.task.id)
        # THEN response status_code should be 405 (method not allowed)
        self.assertEqual(response.status_code, 405)
