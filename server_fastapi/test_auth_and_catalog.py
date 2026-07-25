"""
SYJ OpenTrade Logic - v0.4.0 integration tests
=================================================
Real FastAPI TestClient tests covering: registration, login, RBAC
enforcement across all four roles, organization data isolation (org A
cannot see org B's products), and CSV import end-to-end.

Run on your machine (needs the full stack installed):
    python3 -m unittest server_fastapi.test_auth_and_catalog -v
"""

import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAuthAndCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Termux's system /tmp is often read-only for regular processes --
        # create the temp test DB inside the project directory instead.
        local_tmp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".test_tmp")
        os.makedirs(local_tmp_dir, exist_ok=True)
        cls.tmp_db_fd, cls.tmp_db_path = tempfile.mkstemp(suffix=".db", dir=local_tmp_dir)
        os.close(cls.tmp_db_fd)
        os.remove(cls.tmp_db_path)
        os.environ["SYJ_DATABASE_URL"] = f"sqlite:///{cls.tmp_db_path}"
        os.environ["SYJ_SECRET_KEY"] = "test-secret-key-not-for-production"

        from fastapi.testclient import TestClient
        from server_fastapi.database import init_db
        from server_fastapi.main import app

        init_db()  # explicit -- don't rely on TestClient triggering @app.on_event("startup")
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.tmp_db_path):
            os.remove(cls.tmp_db_path)

    def _register(self, org_name, email, password="Sup3rSecret!", full_name="Test User"):
        resp = self.client.post("/auth/register", json={
            "organization_name": org_name,
            "email": email,
            "password": password,
            "full_name": full_name,
        })
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()

    def _auth_headers(self, access_token):
        return {"Authorization": f"Bearer {access_token}"}

    def test_register_creates_org_and_owner_with_working_tokens(self):
        tokens = self._register("Acme Trading Co", "owner@acme.test")
        self.assertIn("access_token", tokens)
        self.assertIn("refresh_token", tokens)

        me = self.client.get("/auth/me", headers=self._auth_headers(tokens["access_token"]))
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["email"], "owner@acme.test")
        self.assertEqual(me.json()["role"], "owner")

    def test_registering_same_org_name_twice_creates_two_distinct_organizations(self):
        """
        By design, /auth/register never joins an existing org -- letting
        someone "join" a company's org just by typing its name would be a
        security hole. Reusing an organization_name creates a SECOND,
        distinct organization with a disambiguated slug instead. Real
        duplicate-email-within-an-org protection is tested separately via
        the invite endpoint below, which is where it's actually enforced.
        """
        first = self._register("DupeCo", "first@dupe.test")
        second = self.client.post("/auth/register", json={
            "organization_name": "DupeCo",
            "email": "first@dupe.test",  # same email is FINE -- different org
            "password": "Sup3rSecret!",
            "full_name": "Someone Else",
        })
        self.assertEqual(second.status_code, 201, second.text)

        # Confirm they really are two separate organizations, not the same one
        me1 = self.client.get("/auth/me", headers=self._auth_headers(first["access_token"]))
        me2 = self.client.get("/auth/me", headers=self._auth_headers(second.json()["access_token"]))
        self.assertNotEqual(me1.json()["organization_id"], me2.json()["organization_id"])

    def test_inviting_duplicate_email_into_same_org_is_rejected(self):
        """This is where duplicate-email-within-an-org is actually enforced --
        the ADMIN-gated invite endpoint, scoped to a real existing org."""
        owner_tokens = self._register("InviteDupeCo", "owner@invitedupe.test")
        owner_headers = self._auth_headers(owner_tokens["access_token"])

        first_invite = self.client.post("/organizations/members", json={
            "email": "teammate@invitedupe.test", "password": "TeamPass123!", "full_name": "Teammate", "role": "member",
        }, headers=owner_headers)
        self.assertEqual(first_invite.status_code, 201, first_invite.text)

        second_invite = self.client.post("/organizations/members", json={
            "email": "teammate@invitedupe.test", "password": "Different123!", "full_name": "Someone Else", "role": "viewer",
        }, headers=owner_headers)
        self.assertEqual(second_invite.status_code, 409)

    def test_login_with_correct_and_wrong_password(self):
        self._register("LoginTestCo", "user@logintest.test", password="CorrectHorse123!")

        good = self.client.post("/auth/login", json={"email": "user@logintest.test", "password": "CorrectHorse123!"})
        self.assertEqual(good.status_code, 200)

        bad = self.client.post("/auth/login", json={"email": "user@logintest.test", "password": "WrongPassword"})
        self.assertEqual(bad.status_code, 401)

    def test_refresh_token_issues_new_access_token(self):
        tokens = self._register("RefreshCo", "user@refreshtest.test")
        resp = self.client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access_token", resp.json())

    def test_unauthenticated_request_is_rejected(self):
        resp = self.client.get("/products")
        self.assertEqual(resp.status_code, 401)

    def test_owner_can_create_and_list_products(self):
        tokens = self._register("ProductCo", "owner@productco.test")
        headers = self._auth_headers(tokens["access_token"])

        create = self.client.post("/products", json={
            "sku": "DRILL-001", "name": "Cordless Drill", "hts_code": "8467.21.00.10"
        }, headers=headers)
        self.assertEqual(create.status_code, 201, create.text)

        listing = self.client.get("/products", headers=headers)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["count"], 1)

    def test_duplicate_sku_in_same_org_is_rejected(self):
        tokens = self._register("SkuCo", "owner@skuco.test")
        headers = self._auth_headers(tokens["access_token"])
        self.client.post("/products", json={"sku": "X-1", "name": "Widget"}, headers=headers)
        dupe = self.client.post("/products", json={"sku": "X-1", "name": "Widget 2"}, headers=headers)
        self.assertEqual(dupe.status_code, 409)

    def test_organizations_cannot_see_each_others_products(self):
        tokens_a = self._register("OrgA", "owner@orga.test")
        tokens_b = self._register("OrgB", "owner@orgb.test")

        self.client.post("/products", json={"sku": "A-1", "name": "Org A Widget"},
                          headers=self._auth_headers(tokens_a["access_token"]))

        # Org B should see ZERO products, not Org A's
        listing_b = self.client.get("/products", headers=self._auth_headers(tokens_b["access_token"]))
        self.assertEqual(listing_b.json()["count"], 0)

    def test_viewer_cannot_create_products_but_can_list_them(self):
        owner_tokens = self._register("RBACCo", "owner@rbacco.test")
        owner_headers = self._auth_headers(owner_tokens["access_token"])

        invite = self.client.post("/organizations/members", json={
            "email": "viewer@rbacco.test", "password": "ViewerPass123!", "full_name": "Viewer User", "role": "viewer",
        }, headers=owner_headers)
        self.assertEqual(invite.status_code, 201, invite.text)

        viewer_login = self.client.post("/auth/login", json={"email": "viewer@rbacco.test", "password": "ViewerPass123!"})
        viewer_headers = self._auth_headers(viewer_login.json()["access_token"])

        # Viewer CAN list (read-only access)
        listing = self.client.get("/products", headers=viewer_headers)
        self.assertEqual(listing.status_code, 200)

        # Viewer CANNOT create (requires MEMBER+)
        create = self.client.post("/products", json={"sku": "V-1", "name": "Nope"}, headers=viewer_headers)
        self.assertEqual(create.status_code, 403)

    def test_member_can_create_but_not_delete_products(self):
        owner_tokens = self._register("MemberRBACCo", "owner@memberrbac.test")
        owner_headers = self._auth_headers(owner_tokens["access_token"])

        self.client.post("/organizations/members", json={
            "email": "member@memberrbac.test", "password": "MemberPass123!", "full_name": "Member User", "role": "member",
        }, headers=owner_headers)
        member_login = self.client.post("/auth/login", json={"email": "member@memberrbac.test", "password": "MemberPass123!"})
        member_headers = self._auth_headers(member_login.json()["access_token"])

        created = self.client.post("/products", json={"sku": "M-1", "name": "Member Product"}, headers=member_headers)
        self.assertEqual(created.status_code, 201)  # MEMBER can create

        deleted = self.client.delete(f"/products/{created.json()['id']}", headers=member_headers)
        self.assertEqual(deleted.status_code, 403)  # MEMBER cannot delete (requires ADMIN+)

    def test_admin_can_delete_but_only_owner_role_transfer_restriction_applies_to_owner(self):
        owner_tokens = self._register("AdminRBACCo", "owner@adminrbac.test")
        owner_headers = self._auth_headers(owner_tokens["access_token"])

        self.client.post("/organizations/members", json={
            "email": "admin@adminrbac.test", "password": "AdminPass123!", "full_name": "Admin User", "role": "admin",
        }, headers=owner_headers)
        admin_login = self.client.post("/auth/login", json={"email": "admin@adminrbac.test", "password": "AdminPass123!"})
        admin_headers = self._auth_headers(admin_login.json()["access_token"])

        created = self.client.post("/products", json={"sku": "AD-1", "name": "Admin Product"}, headers=owner_headers)
        deleted = self.client.delete(f"/products/{created.json()['id']}", headers=admin_headers)
        self.assertEqual(deleted.status_code, 200)  # ADMIN can delete

    def test_viewer_cannot_invite_members(self):
        owner_tokens = self._register("InviteRBACCo", "owner@inviterbac.test")
        owner_headers = self._auth_headers(owner_tokens["access_token"])
        self.client.post("/organizations/members", json={
            "email": "viewer2@inviterbac.test", "password": "ViewerPass123!", "full_name": "Viewer", "role": "viewer",
        }, headers=owner_headers)
        viewer_login = self.client.post("/auth/login", json={"email": "viewer2@inviterbac.test", "password": "ViewerPass123!"})
        viewer_headers = self._auth_headers(viewer_login.json()["access_token"])

        resp = self.client.post("/organizations/members", json={
            "email": "sneaky@inviterbac.test", "password": "Sneaky123!", "full_name": "Sneaky", "role": "admin",
        }, headers=viewer_headers)
        self.assertEqual(resp.status_code, 403)  # requires ADMIN+, viewer is rejected

    def test_csv_import_creates_multiple_products_and_reports_errors(self):
        tokens = self._register("ImportCo", "owner@importco.test")
        headers = self._auth_headers(tokens["access_token"])

        csv_content = (
            "sku,name,hts_code,duty_rate\n"
            "DRILL-001,Cordless Drill,8467.21.00.10,Free\n"
            "TSHIRT-100,Cotton T-Shirt,6109.10.00.04,16.5%\n"
            "BAD-ROW,,,\n"
        )
        files = {"file": ("products.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        resp = self.client.post("/products/import", files=files, headers=headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        summary = resp.json()
        self.assertEqual(summary["created"], 2)
        self.assertEqual(summary["errors"], 1)

        listing = self.client.get("/products", headers=headers)
        self.assertEqual(listing.json()["count"], 2)

    def test_csv_import_updates_existing_sku_on_second_import(self):
        tokens = self._register("ReimportCo", "owner@reimportco.test")
        headers = self._auth_headers(tokens["access_token"])

        first = "sku,name,duty_rate\nX-1,Original Name,5%\n"
        self.client.post("/products/import", files={"file": ("p.csv", io.BytesIO(first.encode()), "text/csv")}, headers=headers)

        second = "sku,name,duty_rate\nX-1,Updated Name,10%\n"
        resp = self.client.post("/products/import", files={"file": ("p.csv", io.BytesIO(second.encode()), "text/csv")}, headers=headers)
        summary = resp.json()
        self.assertEqual(summary["updated"], 1)
        self.assertEqual(summary["created"], 0)

        listing = self.client.get("/products", headers=headers)
        self.assertEqual(listing.json()["results"][0]["name"], "Updated Name")

    def test_delete_product_and_verify_gone(self):
        tokens = self._register("DeleteCo", "owner@deleteco.test")
        headers = self._auth_headers(tokens["access_token"])
        created = self.client.post("/products", json={"sku": "D-1", "name": "ToDelete"}, headers=headers).json()

        deleted = self.client.delete(f"/products/{created['id']}", headers=headers)
        self.assertEqual(deleted.status_code, 200)

        fetched = self.client.get(f"/products/{created['id']}", headers=headers)
        self.assertEqual(fetched.status_code, 404)


if __name__ == "__main__":
    unittest.main()
