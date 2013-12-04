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
from textwrap import dedent

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test.client import Client
from django.test import TestCase
from model_mommy import mommy
from nose_parameterized import parameterized

from core.sql import *
from core.utils import get_named_patterns
from exmo2010.forms import CertificateOrderForm
from exmo2010.models import (
    Group, Monitoring, Organization, Parameter, Questionnaire, Score,
    Task, OpennessExpression, ValidationError)


class TestMonitoring(TestCase):
    # Scenario: monitoring model test

    @parameterized.expand([(code,) for code in OpennessExpression.OPENNESS_EXPRESSIONS])
    def test_sql_scores_valid(self, code):
        # WHEN openness code in allowable range
        monitoring = mommy.make(Monitoring, openness_expression__code=code)
        openness = monitoring.openness_expression
        expected_result = sql_monitoring_scores % {
            'sql_monitoring': openness.sql_monitoring(),
            'sql_openness_initial': openness.get_sql_openness(initial=True),
            'sql_openness': openness.get_sql_openness(),
            'monitoring_pk': monitoring.pk,
        }
        # THEN function return expected result
        self.assertEqual(monitoring.sql_scores(), expected_result)

    @parameterized.expand([(2,)])
    def test_sql_scores_invalid(self, code):
        # WHEN openness code in disallowable range
        monitoring = mommy.make(Monitoring, openness_expression__code=code)
        # THEN raises exception
        self.assertRaises(ValidationError, monitoring.sql_scores)


class NegativeParamMonitoringRatingTestCase(TestCase):
    # Parameters with negative weight SHOULD affect openness

    def setUp(self):
        # GIVEN monitoring with parameter that has negative weight
        self.monitoring = mommy.make(Monitoring, openness_expression__code=8)
        # AND parameter with weight -1
        self.parameter = mommy.make(Parameter, monitoring=self.monitoring, weight=-1, exclude=None,
                                    complete=1, topical=1, accessible=1, hypertext=1, document=1, image=1)
        # AND parameter with weight 2
        self.parameter2 = mommy.make(Parameter, monitoring=self.monitoring, weight=2, exclude=None,
                                    complete=1, topical=1, accessible=1, hypertext=1, document=1, image=1)
        # AND organization, approved task
        org = mommy.make(Organization, monitoring=self.monitoring)
        task = mommy.make(Task, organization=org, status=Task.TASK_APPROVED)

        # AND equal scores for 2 parameters
        kwargs = dict(found=1, complete=3, topical=3, accessible=3, hypertext=1, document=1, image=1)
        mommy.make(Score, task=task, parameter=self.parameter, **kwargs)
        mommy.make(Score, task=task, parameter=self.parameter2, **kwargs)

    def test_rating_with_negative_param(self):
        # WHEN rating is calculated for monitoring with parameter that has negative weight
        task = self.monitoring.rating()[0]
        # THEN task openness is 50%
        self.assertEqual(task.task_openness, 50)


class TestOpennessExpression(TestCase):
    # Scenario: openness expression model test
    parameters_count = 10
    empty_string = ""
    revision_filter = sql_revision_filter
    parameter_filter = sql_parameter_filter % ','.join(str(i) for i in range(1, parameters_count + 1))

    def setUp(self):
        # GIVEN 2 openness expressions with valid code
        self.v1 = mommy.make(OpennessExpression, code=1)
        self.v8 = mommy.make(OpennessExpression, code=8)
        # AND 1 openness expression with invalid code
        self.v2 = mommy.make(OpennessExpression, code=2)
        # AND any 10 parameters objects
        self.parameters = mommy.make(Parameter, _quantity=self.parameters_count)

    @parameterized.expand([
        ({}, [sql_score_openness_v1, revision_filter, empty_string]),
        ({'initial': True}, [sql_score_openness_initial_v1, empty_string, empty_string]),
        ({'parameters': True}, [sql_score_openness_v1, revision_filter, parameter_filter]),
        ({'parameters': True, 'initial': True}, [sql_score_openness_initial_v1, empty_string, parameter_filter]),
    ])
    def test_get_sql_openness_valid_v1(self, kwargs, args):
        # WHEN openness code in allowable range
        if kwargs.get('parameters', False):
            kwargs['parameters'] = self.parameters

        # THEN function return expected result
        self.assertEqual(self.v1.get_sql_openness(**kwargs),
                         self.expected_result(*args))

    @parameterized.expand([
        ({}, [sql_score_openness_v8, revision_filter, empty_string]),
        ({'initial': True}, [sql_score_openness_initial_v8, empty_string, empty_string]),
        ({'parameters': True}, [sql_score_openness_v8, revision_filter, parameter_filter]),
        ({'parameters': True, 'initial': True}, [sql_score_openness_initial_v8, empty_string, parameter_filter]),
    ])
    def test_get_sql_openness_valid_v1(self, kwargs, args):
        # WHEN openness code in allowable range
        if kwargs.get('parameters', False):
            kwargs['parameters'] = self.parameters

        # THEN function return expected result
        self.assertEqual(self.v8.get_sql_openness(**kwargs),
                         self.expected_result(*args))

    @parameterized.expand([
        ({},),
        ({'initial': True},),
        ({'parameters': True},),
        ({'parameters': True, 'initial': True},),
    ])
    def test_get_sql_openness_invalid(self, kwargs):
        # WHEN openness code is invalid
        if kwargs.get('parameters', False):
            kwargs['parameters'] = self.parameters

        # THEN raises exception
        self.assertRaises(ValidationError, self.v2.get_sql_openness, **kwargs)

    def expected_result(self, sql_score_openness, sql_revision_filter, sql_parameter_filter):
        result = sql_task_openness % {
            'sql_score_openness': sql_score_openness,
            'sql_revision_filter': sql_revision_filter,
            'sql_parameter_filter': sql_parameter_filter,
        }

        return result

    @parameterized.expand([
        (1, {}, sql_score_openness_v1),
        (8, {}, sql_score_openness_v8),
        (1, {'initial': True}, sql_score_openness_initial_v1),
        (8, {'initial': True}, sql_score_openness_initial_v8),
    ])
    def test_get_sql_expression_valid(self, code, kwargs, args):
        # WHEN openness code in allowable range
        # THEN function return expected result
        openness = getattr(self, 'v%d' % code)
        self.assertEqual(openness.get_sql_expression(kwargs), args)

    @parameterized.expand([
        ({},),
        ({'initial': True},),
    ])
    def test_get_sql_expression_invalid(self, kwargs):
        # WHEN openness code is invalid
        # THEN raises exception
        self.assertRaises(ValidationError, self.v2.get_sql_expression, **kwargs)

    @parameterized.expand([
        (1, sql_monitoring_v1),
        (8, sql_monitoring_v8),
    ])
    def test_sql_monitoring_valid(self, code, result):
        # WHEN openness code in allowable range
        # THEN function return expected result
        openness = getattr(self, 'v%d' % code)
        self.assertEqual(openness.sql_monitoring(), result)

    def test_sql_monitoring_invalid(self):
        # WHEN openness code is invalid
        # THEN raises exception
        self.assertRaises(ValidationError, self.v2.sql_monitoring)


class CanonicalViewKwargsTestCase(TestCase):
    # Url patterns and views should use and accept only canonical kwargs

    exmo_urlpatterns = [pat for pat in get_named_patterns() if pat._full_name.startswith('exmo2010:')]

    post_urls = set([
        'claim_create',
        'claim_delete',
        'clarification_create',
        'get_pc',
        'user_reset_dashboard',
        'toggle_comment',
    ])

    ajax_urls = set([
        'get_qq',
        'get_qqt',
        'ajax_task_approve',
        'ajax_task_open',
        'ajax_task_close',
    ])

    urls_excluded = [
        'auth_logout',   # do not logout during test
        'ratingUpdate',  # requires GET params, should be tested explicitly,
        'certificate_order'  # require org permissions, should be tested explicitly
    ]

    test_patterns = set([p.name for p in exmo_urlpatterns]) - set(urls_excluded)

    def setUp(self):
        # GIVEN monitoring, organization
        monitoring = mommy.make(Monitoring)
        organization = mommy.make(Organization, monitoring=monitoring)
        # AND approved task (for monitoring_answers_export to work)
        task = mommy.make(Task, organization=organization, status=Task.TASK_APPROVED)
        # AND parameter, score, questionnaire
        parameter = mommy.make(Parameter, monitoring=monitoring)
        score = mommy.make(Score, task=task, parameter=parameter)
        questionnaire = mommy.make(Questionnaire, monitoring=monitoring)

        # AND i am logged-in as superuser
        admin = User.objects.create_superuser('admin', 'admin@svobodainfo.org', 'password')
        admin.groups.add(Group.objects.get(name=admin.profile.expertA_group))
        self.client = Client()
        self.client.login(username='admin', password='password')

        # AND canonical kwargs to reverse view urls
        self.auto_pattern_kwargs = {
            'monitoring_pk': monitoring.pk,
            'score_pk': score.pk,
            'parameter_pk': parameter.pk,
            'task_pk': task.pk,
            'org_pk': organization.pk,
            'activation_key': '123',  # for registration_activate
            'uidb36': '123',          # for auth_password_reset_confirm
            'token': '123',           # for auth_password_reset_confirm
            'report_type': 'inprogress',   # for monitoring_report_*
            'print_report_type': 'print',  # for score_list_by_task
        }

        self.patterns_by_name = dict((p.name, p) for p in self.exmo_urlpatterns)

    @parameterized.expand(test_patterns)
    def test_urlpattern(self, name):
        pat = self.patterns_by_name[name]

        if pat.regex.groups > len(pat.regex.groupindex):
            raise Exception(dedent(
                'Urlpattern ("%s", "%s") uses positional args and can\'t be reversed for this test.\
                It should be modified to use only kwargs or excluded from this test and tested explicitly'\
                    % (pat.regex.pattern, pat.name)))
        unknown_kwargs = set(pat.regex.groupindex) - set(self.auto_pattern_kwargs)
        if unknown_kwargs:
            raise Exception(dedent(
                'Urlpattern ("%s", "%s") uses unknown kwargs and can\'t be reversed for this test.\
                These kwargs should be added to this test\'s auto_pattern_kwargs in setUp'\
                    % (pat.regex.pattern, pat.name)))

        kwargs = dict((k, self.auto_pattern_kwargs[k]) for k in pat.regex.groupindex)
        url = reverse(pat._full_name, kwargs=kwargs)

        # WHEN i get url
        if pat.name in self.ajax_urls:
            res = self.client.get(url, follow=True, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        else:
            res = self.client.get(url, follow=True)

        # THEN no exception should raise

        if pat.name not in set(self.ajax_urls | self.post_urls):
            # AND non-ajax and non-post urls should return http status 200 (OK)
            self.assertEqual(res.status_code, 200)


class CertificateOrderFormTestCase(TestCase):
    # Scenario: Form tests
    @parameterized.expand([
        (1, 1, 0, 'name', 'wishes', 'test@mail.com', '', '', ''),
        (2, 0, 0, '', '', 'test@mail.com', '', '', ''),
        (3, 0, 1, '', '', 'test@mail.com', 'name', '123456', 'address'),
    ])
    def test_valid_form(self, task_id, certificate_for, send, name, wishes, email, for_whom, zip_code, address):
        # WHEN user send CertificateOrderForm with data
        form_data = {
            'task_id': task_id,
            'certificate_for': certificate_for,
            'send': send,
            'name': name,
            'wishes': wishes,
            'email': email,
            'for_whom': for_whom,
            'zip_code': zip_code,
            'address': address,
        }

        form = CertificateOrderForm(data=form_data)
        # THEN form is valid
        self.assertEqual(form.is_valid(), True)

    @parameterized.expand([
        (1, 1, 0, 'name', 'wishes', 'test@.mail.com', '', '', ''),
        (3, 0, 1, '', '', 'test@mail.com', 'name', '1234', 'address'),
        (3, 0, 1, '', '', 'test@mail.com', 'name', 'text', 'address'),
    ])
    def test_invalid_form(self, task_id, certificate_for, send, name, wishes, email, for_whom, zip_code, address):
        # WHEN user send CertificateOrderForm with data
        form_data = {
            'task_id': task_id,
            'certificate_for': certificate_for,
            'send': send,
            'name': name,
            'wishes': wishes,
            'email': email,
            'for_whom': for_whom,
            'zip_code': zip_code,
            'address': address,
        }

        form = CertificateOrderForm(data=form_data)
        # THEN form is invalid
        self.assertEqual(form.is_valid(), False)
