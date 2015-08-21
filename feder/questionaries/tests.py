from django.test import TestCase, RequestFactory
from django.core.urlresolvers import reverse
from feder.monitorings.models import Monitoring
from django.core.exceptions import PermissionDenied
from guardian.shortcuts import assign_perm
from autofixture import AutoFixture
# from feder.teryt.models import JednostkaAdministracyjna
# from feder.institutions.models import Institution
from feder.questionaries import views
from feder.questionaries.models import Questionary

try:
    from django.contrib.auth import get_user_model
    User = get_user_model()
except ImportError:
    from django.contrib.auth.models import User


class QuestionariesTestCase(TestCase):
    # def _get_third_level_jst(self):
    #     jst = AutoFixture(JednostkaAdministracyjna,
    #         field_values={'updated_on': '2015-02-12'},
    #         generate_fk=True).create_one(commit=False)
    #     jst.save()
    #     JednostkaAdministracyjna.objects.rebuild()
    #     return jst

    # def _get_institution(self):
    #     self._get_third_level_jst()
    #     institution = AutoFixture(Institution,
    #         field_values={'user': self.user},
    #         generate_fk=True).create_one()
    #     return institution

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='jacob', email='jacob@example.com', password='top_secret')
        assign_perm('monitorings.add_monitoring', self.user)
        self.quest = User.objects.create_user(
            username='smith', email='smith@example.com', password='top_secret')
        self.monitoring = Monitoring(name="Lor", user=self.user)
        self.monitoring.save()
        self.questionary = Questionary(title="blabla", monitoring=self.monitoring)
        self.questionary.save()

    def test_list_display(self):
        request = self.factory.get(reverse('questionaries:list'))
        request.user = self.user
        response = views.QuestionaryListView.as_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_details_display(self):
        request = self.factory.get(self.questionary.get_absolute_url())
        request.user = self.user
        response = views.QuestionaryDetailView.as_view()(request, pk=self.questionary.pk)
        self.assertEqual(response.status_code, 200)

    def _perm_check(self, view, reverse_name, kwargs):
        request = self.factory.get(reverse(reverse_name,
            kwargs=kwargs))
        request.user = self.user
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 200)

        request.user = self.quest
        with self.assertRaises(PermissionDenied):
            view(request, **kwargs)

    def test_create_permission_check(self):
        self._perm_check(views.QuestionaryCreateView.as_view(), 'questionaries:create',
            kwargs={'monitoring': str(self.monitoring.pk)})

    def test_update_permission_check(self):
        self._perm_check(views.QuestionaryUpdateView.as_view(), 'questionaries:update',
            kwargs={'pk': self.questionary.pk})

    def test_delete_permission_check(self):
        self._perm_check(views.QuestionaryDeleteView.as_view(), 'questionaries:delete',
            kwargs={'pk': self.questionary.pk})
