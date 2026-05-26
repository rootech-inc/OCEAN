from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from ssml.models import Contractor
import json


class ContractorApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='secret')
        self.url = reverse('contractors_api')

    def test_create_contractor(self):
        payload = {
            'module': 'contractor',
            'data': {
                'company': 'TestCo Ltd',
                'owner': 'Alice Johnson',
                'phone': '0244123456',
                'email': 'alice@testco.local',
                'country': 'Ghana',
                'city': 'Accra',
                'postal_code': 'GA-123-4567',
                'gh_post_code': 'GA-123-4567',
                'gh_card_no': 'GHA-1234567',
                'link': 'testco-link',
                'created_by': self.user.id
            }
        }
        response = self.client.put(self.url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('status_code'), 200)
        self.assertTrue(Contractor.objects.filter(company='TestCo Ltd').exists())

    def test_update_contractor(self):
        contractor = Contractor.objects.create(
            company='OldCo',
            owner='Bob Smith',
            phone='0244987654',
            email='bob@oldco.local',
            country='Ghana',
            city='Kumasi',
            postal_code='KA-111-2222',
            gh_post_code='KA-111-2222',
            gh_card_no='GHA-7654321',
            link='oldco-link',
            created_by=self.user
        )
        payload = {
            'module': 'contractor',
            'data': {
                'id': contractor.id,
                'company': 'NewCo Updated',
                'created_by': self.user.id
            }
        }
        response = self.client.put(self.url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('status_code'), 200)
        contractor.refresh_from_db()
        self.assertEqual(contractor.company, 'NewCo Updated')

    def test_patch_contractor_via_ssml_api(self):
        contractor = Contractor.objects.create(
            company='PatchCo',
            owner='Carol Brown',
            phone='0244000000',
            email='carol@patchco.local',
            country='Ghana',
            city='Tema',
            postal_code='TE-000-0000',
            gh_post_code='TE-000-0000',
            gh_card_no='GHA-0000000',
            link='patchco-link',
            created_by=self.user
        )
        payload = {
            'module': 'contractor',
            'data': {
                'id': contractor.id,
                'company': 'PatchCo Updated',
                'owner_phone': '0555000000'
            }
        }
        response = self.client.patch('/ssml/api/', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('status_code'), 200)
        contractor.refresh_from_db()
        self.assertEqual(contractor.company, 'PatchCo Updated')
        self.assertEqual(contractor.owner_phone, '0555000000')
