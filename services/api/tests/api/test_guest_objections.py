"""The two ways a guest can say "this is wrong".

Spec section 8.6 lists them beside "yes, show me how to transfer":

    [Đúng, xem cách chuyển] · [Số tiền không đúng] · [Tôi không phải Hà]

They shipped as links to routes that did not exist, so a guest who pressed
either one got a 404. The page invited an objection and then behaved as though
objecting had broken something.
"""

from __future__ import annotations

from app.api.limits import OBJECTION_LIMIT

from .helpers import create_batch, propose_and_confirm, publish_batch


def _published_flow(client, repository):
    propose_and_confirm(client)
    batch = create_batch(client, repository)
    published = publish_batch(client, batch["batch_id"])
    return published["guest_links"][0]["path"]


class TestNotMe:
    def test_the_page_loads_instead_of_404(self, client, repository):
        path = _published_flow(client, repository)
        response = client.get(f"{path}/khong-phai-toi")
        assert response.status_code == 200

    def test_it_shows_less_than_the_main_page_never_more(self, client, repository):
        """Somebody who is not the intended reader should leave knowing
        strictly less about this group than when they arrived."""
        path = _published_flow(client, repository)
        body = client.get(f"{path}/khong-phai-toi").text
        assert "82.000" not in body
        assert "Techcombank" not in body

    def test_it_never_asks_the_reader_who_they_are(self, client, repository):
        """The product cannot tell who holds a link. Asking would collect a
        stranger's details for a claim it could not check anyway."""
        path = _published_flow(client, repository)
        body = client.get(f"{path}/khong-phai-toi").text
        assert 'type="text"' not in body
        assert 'type="tel"' not in body
        assert 'type="email"' not in body

    def test_reporting_revokes_the_link(self, client, repository):
        path = _published_flow(client, repository)
        assert client.post(f"{path}/khong-phai-toi").status_code == 200
        assert [o["kind"] for o in repository.objections] == ["not_me"]

    def test_the_obligation_survives_a_revoked_link(self, client, repository):
        """Section 8.2: a dead link does not make a debt disappear."""
        path = _published_flow(client, repository)
        client.post(f"{path}/khong-phai-toi")
        body = client.get(path).text
        assert "vẫn còn" in body
        # repo-guard: allow=long-number reason=synthetic-fixture-never-real-participant-data
        assert "19036812345678" not in body


class TestWrongAmount:
    def test_the_page_loads_instead_of_404(self, client, repository):
        path = _published_flow(client, repository)
        response = client.get(f"{path}/doi-so-tien")
        assert response.status_code == 200

    def test_it_says_missing_evidence_does_not_mean_the_guest_is_wrong(self, client, repository):
        """Section 10.5, said out loud to the person who needs to hear it.

        Someone who believes silence counts against them will pay an amount
        they think is wrong just to end the discomfort.
        """
        path = _published_flow(client, repository)
        body = client.get(f"{path}/doi-so-tien").text
        assert "không</strong> có nghĩa là bạn sai" in body

    def test_it_says_other_obligations_are_unaffected(self, client, repository):
        """Section 8.2: a dispute with Ha must not block the transfer to Nam."""
        path = _published_flow(client, repository)
        body = client.get(f"{path}/doi-so-tien").text
        assert "không bị ảnh hưởng" in body

    def test_it_never_claims_collection_stops(self, client, repository):
        """This test used to assert the opposite, pinning a promise the system
        does not keep: nothing stops collection, and no surface shows the
        objection to whoever recorded the expense. A guest who reads that the
        amount is on hold and is then chased for it is worse off than one who
        was never offered the button."""
        path = _published_flow(client, repository)

        body = client.get(f"{path}/doi-so-tien").text

        assert "tạm dừng" not in body
        assert "chưa tự dừng khoản này" in body
        assert "chưa tự báo cho" in body

    def test_submitting_records_the_reason(self, client, repository):
        path = _published_flow(client, repository)
        page = client.get(f"{path}/doi-so-tien").text
        marker = 'name="obligation_id" value="'
        oid = page.split(marker, 1)[1].split('"', 1)[0]
        response = client.post(
            f"{path}/doi-so-tien",
            data={"obligation_id": oid, "reason": "amount_too_high"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert repository.objections[-1]["reason"] == "amount_too_high"

    def test_an_unknown_reason_is_refused(self, client, repository):
        """A closed list, because free text from a stranger is where the group
        accidentally learns something."""
        path = _published_flow(client, repository)
        page = client.get(f"{path}/doi-so-tien").text
        oid = page.split('name="obligation_id" value="', 1)[1].split('"', 1)[0]
        response = client.post(
            f"{path}/doi-so-tien",
            data={"obligation_id": oid, "reason": "he_is_rude"},
            follow_redirects=False,
        )
        assert response.status_code == 422
        assert repository.objections == []


class TestNoPageClaimsSomeoneWasTold:
    """Objections are append-only audit events. No route, no schema, and no
    screen reads them back, so nobody is notified by anything."""

    def test_not_me_does_not_claim_the_recorder_was_told(self, client, repository):
        path = _published_flow(client, repository)

        # Read the POST response, not a later GET: objecting revokes the link,
        # and a revoked link must refuse to render.
        body = client.post(f"{path}/khong-phai-toi").text

        assert "đã được báo" not in body
        assert "chưa tự báo cho" in body

    def test_evidence_request_does_not_claim_anyone_was_asked(self, client, repository):
        path = _published_flow(client, repository)
        oid = _oid(client, path)
        client.post(f"{path}/xin-cach-tinh", data={"obligation_id": oid},
                    follow_redirects=False)

        body = client.get(f"{path}/doi-so-tien?obligation_id={oid}").text

        assert "Đã hỏi" not in body
        assert "chưa tự chuyển tới" in body


class TestEvidenceRequest:
    def test_asking_is_all_it_does(self, client, repository):
        path = _published_flow(client, repository)
        page = client.get(f"{path}/doi-so-tien").text
        oid = page.split('name="obligation_id" value="', 1)[1].split('"', 1)[0]
        response = client.post(
            f"{path}/xin-cach-tinh", data={"obligation_id": oid}, follow_redirects=False
        )
        assert response.status_code == 303
        assert repository.objections[-1]["kind"] == "evidence_request"


def _oid(client, path):
    page = client.get(f"{path}/doi-so-tien").text
    return page.split('name="obligation_id" value="', 1)[1].split('"', 1)[0]


class TestTheLinkIsTheOnlyAuthority:
    """A guest link is a capability. It covers the obligations in its own
    envelope and nothing else."""

    def test_an_obligation_from_someone_elses_link_is_refused(self, client, repository):
        path = _published_flow(client, repository)

        response = client.post(
            f"{path}/doi-so-tien",
            data={
                "obligation_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "reason": "amount_too_high",
            },
            follow_redirects=False,
        )

        assert response.status_code == 404
        assert repository.objections == []

    def test_asking_for_evidence_is_scoped_the_same_way(self, client, repository):
        path = _published_flow(client, repository)

        response = client.post(
            f"{path}/xin-cach-tinh",
            data={"obligation_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"},
            follow_redirects=False,
        )

        assert response.status_code == 404
        assert repository.objections == []


class TestQuota:
    def test_objecting_more_than_the_limit_is_refused(self, client, repository):
        path = _published_flow(client, repository)
        oid = _oid(client, path)

        for _ in range(OBJECTION_LIMIT):
            accepted = client.post(
                f"{path}/doi-so-tien",
                data={"obligation_id": oid, "reason": "amount_too_high"},
                follow_redirects=False,
            )
            assert accepted.status_code == 303

        refused = client.post(
            f"{path}/doi-so-tien",
            data={"obligation_id": oid, "reason": "amount_too_high"},
            follow_redirects=False,
        )

        assert refused.status_code == 429
        assert len(repository.objections) == OBJECTION_LIMIT

    def test_asking_how_a_number_was_reached_does_not_spend_the_quota(
        self, client, repository
    ):
        """Charging someone for asking is how a group learns not to ask."""
        path = _published_flow(client, repository)
        oid = _oid(client, path)

        for _ in range(OBJECTION_LIMIT + 2):
            asked = client.post(
                f"{path}/xin-cach-tinh",
                data={"obligation_id": oid},
                follow_redirects=False,
            )
            assert asked.status_code == 303

        still_allowed = client.post(
            f"{path}/doi-so-tien",
            data={"obligation_id": oid, "reason": "amount_too_high"},
            follow_redirects=False,
        )

        assert still_allowed.status_code == 303


class TestTheRealRepositoryCanActuallyStoreOne:
    def test_the_concrete_class_implements_it(self):
        """The implementation was written inside the Protocol, where nothing
        calls it, leaving the concrete class without the method at all. Every
        test passed, because they all run against the fake."""
        import inspect

        from app.api.repository import ApiRepository, SqlAlchemyApiRepository

        assert hasattr(SqlAlchemyApiRepository, "save_guest_objection")
        assert "session" in inspect.getsource(
            SqlAlchemyApiRepository.save_guest_objection
        )
        assert "session" not in inspect.getsource(ApiRepository.save_guest_objection)
