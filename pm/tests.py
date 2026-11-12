import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase

from pm.models import Clients, Projects, ProjectTimeline


class PmCrudTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='pmtester', password='secret', first_name='PM', last_name='Tester')
        self.http = Client()
        self.http.force_login(self.user)

    def _api(self, method, module, data):
        return self.http.generic(
            method,
            '/pm/api/',
            json.dumps({'module': module, 'data': data}),
            content_type='application/json',
        )

    def test_pages_render(self):
        res_projects = self.http.get('/pm/')
        self.assertEqual(res_projects.status_code, 200)

        res_clients = self.http.get('/pm/clients/')
        self.assertEqual(res_clients.status_code, 200)

    @patch('pm.pm_api.generate_text', return_value='Generated SEO text')
    def test_full_crud_flow(self, _mock_ai):
        # 1. Client Create
        res = self._api('PUT', 'client', {
            'name': 'Acme Corp',
            'email': 'info@acme.example',
            'phone': '+233200000001',
            'address': '123 Accra Way',
        })
        body = res.json()
        self.assertEqual(body['status_code'], 200)
        client_pk = body['message']['pk']

        # Client Read
        res = self._api('VIEW', 'client', {'pk': '*'})
        self.assertEqual(res.json()['status_code'], 200)
        self.assertEqual(len(res.json()['message']), 1)

        # Client Update
        res = self._api('PATCH', 'client', {'pk': client_pk, 'phone': '+233200000002'})
        self.assertEqual(res.json()['status_code'], 200)
        self.assertEqual(res.json()['message']['phone'], '+233200000002')

        # 2. Project Create
        res = self._api('PUT', 'project', {
            'client_pk': client_pk,
            'type': 'software',
            'title': 'ERP Rollout',
            'description': 'Full ERP deployment',
            'mypk': self.user.pk,
        })
        p_body = res.json()
        self.assertEqual(p_body['status_code'], 200)
        project_pk = p_body['message']['pk']
        project_url = p_body['message']['url']

        # Project Detail Page
        res_detail = self.http.get(f'/pm/projects/{project_url}/')
        self.assertEqual(res_detail.status_code, 200)

        # Project Read (single & list)
        res = self._api('VIEW', 'project', {'url': project_url})
        self.assertEqual(res.json()['status_code'], 200)
        self.assertEqual(res.json()['message']['pk'], project_pk)

        # Project Update
        res = self._api('PATCH', 'project', {'pk': project_pk, 'is_closed': True, 'is_open': False})
        self.assertEqual(res.json()['status_code'], 200)
        self.assertTrue(res.json()['message']['is_closed'])

        # 3. Timeline Create
        res = self._api('PUT', 'update_timeline', {
            'url': project_url,
            'title': 'Kickoff',
            'description': 'Initial kickoff meeting',
            'date': '2026-11-12',
            'mypk': self.user.pk,
        })
        tl_body = res.json()
        self.assertEqual(tl_body['status_code'], 200)
        tl_pk = tl_body['message']['timeline']['pk']

        # Timeline Update
        res = self._api('PATCH', 'update_timeline', {
            'pk': tl_pk,
            'title': 'Kickoff Updated',
        })
        self.assertEqual(res.json()['status_code'], 200)
        self.assertEqual(res.json()['message']['timeline']['title'], 'Kickoff Updated')

        # Protected delete check: cannot delete project while timeline exists
        res = self._api('DELETE', 'project', {'pk': project_pk})
        self.assertNotEqual(res.json()['status_code'], 200)

        # Timeline Delete
        res = self._api('DELETE', 'update_timeline', {'pk': tl_pk})
        self.assertEqual(res.json()['status_code'], 200)
        self.assertEqual(ProjectTimeline.objects.count(), 0)

        # Project Delete
        res = self._api('DELETE', 'project', {'pk': project_pk})
        self.assertEqual(res.json()['status_code'], 200)
        self.assertEqual(Projects.objects.count(), 0)

        # Client Delete
        res = self._api('DELETE', 'client', {'pk': client_pk})
        self.assertEqual(res.json()['status_code'], 200)
        self.assertEqual(Clients.objects.count(), 0)
