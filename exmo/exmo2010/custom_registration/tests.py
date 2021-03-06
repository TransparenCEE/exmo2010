# -*- coding: utf-8 -*-
# This file is part of EXMO2010 software.
# Copyright 2014 Foundation "Institute for Information Freedom Development"
# Copyright 2014-2015 IRSI LTD
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
import re
from urllib import urlencode

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.auth import authenticate
from django.core import mail
from django.core.urlresolvers import resolve, reverse
from django.http.request import QueryDict
from mock import MagicMock
from model_mommy import mommy
from nose_parameterized import parameterized

from . import tokens
from .views import registration_form
from core.test_utils import OptimizedTestCase
from core.test_utils import TestCase
from exmo2010.models import Monitoring, Organization, Task, MONITORING_INTERACTION


class EmailConfirmationTestCase(TestCase):
    # exmo2010:confirm_email

    #TODO: move this testcase to *general logic* tests directory

    # Should activate user after he visits confirmation link from email.
    # Should fail if url token is forged.

    fields = 'first_name patronymic last_name email password notification'.split()

    def test_after_registration(self):
        user_email = 'test@mail.com'
        # WHEN I visit registration page (to enable test_cookie)
        self.client.get(reverse('exmo2010:registration_form'))
        # AND I submit registration form
        hostname = 'test.host.com'
        form_data = dict(zip(self.fields, ('first_name', 'patronymic', 'last_name', user_email, 'password', '')))
        response = self.client.post(reverse('exmo2010:registration_form'), form_data, HTTP_HOST=hostname, follow=True)
        # THEN I should be redirected to auth_send_email page and then to please_confirm_email page
        self.assertEqual(response.redirect_chain[0],
                         ('http://' + hostname + reverse('exmo2010:auth_send_email') + '?' +
                         urlencode({'email': form_data['email']}), 302))
        self.assertEqual(response.redirect_chain[1],
                         ('http://' + hostname + reverse('exmo2010:please_confirm_email') + '?' +
                          urlencode({'email': form_data['email']}), 302))
        # AND one user should be created with email_confirmed=False and is_active=False
        all_confirmed = [u.profile.email_confirmed for u in User.objects.all()]
        all_active = [u.is_active for u in User.objects.all()]
        self.assertEqual(all_confirmed, [False])
        self.assertEqual(all_active, [False])
        # AND one email message should be sent
        self.assertEqual(len(mail.outbox), 1)

        # WHEN i visit confirmation link
        url = re.search('http://(?P<host>[^/]+)(?P<rel_url>[^\s]+)', mail.outbox[0].body).group('rel_url')
        response = self.client.get(url)

        # THEN i should be redirected to the index page
        self.assertRedirects(response, reverse('exmo2010:index'))
        # AND user should be activated with email_confirmed=True and is_active=True
        all_confirmed = [u.profile.email_confirmed for u in User.objects.all()]
        all_active = [u.is_active for u in User.objects.all()]
        self.assertEqual(all_confirmed, [True])
        self.assertEqual(all_active, [True])

    def test_after_resend_email(self):
        # GIVEN existing non-activated user
        user = User.objects.create_user('org', 'test@mail.com', 'password')
        user.is_active = False
        user.save()
        user.profile.email_confirmed = False
        user.profile.save()

        # WHEN I visit registration page (to enable test_cookie)
        # self.client.get(reverse('exmo2010:registration_form'))
        # AND I submit resend confirmation email form
        response = self.client.get(reverse('exmo2010:auth_send_email') + '?' + urlencode({'email': 'test@mail.com'}))
        # THEN I should be redirected to the please_confirm_email page
        self.assertRedirects(response,
                             reverse('exmo2010:please_confirm_email') + '?' + urlencode({'email': user.email}))
        # AND one user should be created with email_confirmed=False and is_active=False
        all_confirmed = [u.profile.email_confirmed for u in User.objects.all()]
        all_active = [u.is_active for u in User.objects.all()]
        self.assertEqual(all_confirmed, [False])
        self.assertEqual(all_active, [False])
        # AND one email message should be sent
        self.assertEqual(len(mail.outbox), 1)

        # WHEN i visit confirmation link
        url = re.search('http://(?P<host>[^/]+)(?P<rel_url>[^\s]+)', mail.outbox[0].body).group('rel_url')
        response = self.client.get(url)
        # THEN i should be redirected to the index page
        self.assertRedirects(response, reverse('exmo2010:index'))
        # AND user should be activated with email_confirmed=True and is_active=True
        all_confirmed = [u.profile.email_confirmed for u in User.objects.all()]
        all_active = [u.is_active for u in User.objects.all()]
        self.assertEqual(all_confirmed, [True])
        self.assertEqual(all_active, [True])

    def test_forged_confirmation_url(self):
        # WHEN i visit registration page (to enable test_cookie)
        self.client.get(reverse('exmo2010:registration_form'))
        # AND i submit registration form
        data = ('first_name', 'patronymic', 'last_name', 'test@mail.com', 'password', '')
        self.client.post(reverse('exmo2010:registration_form'), dict(zip(self.fields, data)))

        # WHEN i visit forged confirm_email url
        url = reverse('exmo2010:confirm_email', args=[User.objects.all()[0].pk, '122-2342262654'])
        response = self.client.get(url, follow=True)

        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)

        # AND user should still have email_confirmed=False and is_active=False
        all_confirmed = [u.profile.email_confirmed for u in User.objects.all()]
        all_active = [u.is_active for u in User.objects.all()]
        self.assertEqual(all_confirmed, [False])
        self.assertEqual(all_active, [False])


class RegistrationWithKnownOrgEmailTestCase(TestCase):
    # exmo2010:registration_form

    #TODO: move this testcase to general logic tests directory

    # If registering user email matches any organization email which he is willing to represent, he should be activated
    # immediately after registration form is submitted.
    # If task for given org exists and user has permission to view it - redirect him to the task recommendations page.
    # Otherwise redirect him to the front page

    def setUp(self):
        # GIVEN organization in INTERACTION monitoring
        self.org = mommy.make(Organization, monitoring__status=MONITORING_INTERACTION, email='org@test.ru')

    def test_registration_with_task_accessible(self):
        # GIVEN approved task for existing org
        expertB = User.objects.create_user('expertB', 'expertB@svobodainfo.org', 'password')
        task = mommy.make(Task, organization=self.org, status=Task.TASK_APPROVED, user=expertB)
        # NOTE: pop email message about task assignment
        mail.outbox.pop()

        # WHEN i visit registration page (to enable test_cookie)
        self.client.get(reverse('exmo2010:registration_form'))
        # AND i submit registration form
        url = reverse('exmo2010:registration_form') + '?code={}'.format(self.org.inv_code)
        response = self.client.post(url, {'email': self.org.email, 'password': 'password'})

        # THEN i should be redirected to the front page
        self.assertRedirects(response, reverse('exmo2010:recommendations', args=(task.pk,)))
        # AND no email message should be sent
        self.assertEqual(len(mail.outbox), 0)
        # AND 2 users should exist in database (new user and task expertB)
        emails = set(User.objects.values_list('email', flat=True))
        self.assertEqual(emails, {'expertB@svobodainfo.org', self.org.email})
        # AND user should be activated with email_confirmed=True and is_active=True
        all_confirmed = [u.profile.email_confirmed for u in User.objects.all()]
        all_active = [u.is_active for u in User.objects.all()]
        self.assertEqual(all_confirmed, [True, True])
        self.assertEqual(all_active, [True, True])

    def test_registration_without_task(self):
        # WHEN i visit registration page (to enable test_cookie)
        self.client.get(reverse('exmo2010:registration_form'))
        # AND i submit registration form
        url = reverse('exmo2010:registration_form') + '?code={}'.format(self.org.inv_code)
        response = self.client.post(url, {'email': self.org.email, 'password': 'password'})

        # THEN i should be redirected to the front page
        self.assertRedirects(response, reverse('exmo2010:index'))
        # AND no email message should be sent
        self.assertEqual(len(mail.outbox), 0)
        # AND user should be activated with email_confirmed=True and is_active=True
        all_confirmed = [u.profile.email_confirmed for u in User.objects.all()]
        all_active = [u.is_active for u in User.objects.all()]
        self.assertEqual(all_confirmed, [True])
        self.assertEqual(all_active, [True])


class RegistrationEmailTestCase(TestCase):
    # exmo2010:registration_form

    #TODO: move this testcase to email tests directory

    # If registering user email does not match any organization email which he is willing to represent,
    # email message with activation url should be sent when registration form is submitted.

    def test_registration(self):
        # WHEN I visit registration page (to enable test_cookie)
        self.client.get(reverse('exmo2010:registration_form'))
        # AND I submit registration form
        hostname = 'test.host.com'
        form_data = {'status': 'representative', 'email': 'test@mail.com', 'password': '123'}
        response = self.client.post(reverse('exmo2010:registration_form'), form_data, HTTP_HOST=hostname, follow=True)

        # THEN I should be redirected to auth_send_email page and then to please_confirm_email page
        self.assertEqual(response.redirect_chain[0],
                         ('http://' + hostname + reverse('exmo2010:auth_send_email') + '?' +
                         urlencode({'email': form_data['email']}), 302))
        self.assertEqual(response.redirect_chain[1],
                         ('http://' + hostname + reverse('exmo2010:please_confirm_email') + '?' +
                          urlencode({'email': form_data['email']}), 302))
        # AND one email message should be sent
        self.assertEqual(len(mail.outbox), 1)
        # AND message contain valid link with email confirmation token
        url = re.search('http://(?P<host>[^/]+)(?P<rel_url>[^\s]+)', mail.outbox[0].body).group('rel_url')
        urlkwargs = resolve(url).kwargs
        user = User.objects.get(pk=urlkwargs['user_pk'])
        token_generator = tokens.EmailConfirmTokenGenerator()
        self.assertTrue(token_generator.check_token(user, urlkwargs['token']))


class RegistrationWithInvCodesAndRedirectTestCase(TestCase):
    # exmo2010:registration_form

    # If registering user email matches any organization email which he is willing to represent,
    # he should be redirected to the recommendations page if the count of organizations equals one,
    # or to the index page if the count of organizations more then one.
    # Otherwise redirect him to the please_confirm_email page.

    def setUp(self):
        # GIVEN INTERACTION monitoring
        self.monitoring = mommy.make(Monitoring, status=MONITORING_INTERACTION)
        # AND two organizations with unique emails
        self.org1 = mommy.make(Organization, monitoring=self.monitoring, email='org1@test.ru')
        self.org2 = mommy.make(Organization, monitoring=self.monitoring, email='org2@test.ru')
        # AND approved task for each organization
        self.task1 = mommy.make(Task, organization=self.org1, status=Task.TASK_APPROVED)
        self.task2 = mommy.make(Task, organization=self.org2, status=Task.TASK_APPROVED)
        # AND url for GET and POST requests
        self.url = reverse('exmo2010:registration_form')

    def test_two_codes_and_not_orgs_email(self):
        user_email = 'usr@svobodainfo.org'
        # WHEN I get registration page with 2 invitation codes and not orgs email in GET params
        params = {'code': [self.org1.inv_code, self.org2.inv_code], 'email': user_email}
        url = self.url + '?' + urlencode(params, True)
        response_get = self.client.get(url)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(response_get.status_code, 200)

        # WHEN I get all initial values and add value for password field
        hostname = 'test.host.com'
        form_data = response_get.context['form'].initial
        form_data.update({'password': 'password'})
        # AND submit form
        response_post = self.client.post(url, form_data, HTTP_HOST=hostname, follow=True)
        # THEN I should be redirected to the auth_send_email page and then to please_confirm_email page
        self.assertEqual(response_post.redirect_chain[0],
                         ('http://' + hostname + reverse('exmo2010:auth_send_email') + '?' +
                         urlencode(params, True), 302))
        self.assertEqual(response_post.redirect_chain[1],
                         ('http://' + hostname + reverse('exmo2010:please_confirm_email') + '?' +
                          urlencode({'email': form_data['email']}), 302))
        # AND I shouldn't be connected to any organizations from url
        user = User.objects.get(email=user_email)
        self.assertEqual(set(user.profile.organization.values_list('inv_code', flat=True)), set([]))

    def test_two_codes_and_org_email(self):
        # WHEN I get registration page with 2 invitation codes and org email in GET params
        params = {'code': [self.org1.inv_code, self.org2.inv_code], 'email': self.org1.email}
        url = self.url + '?' + urlencode(params, True)
        response_get = self.client.get(url)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(response_get.status_code, 200)

        # WHEN I get all initial values and add value for password field
        data = response_get.context['form'].initial
        data.update({'password': 'password'})
        # AND submit form
        response_post = self.client.post(url, data)
        # THEN I should be redirected to the index page
        self.assertRedirects(response_post, reverse('exmo2010:index'))
        # AND I should be connected to 2 organizations from url
        user = User.objects.get(email=self.org1.email)
        self.assertEqual(set(user.profile.organization.values_list('inv_code', flat=True)),
                         {self.org1.inv_code, self.org2.inv_code})

    def test_one_code_and_org_email(self):
        # WHEN I get registration page with 1 invitation code and org email in GET params
        params = {'code': [self.org1.inv_code], 'email': self.org1.email}
        url = self.url + '?' + urlencode(params, True)
        response_get = self.client.get(url)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(response_get.status_code, 200)

        # WHEN I get all initial values and add value for password field
        data = response_get.context['form'].initial
        data.update({'password': 'password'})
        # AND submit form
        response_post = self.client.post(url, data)
        # THEN I should be redirected to the recommendations page
        self.assertRedirects(response_post, reverse('exmo2010:recommendations', args=(self.task1.pk,)))
        # AND I should be connected to 1 organization from url
        user = User.objects.get(email=self.org1.email)
        self.assertEqual(set(user.profile.organization.values_list('inv_code', flat=True)), {self.org1.inv_code})


class RegistrationFormValidationTestCase(OptimizedTestCase):
    # TODO: move this testcase to *validation* tests directory

    # exmo2010:registration_form

    # RegistrationForm should properly validate input data

    @classmethod
    def setUpClass(cls):
        super(RegistrationFormValidationTestCase, cls).setUpClass()
        mommy.make(Organization, inv_code='123')
        cls.url = reverse('exmo2010:registration_form')

    @parameterized.expand([
        ('email1@test.com', 'password', ''),
        ('email2@test.com', 'password', '123'),
        ('email3@мвд.рф', 'password', '123'),
    ])
    def test_valid_form(self, email, password, inv_code):
        # WHEN anonymous submits request with valid data
        data = {'email': email, 'password': password, 'invitation_code': inv_code}
        request = MagicMock(user=AnonymousUser(), method='POST', POST=data, GET=QueryDict(''))
        request.path_info = self.url
        response = registration_form(request)
        # THEN response status_code should be 302 (redirect)
        self.assertEqual(response.status_code, 302)
        # AND user should be registered
        self.assertEqual(User.objects.filter(email=email).count(), 1)

    @parameterized.expand([
        ('', 'password', ''),  # missing email
        ('invalid_email.com', 'password', ''),  # incorrect email
        ('юзер@мвд.рф', 'password', ''),   # rfc6531 usernames in email is not supported yet
        ('valid_email@test.com', '', ''),  # missing password
        ('valid_email@test.com', 'password', '456'),  # invalid invite code
        ('valid_email@test.com', 'password', 'ыва'),  # invalid invite code (cyrillic, see BUG 2386)
    ])
    def test_invalid_form(self, email, password, inv_code):
        # WHEN anonymous submits request with invalid data
        data = {'email': email, 'password': password, 'invitation_code': inv_code}
        request = MagicMock(user=AnonymousUser(), method='POST', POST=data, GET=QueryDict(''))
        request.path_info = self.url
        response = registration_form(request)
        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)
        # AND form validation should fail
        self.assertEqual(response.context_data['form'].is_valid(), False)
        # AND user shouldn't be registered
        self.assertEqual(User.objects.filter(email=email).count(), 0)


class ResendConfirmationEmailTestCase(TestCase):
    # exmo2010:auth_send_email

    #TODO: move this testcase to email tests directory

    # Should send email when resend activation email form submitted.

    def setUp(self):
        # GIVEN existing user
        self.user = User.objects.create_user('user', 'test@mail.com', 'password')

    def test_resend(self):
        # WHEN I get resend email url with email in GET parameters
        response = self.client.get(reverse('exmo2010:auth_send_email') + '?' + urlencode({'email': self.user.email}))
        # THEN I should be redirected to the please_confirm_email page
        self.assertRedirects(response,
                             reverse('exmo2010:please_confirm_email') + '?' + urlencode({'email': self.user.email}))
        # AND one email message should be sent
        self.assertEqual(len(mail.outbox), 1)


class PasswordResetEmailTestCase(TestCase):
    # exmo2010:password_reset_request

    #TODO: move this testcase to email tests directory

    # Should send email with password reset url when reset password form is submitted.

    def setUp(self):
        # GIVEN existing user
        self.user = User.objects.create_user('user', 'test@mail.com', 'password')

    def test_password_reset(self):
        # WHEN i submit reset password form
        response = self.client.post(reverse('exmo2010:password_reset_request'), {'email': self.user.email})
        # THEN i should be redirected to the password_reset_sent page
        self.assertRedirects(response,
                             reverse('exmo2010:password_reset_sent') + '?' + urlencode({'email': self.user.email}))
        # AND one email message should be sent
        self.assertEqual(len(mail.outbox), 1)


class PasswordResetConfirmTestCase(TestCase):
    # exmo2010:password_reset_confirm

    #TODO: move this testcase to general logic tests directory

    # Valid reset url should show password reset form, which should allow to
    # update password. After updating user should be connected to organizations
    # if confirmation link in email contains invitation codes.

    def setUp(self):
        # GIVEN existing user
        self.user = User.objects.create_user('user', 'test@mail.com', 'password')
        # AND two organizations
        orgs = mommy.make(Organization, _quantity=2)
        # AND list of organization codes
        self.codes = [orgs[0].inv_code, orgs[1].inv_code]
        # AND password reset url
        self.url = reverse('exmo2010:password_reset_request')

    def test_password_reset_and_redirect(self):
        # WHEN i submit reset password form
        response = self.client.post(self.url, {'email': 'test@mail.com'})
        # THEN i should be redirected to the password_reset_sent page
        self.assertRedirects(response,
                             reverse('exmo2010:password_reset_sent') + '?' + urlencode({'email': self.user.email}))
        # AND one email message should be sent
        self.assertEqual(len(mail.outbox), 1)

        # WHEN i visit confirmation link
        url = re.search('http://(?P<host>[^/]+)(?P<rel_url>[^\s]+)', mail.outbox[0].body).group('rel_url')
        response = self.client.get(url)

        # THEN response status_code should be 200 (OK)
        self.assertEqual(response.status_code, 200)
        # AND new_password form should be displayed.
        self.assertTrue('new_password_form' in response.content)

        # WHEN i submit new_password form with new password
        response = self.client.post(url, {'new_password': 'new'})

        # THEN i should be redirected to the index page
        self.assertRedirects(response, reverse('exmo2010:index'))
        # AND user password should change
        user = authenticate(username='user', password='new')
        self.assertEqual(self.user, user)

    def test_password_reset_and_connect_to_orgs(self):
        # WHEN I submit reset password form with GET parameters in url
        self.client.post(self.url + '?' + urlencode({'code': self.codes}, True), {'email': self.user.email})
        # THEN one email message should be sent
        self.assertEqual(len(mail.outbox), 1)

        # WHEN I get confirmation link from email
        confirmation_url = re.search('http://(?P<host>[^/]+)(?P<rel_url>[^\s]+)', mail.outbox[0].body).group('rel_url')
        # AND submit new_password form with new password
        self.client.post(confirmation_url, {'new_password': 'new'})
        # THEN I should be connected to 2 organizations from url
        user = User.objects.get(pk=self.user.pk)
        self.assertEqual(set(user.profile.organization.values_list('inv_code', flat=True)), set(self.codes))
