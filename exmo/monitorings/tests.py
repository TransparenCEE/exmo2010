# -*- coding: utf-8 -*-
# This file is part of EXMO2010 software.
# Copyright 2013 Foundation "Institute for Information Freedom Development"
# Copyright 2013 Al Nikolov
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
from cStringIO import StringIO

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.client import Client
from django.utils import simplejson
from django.utils.translation import ungettext
from model_mommy import mommy
from nose_parameterized import parameterized

from core.utils import UnicodeReader
from custom_comments.models import CommentExmo
from exmo2010.models import *
from monitorings.views import rating, _total_orgs_translate


class RatingsTableValuesTestCase(TestCase):
    # Scenario: Output to Ratings Table
    def setUp(self):
        # GIVEN published monitoring
        self.client = Client()
        self.today = datetime.date.today()
        self.monitoring_name = "Name"
        monitoring = mommy.make(Monitoring, status=MONITORING_PUBLISHED,
                                name=self.monitoring_name,
                                publish_date=self.today)
        organization = mommy.make(Organization, monitoring=monitoring)
        task = mommy.make(Task, organization=organization, status=Task.TASK_APPROVED)
        parameter = mommy.make(Parameter, monitoring=monitoring)
        score = mommy.make(Score, task=task, parameter=parameter)

    def test_values(self):
        # WHEN user requests ratings page
        response = self.client.get(reverse('exmo2010:ratings'))
        monitoring = response.context['monitoring_list'][0]
        # THEN server returns "OK" response
        self.assertEqual(response.status_code, 200)
        # AND output data equals initial data
        self.assertEqual(monitoring.name, self.monitoring_name)
        self.assertEqual(monitoring.publish_date, self.today)
        self.assertEqual(monitoring.org_count, 1)
        # AND equals none because of absence of openness
        self.assertEqual(monitoring.average, None)


class RatingTableSettingsTestCase(TestCase):
    # Scenario: User settings for Rating Table columns
    def setUp(self):
        # GIVEN User and UserProfile model instances
        self.client = Client()
        self.usr = User.objects.create_user('usr', 'usr@svobodainfo.org', 'password')
        # AND published monitoring
        monitoring = mommy.make(Monitoring, status=MONITORING_PUBLISHED)
        self.monitoring_id = monitoring.pk
        organization = mommy.make(Organization, monitoring=monitoring)
        task = mommy.make(Task, organization=organization, status=Task.TASK_APPROVED)
        parameter = mommy.make(Parameter, monitoring=monitoring, weight=1)
        score = mommy.make(Score, task=task, parameter=parameter)

    def test_rt_settings_exist(self):
        # WHEN User instance is created
        # THEN visibility of "Representatives" column setting is True
        self.assertEqual(self.usr.profile.rt_representatives, True)
        # AND visibility of "Comments" column setting is True
        self.assertEqual(self.usr.profile.rt_comment_quantity, True)
        # AND visibility of "Initial" openness column setting is False
        self.assertEqual(self.usr.profile.rt_initial_openness, False)
        # AND visibility of "Openness" column setting is True
        self.assertEqual(self.usr.profile.rt_final_openness, True)
        # AND visibility of "Difference" column setting is True
        self.assertEqual(self.usr.profile.rt_difference, True)

    def test_rt_settings_change(self):
        # WHEN User logging in
        self.client.login(username='usr', password='password')
        # AND changes settings via web-interface
        url = reverse('exmo2010:monitoring_rating', args=[self.monitoring_id])
        self.client.get(url, {'initial_openness': 'on'})
        # THEN changes are stored in user's profile
        self.assertEqual(self.usr.profile.rt_representatives, False)
        self.assertEqual(self.usr.profile.rt_comment_quantity, False)
        self.assertEqual(self.usr.profile.rt_final_openness, False)
        self.assertEqual(self.usr.profile.rt_difference, False)


class RatingTableValuesTestCase(TestCase):
    # Scenario: Output to Rating Table
    def setUp(self):
        # GIVEN published monitoring
        self.client = Client()
        self.monitoring = mommy.make(Monitoring, status=MONITORING_PUBLISHED)
        self.monitoring_id = self.monitoring.pk
        self.url = reverse('exmo2010:monitoring_rating', args=[self.monitoring_id])
        organization = mommy.make(Organization, monitoring=self.monitoring)
        self.task = mommy.make(Task, organization=organization, status=Task.TASK_APPROVED)
        self.parameter = mommy.make(Parameter, monitoring=self.monitoring, weight=1)
        score = mommy.make(Score, task=self.task, parameter=self.parameter, found=0)

    def test_rt_row_output(self):
        # WHEN user requests rating page
        response = self.client.get(self.url)
        o = response.context['object_list'][0]
        # THEN output data equals default values for organization
        self.assertEqual(o, self.task)
        self.assertEqual(o.place, 1)
        self.assertEqual(o.repr_len, 0)
        self.assertEqual(o.active_repr_len, 0)
        self.assertEqual(o.comments, 0)
        self.assertEqual(o.openness, 0)
        self.assertEqual(o.openness_initial, 0)
        self.assertEqual(o.openness_delta, 0.0)

    def test_rt_average_output(self):
        # WHEN user requests rating page
        response = self.client.get(self.url)
        a = response.context['average']
        # THEN output average data equals expected values
        self.assertEqual(a['total_tasks'], 1)
        self.assertEqual(a['repr_len'], 0)
        self.assertEqual(a['active_repr_len'], 0)
        self.assertEqual(a['comments'], 0)
        self.assertEqual(a['openness'], 0)
        self.assertEqual(a['openness_initial'], 0)
        self.assertEqual(a['openness_delta'], 0.0)

    def test_organizations_count(self):
        # WHEN function accepts monitoring and parameters data
        rating_list, avg = rating(self.monitoring, [self.parameter])
        text = _total_orgs_translate(avg, rating_list, '')
        # THEN expected text and organization count exist in returned text
        expected_text = ungettext(
        'Altogether, there is %(count)d organization in the monitoring cycle',
        'Altogether, there are %(count)d organizations in the monitoring cycle',
        avg['total_tasks']
        ) % {'count': 1}
        self.assertTrue(expected_text in text)


class ActiveRepresentativesTestCase(TestCase):
    def setUp(self):
        # GIVEN User instance and two connected organizations to it
        self.client = Client()
        monitoring = mommy.make(Monitoring, status=MONITORING_PUBLISHED)
        monitoring_id = monitoring.pk
        organization1 = mommy.make(Organization, monitoring=monitoring)
        organization2 = mommy.make(Organization, monitoring=monitoring)
        self.url = reverse('exmo2010:monitoring_rating', args=[monitoring_id])
        self.usr = User.objects.create_user('usr', 'usr@svobodainfo.org', 'password')
        profile = self.usr.get_profile()
        profile.organization = [organization1, organization2]
        profile.save()
        # AND two corresponding tasks, parameters, and scores for organizations
        task1 = mommy.make(Task, organization=organization1, status=Task.TASK_APPROVED)
        task2 = mommy.make(Task, organization=organization2, status=Task.TASK_APPROVED)
        parameter1 = mommy.make(Parameter, monitoring=monitoring, weight=1)
        parameter2 = mommy.make(Parameter, monitoring=monitoring, weight=1)
        self.score1 = mommy.make(Score, task=task1, parameter=parameter1)
        self.score2 = mommy.make(Score, task=task2, parameter=parameter2)
        self.content_type = ContentType.objects.get_for_model(Score)
        self.site = Site.objects.get_current()

    def test_first_org_active_users(self):
        # WHEN representative adds a comment to first task's score
        comment = CommentExmo(content_type=self.content_type, object_pk=self.score1.pk, user=self.usr, site=self.site)
        comment.save()

        # AND requests rating page for monitoring
        response = self.client.get(self.url)
        o1 = response.context['object_list'][0]
        o2 = response.context['object_list'][1]

        # THEN representatives quantity for every organization equals 1
        self.assertEqual(o1.repr_len, 1)
        self.assertEqual(o2.repr_len, 1)

        # AND active representatives quantity for first organization equals 1 (because of comment)
        self.assertEqual(o1.active_repr_len, 1)

        # AND active representatives quantity for second organization equals 0 (because of absence of comment)
        self.assertEqual(o2.active_repr_len, 0)

    def test_second_org_active_users(self):
        # WHEN representative adds two comments to second task's score
        comment = CommentExmo(content_type=self.content_type, object_pk=self.score2.pk, user=self.usr, site=self.site)
        comment.save()
        comment = CommentExmo(content_type=self.content_type, object_pk=self.score2.pk, user=self.usr, site=self.site)
        comment.save()

        # AND requests rating page for monitoring
        response = self.client.get(self.url)
        o2 = response.context['object_list'][1]

        # THEN active representatives quantity for second organization equals 1
        self.assertEqual(o2.active_repr_len, 1)


class EmptyMonitoringTestCase(TestCase):
    def setUp(self):
        # GIVEN monitoring without tasks
        self.client = Client()
        self.monitoring = mommy.make(Monitoring, status=MONITORING_PUBLISHED)
        self.monitoring_id = self.monitoring.pk
        self.url = reverse('exmo2010:monitoring_rating', args=[self.monitoring_id])
        organization = mommy.make(Organization, monitoring=self.monitoring)
        # AND expertA account
        self.usr = User.objects.create_user('usr', 'usr@svobodainfo.org', 'password')
        self.usr.groups.add(Group.objects.get(name=self.usr.profile.expertA_group))

    def test_ok_response(self):
        self.client.login(username='usr', password='password')
        # WHEN expertA requests rating page
        response = self.client.get(self.url)
        # THEN server's response is OK
        self.assertEqual(response.status_code, 200)


class TestMonitoringExport(TestCase):
    # Scenario: Экспорт данных мониторинга
    def setUp(self):
        self.client = Client()
        # GIVEN предопределены все code OPENNESS_EXPRESSION
        for code in OpennessExpression.OPENNESS_EXPRESSIONS:
            # AND для каждого code есть опубликованный мониторинг
            monitoring = mommy.make(
                Monitoring,
                openness_expression__code=code,
                status=MONITORING_PUBLISHED)
            # AND в каждом мониторинге есть организация
            organization = mommy.make(Organization, monitoring=monitoring)
            # AND есть активный пользователь, не суперюзер, expert (см выше, этот - не эксперт, надо создать эксперта)
            expert = mommy.make_recipe('exmo2010.active_user')
            expert.profile.is_expertB = True
            # AND в каждой организации есть одобренная задача для expert
            task = mommy.make(
                Task,
                organization=organization,
                user=expert,
                status=Task.TASK_APPROVED,
            )
            # AND в каждом мониторинге есть параметр parameter с одним нерелевантным критерием
            parameter = mommy.make(
                Parameter,
                monitoring=monitoring,
                complete=False,
                weight=1,
            )
            # AND в каждой задаче есть оценка по parameter
            score = mommy.make(
                Score,
                task=task,
                parameter=parameter,
            )
            score = mommy.make(
                Score,
                task=task,
                parameter=parameter,
                revision=Score.REVISION_INTERACT,
            )

    def parameter_type(self, score):
        return 'npa' if score.parameter.npa else 'other'

    @parameterized.expand(
        [("expression-v%d" % code, code)
            for code in OpennessExpression.OPENNESS_EXPRESSIONS])
    def test_json(self, name, code):
        monitoring = Monitoring.objects.get(openness_expression__code=code)
        # WHEN анонимный пользователь запрашивает данные каждого мониторинга в json
        url = reverse('exmo2010:monitoring_export', args=[monitoring.pk])
        response = self.client.get(url + '?format=json')
        # THEN запрос удовлетворяется
        self.assertEqual(response.status_code, 200)
        # AND отдается json
        self.assertEqual(response.get('content-type'), 'application/json')
        json = simplejson.loads(response.content)
        organization = monitoring.organization_set.all()[0]
        task = organization.task_set.all()[0]
        score = task.score_set.filter(revision=Score.REVISION_DEFAULT,)[0]
        # AND имя мониторинга в БД и json совпадает
        self.assertEqual(json['monitoring']['name'], monitoring.name)
        # AND имя организации (для первой задачи) в БД и json совпадает
        self.assertEqual(
            json['monitoring']['tasks'][0]['name'],
            organization.name)
        # AND КИД (для первой задачи) в БД и json совпадает
        self.assertEqual(
            json['monitoring']['tasks'][0]['openness'],
            ('%.3f' % task.openness) if task.openness is not None else task.openness)
        self.assertEqual(
            int(json['monitoring']['tasks'][0]['position']),
            1)
        # AND балл найденности (в первой задаче, в оценке по первому параметру)
        # в БД и json совпадает
        self.assertEqual(
            int(json['monitoring']['tasks'][0]['scores'][0]['found']),
            int(score.found))
        self.assertEqual(
            json['monitoring']['tasks'][0]['scores'][0]['type'],
            self.parameter_type(score)
        )

    @parameterized.expand(
        [("expression-v%d" % code, code)
            for code in OpennessExpression.OPENNESS_EXPRESSIONS])
    def test_csv(self, name, code):
        monitoring = Monitoring.objects.get(openness_expression__code=code)
        # WHEN анонимный пользователь запрашивает данные каждого мониторинга в csv
        url = reverse('exmo2010:monitoring_export', args=[monitoring.pk])
        response = self.client.get(url + '?format=csv')
        # THEN запрос удовлетворяется
        self.assertEqual(response.status_code, 200)
        # AND отдается csv
        self.assertEqual(response.get('content-type'), 'application/vnd.ms-excel')
        csv = UnicodeReader(StringIO(response.content))
        organization = monitoring.organization_set.all()[0]
        task = organization.task_set.all()[0]
        row_count = 0
        for row in csv:
            row_count += 1
            self.assertEqual(len(row), 18)
            if row_count == 1:
                self.assertEqual(row[0], '#Monitoring')
                continue
            else:
                revision = row[17]
                self.assertIn(revision, Score.REVISION_EXPORT.values())
                for k, v in Score.REVISION_EXPORT.iteritems():
                    if v == revision:
                        revision = k
                        break
                score = task.score_set.filter(revision=revision)[0]
                # AND имя мониторинга в БД и json совпадает
                self.assertEqual(row[0], monitoring.name)
                # AND имя организации (для первой задачи) в БД и json совпадает
                self.assertEqual(
                    row[1],
                    organization.name)
                self.assertEqual(
                    int(row[2]),
                    organization.pk)
                self.assertEqual(
                    int(row[3]),
                    1)
                # AND КИД (для первой задачи) в БД и json совпадает
                self.assertEqual(
                    row[5],
                    '%.3f' % task.openness if task.openness is not None else '')
                self.assertEqual(
                    float(row[7]),
                    float(score.parameter.pk))
                # AND балл найденности (в первой задаче, в оценке по первому параметру)
                # в БД и json совпадает
                self.assertEqual(
                    int(row[8]),
                    int(score.found))
                self.assertEqual(
                    row[16],
                    self.parameter_type(score)
                )


class TestMonitoringExportApproved(TestCase):
    # Scenario: Экспорт данных мониторинга
    def setUp(self):
        self.client = Client()
        self.monitoring = mommy.make(
            Monitoring,
            pk=999,
            status=MONITORING_PUBLISHED)
        # AND в каждом мониторинге есть организация
        organization = mommy.make(Organization, monitoring=self.monitoring)
        # AND есть активный пользователь, не суперюзер, expert (см выше, этот - не эксперт, надо создать эксперта)
        expert1 = mommy.make_recipe('exmo2010.active_user')
        expert1.profile.is_expertB = True
        expert2 = mommy.make_recipe('exmo2010.active_user')
        expert2.profile.is_expertB = True
        # AND в каждой организации есть одобренная задача для expert
        task = mommy.make(
            Task,
            organization=organization,
            user=expert1,
            status=Task.TASK_APPROVED,
        )
        task = mommy.make(
            Task,
            organization=organization,
            user=expert2,
            status=Task.TASK_OPEN,
        )
        # AND в каждом мониторинге есть параметр parameter с одним нерелевантным критерием
        parameter = mommy.make(
            Parameter,
            monitoring=self.monitoring,
            complete=False,
            weight=1)
        # AND в каждой задаче есть оценка по parameter
        score = mommy.make(
            Score,
            task=task,
            parameter=parameter,
        )

    def test_approved_json(self):
        url = reverse('exmo2010:monitoring_export', args=[self.monitoring.pk])
        response = self.client.get(url + '?format=json')
        # THEN запрос удовлетворяется
        self.assertEqual(response.status_code, 200)
        # AND отдается json
        self.assertEqual(response.get('content-type'), 'application/json')
        json = simplejson.loads(response.content)
        self.assertEqual(len(json['monitoring']['tasks']), 0, simplejson.dumps(json, indent=2))

    def test_approved_csv(self):
        url = reverse('exmo2010:monitoring_export', args=[self.monitoring.pk])
        response = self.client.get(url + '?format=csv')
        # THEN запрос удовлетворяется
        self.assertEqual(response.status_code, 200)
        # AND отдается csv
        self.assertEqual(response.get('content-type'), 'application/vnd.ms-excel')
        csv = [line for line in UnicodeReader(StringIO(response.content))]
        #only header
        self.assertEqual(len(csv), 1)
