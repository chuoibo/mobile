"""The two ways a guest can say "this is wrong".

Spec section 8.6 lists them beside "yes, show me how to transfer":

    [Đúng, xem cách chuyển] · [Số tiền không đúng] · [Tôi không phải Hà]

They shipped as links to routes that did not exist, so a guest who pressed
either one got a 404. The page invited an objection and then behaved as though
objecting had broken something.
"""

from __future__ import annotations

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

    def test_it_says_only_this_obligation_stops(self, client, repository):
        """Section 8.2: a dispute with Ha must not block the transfer to Nam."""
        path = _published_flow(client, repository)
        body = client.get(f"{path}/doi-so-tien").text
        assert "Chỉ khoản này tạm dừng" in body

    def test_submitting_records_the_reason(self, client, repository):
        path = _published_flow(client, repository)
        view = client.get(path).json() if "json" in path else None
        del view
        obligation_id = repository.objections and None
        del obligation_id
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
