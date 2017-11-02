import warnings

from django.conf import settings
from django.contrib.auth.models import User, AnonymousUser, Group
from django.core.urlresolvers import reverse
from django.db import models
from django.test.testcases import TestCase

from hamcrest import assert_that, instance_of, equal_to, is_, empty, has_length

from django_currentuser.middleware import (
    get_current_user, _set_current_user, get_current_authenticated_user)
from django_currentuser.db.models import CurrentUserField

from .sixmock import patch


class TestSetUserToThread(TestCase):

    def tearDown(self):
        super(TestSetUserToThread, self).tearDown()
        _set_current_user(None)

    def setUp(self):
        super(TestSetUserToThread, self).setUp()
        self.user1 = User.objects.create(username="user1", is_staff=True)
        self.user1.set_password("pw1")
        self.user1.save()
        self.user2 = User.objects.create(username="user2", is_staff=True)
        self.user2.set_password("pw2")
        self.user2.save()

    def test__local_thread_var_is_set_to_logged_in_user(self):
        _set_current_user(None)
        self.assertIsNone(get_current_user())

        self.login_and_go_to_homepage(username="user1", password="pw1")
        self.assertEqual(self.user1, get_current_user())
        self.client.logout()

        self.login_and_go_to_homepage(username="user2", password="pw2")
        self.assertEqual(self.user2, get_current_user())
        self.client.logout()

        self.client.get("/")
        current_user = get_current_user()
        assert_that(current_user, instance_of(AnonymousUser))

    def login_and_go_to_homepage(self, username, password):
        data = {"username": username, "password": password}
        self.client.post(reverse("login"), follow=True, data=data)
        self.client.get('/')


class GetCurrentPersistedUserTestCase(TestCase):

    def test_if_user_is_none_it_is_none(self):
        self.assert_becomes(current_user=None, expected_thread_user=None)

    def test_if_user_then_its_the_user(self):
        user = User(email='jane@acme.org')
        self.assert_becomes(current_user=user, expected_thread_user=user)

    def test_if_anon_user_then_none(self):
        self.assert_becomes(
            current_user=AnonymousUser(), expected_thread_user=None)

    def assert_becomes(self, current_user, expected_thread_user):
        _set_current_user(current_user)
        assert_that(
            get_current_authenticated_user(), equal_to(expected_thread_user))


class CurrentUserFieldTestCase(TestCase):

    field_cls = CurrentUserField

    def setUp(self):
        super(CurrentUserFieldTestCase, self).setUp()
        warnings.simplefilter("always")

    def test_is_a_foreignkey(self):
        assert_that(issubclass(self.field_cls, models.ForeignKey), is_(True))

    @patch.object(models.ForeignKey, "__init__")
    def test_ignores_args_and_kwargs_for_default_null_and_to(self,
                                                             mock_fk_init):
        self.field_cls(Group, default="foo", null="bar", to='baz')

        assert_that(mock_fk_init.was_called)
        assert_that(mock_fk_init.call_count, equal_to(1))
        args, kwargs = mock_fk_init.call_args
        assert_that(args, empty())
        assert_that(set(kwargs).intersection({"foo", "bar", "baz"}), empty())

    def test_raises_warning_when_non_default_arguments_are_passed(self):
        with warnings.catch_warnings(record=True) as my_warnings:
            self.field_cls(Group)
            self.field_cls(default="foo")
            self.field_cls(null="bar")
            self.field_cls(to='baz')
            assert_that(my_warnings, has_length(4))
            assert_that([str(m.message) for m in my_warnings],
                        is_([CurrentUserField.warning] * 4))

    def test_no_warning_raised_if_passed_argument_values_match_defaults(self):
        with warnings.catch_warnings(record=True) as my_warnings:
            self.field_cls(default=get_current_authenticated_user)
            self.field_cls(null=True)
            self.field_cls(to="auth.User")
            assert_that(my_warnings, has_length(0))

    def test_is_a_nullable_fk_to_the_user_model(self):
        field = self.field_cls()
        assert_that(field.rel.to, is_(equal_to(settings.AUTH_USER_MODEL)))
        assert_that(field.null, is_(True))

    def test_default_value_is_get_current_django_user(self):
        field = self.field_cls()
        assert_that(field.default, is_(get_current_authenticated_user))
