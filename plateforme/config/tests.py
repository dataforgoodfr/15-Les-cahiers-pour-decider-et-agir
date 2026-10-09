from django.contrib.auth.models import User
from django.test import TestCase


class AdminTests(TestCase):
    def test_page_de_connexion(self):
        reponse = self.client.get("/admin/login/")
        self.assertContains(reponse, "Les cahiers pour décider et agir")

    def test_admin_reservee_aux_administrateurs(self):
        self.assertRedirects(self.client.get("/admin/"), "/admin/login/?next=/admin/")
        User.objects.create_superuser("admin", password="motdepasse")
        self.client.login(username="admin", password="motdepasse")
        self.assertEqual(self.client.get("/admin/").status_code, 200)
