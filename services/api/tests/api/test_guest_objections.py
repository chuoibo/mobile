"""The two ways a guest can say "this is wrong".

Spec section 8.6 lists them beside "yes, show me how to transfer":

    [Đúng, xem cách chuyển] · [Số tiền không đúng] · [Tôi không phải Hà]

They shipped as links to routes that did not exist, so a guest who pressed
either one got a 404. The page invited an objection and then behaved as though
objecting had broken something.
"""

from __future__ import annotations

import uuid

import pytest

from app.api.limits import OBJECTION_LIMIT

from .helpers import (
    ADVANCER_ID,
    OTHER_ID,
    SENDER_ID,
    actor_headers,
    create_batch,
    join_group,
    propose_and_confirm,
    publish_batch,
)


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

    def test_it_describes_what_actually_happens_to_the_obligation(
        self, client, repository
    ):
        """This assertion has now been rewritten three times, each time
        following the behaviour rather than leading it.

        It first claimed collection stopped, when nothing stopped it. It then
        asserted the page admits nothing stops -- honest, but that pinned the
        missing behaviour in place, which is how a test stops guarding a
        promise and starts guarding a gap. It then said "dừng thu", which was
        true while a dispute was one of the payment statuses.

        Payment and disagreement are separate facts now, so "dừng thu" is the
        wrong sentence: on a debt already paid there is nothing to stop, and
        saying so anyway is a promise nobody kept. What is true in every case
        is that the obligation is marked, and stops counting as owed."""
        path = _published_flow(client, repository)

        # Whitespace-normalised: the template wraps its prose, so a phrase can
        # be split across lines. Asserting on the raw HTML would make this a
        # test about line breaks rather than about what the page says.
        body = " ".join(client.get(f"{path}/doi-so-tien").text.split())

        assert "đang thắc mắc" in body
        assert "không bị tính là còn nợ" in body
        assert "không bị ảnh hưởng" in body

    def test_it_still_never_claims_anyone_was_notified(self, client, repository):
        """Appearing on a board is not the same as somebody having looked.

        The page may now say collection stopped, because it does. It must not
        slide from there into saying the person was told."""
        path = _published_flow(client, repository)

        body = client.get(f"{path}/doi-so-tien").text

        assert "chưa" in body and "tự nhắn" in body
        for lie in ("đã được báo", "đã báo cho", "đã thông báo"):
            assert lie not in body

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


class TestADisputeStopsExactlyOneObligation:
    """Section 8.2, and the whole point of PR11-01.

    A guest could file "this amount is wrong", be told truthfully that it was
    recorded, and every collection path carried on as though nothing had
    happened -- because the objection was an audit event no surface read back.
    These go through the collection board, which is the surface that was
    missing.
    """

    @staticmethod
    def _board(client, batch_id):
        response = client.get(
            f"/batches/{batch_id}/obligations", headers=actor_headers()
        )
        assert response.status_code == 200, response.text
        return response.json()

    def test_the_objected_obligation_becomes_disputed(self, client, repository):
        propose_and_confirm(client)
        batch = create_batch(client, repository)
        published = publish_batch(client, batch["batch_id"])
        path = published["guest_links"][0]["path"]

        before = self._board(client, batch["batch_id"])
        assert before["disputed_count"] == 0
        target = before["obligations"][0]["obligation_id"]

        client.post(
            f"{path}/doi-so-tien",
            data={"obligation_id": target, "reason": "amount_too_high"},
            follow_redirects=False,
        )

        after = self._board(client, batch["batch_id"])
        rows = {row["obligation_id"]: row for row in after["obligations"]}
        assert rows[target]["disputed"] is True
        assert rows[target]["disputed_reason"] == "amount_too_high"
        assert after["disputed_count"] == 1
        # The payment status is a separate fact and is unchanged: nobody has
        # sent or received anything by objecting.
        assert rows[target]["obligation_status"] == "outstanding"

    def test_every_other_obligation_is_untouched(self, client, repository):
        # Three participants, so two people owe the advancer and the batch has
        # two obligations on two separate links. With one obligation there is
        # nothing for a stray dispute to spill onto and the test proves nothing.
        join_group(repository, OTHER_ID)
        propose_and_confirm(
            client, total=90_000, participants=[SENDER_ID, OTHER_ID, ADVANCER_ID]
        )
        batch = create_batch(client, repository)
        published = publish_batch(client, batch["batch_id"])
        path = published["guest_links"][0]["path"]

        before = self._board(client, batch["batch_id"])
        assert len(before["obligations"]) >= 2, "fixture stopped producing two obligations"
        target = before["obligations"][0]["obligation_id"]
        others = [row["obligation_id"] for row in before["obligations"][1:]]

        client.post(
            f"{path}/doi-so-tien",
            data={"obligation_id": target, "reason": "amount_too_high"},
            follow_redirects=False,
        )

        rows = {
            row["obligation_id"]: row
            for row in self._board(client, batch["batch_id"])["obligations"]
        }
        assert rows[target]["disputed"] is True
        for other in others:
            assert rows[other]["disputed"] is False, (
                "one objection stopped a different person's obligation"
            )

    def test_an_unknown_batch_is_404_not_an_empty_board(self, client, repository):
        """An empty list would read as "nothing to collect" for a batch that
        does not exist -- a quiet answer to a wrong question."""
        response = client.get(
            f"/batches/{uuid.uuid4()}/obligations", headers=actor_headers()
        )
        assert response.status_code == 404


class TestAskingHowANumberWasReachedIsNotAnObjection:
    """PR11-02. The repository said asking does not spend the quota, the
    comment beside it said so too, and the service checked the quota before it
    looked at the kind -- so a guest who had objected three times got 429 for
    asking a question the code claimed was free."""

    def test_evidence_request_survives_an_exhausted_objection_quota(
        self, client, repository
    ):
        propose_and_confirm(client)
        batch = create_batch(client, repository)
        published = publish_batch(client, batch["batch_id"])
        path = published["guest_links"][0]["path"]
        board = client.get(
            f"/batches/{batch['batch_id']}/obligations", headers=actor_headers()
        ).json()
        target = board["obligations"][0]["obligation_id"]

        for _ in range(OBJECTION_LIMIT):
            client.post(
                f"{path}/doi-so-tien",
                data={"obligation_id": target, "reason": "amount_too_high"},
                follow_redirects=False,
            )

        response = client.post(
            f"{path}/xin-cach-tinh",
            data={"obligation_id": target},
            follow_redirects=False,
        )

        assert response.status_code != 429, response.text


class TestTheCollectionBoardIsNotPublic:
    """QA called this endpoint as a stranger and read the whole batch.

    The service took an `actor` argument and never looked at it, so any valid
    actor header plus a batch id returned every sender, every recipient, every
    amount, and the private reason a guest gave for objecting. The parameter
    being there is what made it look checked.
    """

    @staticmethod
    def _batch(client, repository):
        propose_and_confirm(client)
        batch = create_batch(client, repository)
        publish_batch(client, batch["batch_id"])
        return batch["batch_id"]

    def test_a_member_of_the_group_can_read_it(self, client, repository):
        batch_id = self._batch(client, repository)
        response = client.get(
            f"/batches/{batch_id}/obligations", headers=actor_headers()
        )
        assert response.status_code == 200, response.text

    def test_somebody_from_another_group_cannot(self, client, repository):
        batch_id = self._batch(client, repository)
        outsider = {
            "X-Actor-ID": str(uuid.uuid4()),
            "X-Actor-Roles": "member",
            "X-Actor-Contexts": str(uuid.uuid4()),
        }

        response = client.get(f"/batches/{batch_id}/obligations", headers=outsider)

        assert response.status_code == 403, response.text
        # And nothing leaks in the refusal itself.
        for leaked in ("amount_vnd", "sender_id", "disputed_reason"):
            assert leaked not in response.text

    def test_an_actor_with_no_context_at_all_cannot(self, client, repository):
        batch_id = self._batch(client, repository)
        response = client.get(
            f"/batches/{batch_id}/obligations",
            headers={"X-Actor-ID": str(uuid.uuid4()), "X-Actor-Roles": "member"},
        )
        assert response.status_code == 403, response.text

    def test_no_actor_header_is_refused_before_anything_is_read(
        self, client, repository
    ):
        batch_id = self._batch(client, repository)
        response = client.get(f"/batches/{batch_id}/obligations")
        assert response.status_code == 401, response.text


class TestAReceiptCannotCloseAnArgument:
    """Both of these were found by QA attacking a rule I wrote myself.

    The rule was "money that already arrived outranks a dispute", with
    `disputed` folded into `obligation_status`. It broke from both directions
    within an hour, and both breaks had the same shape: the person a guest is
    objecting to could make the objection disappear, or prevent it existing,
    with a click that belongs to them.
    """

    @staticmethod
    def _board(client, batch_id):
        response = client.get(
            f"/batches/{batch_id}/obligations", headers=actor_headers()
        )
        assert response.status_code == 200, response.text
        return response.json()

    @staticmethod
    def _published(client, repository):
        propose_and_confirm(client)
        batch = create_batch(client, repository)
        published = publish_batch(client, batch["batch_id"])
        return batch["batch_id"], published["guest_links"][0]["path"]

    def _confirm_full_receipt(self, client, obligation_id, amount_vnd):
        return client.post(
            f"/obligations/{obligation_id}/confirm-receipt",
            headers=actor_headers(),
            json={"amount_vnd": amount_vnd, "idempotency_key": str(uuid.uuid4())},
        )

    def test_the_recipient_cannot_erase_a_dispute_by_confirming_receipt(
        self, client, repository
    ):
        """QA finding 2. The recipient is the party being objected to, and
        confirming receipt is their click. If it cleared the objection, an
        argument would end whenever the person on the other side of it said so.
        """
        batch_id, path = self._published(client, repository)
        row = self._board(client, batch_id)["obligations"][0]

        client.post(
            f"{path}/doi-so-tien",
            data={"obligation_id": row["obligation_id"], "reason": "amount_too_high"},
            follow_redirects=False,
        )
        assert self._board(client, batch_id)["disputed_count"] == 1

        self._confirm_full_receipt(client, row["obligation_id"], row["amount_vnd"])

        after = self._board(client, batch_id)
        target = [
            item
            for item in after["obligations"]
            if item["obligation_id"] == row["obligation_id"]
        ][0]
        assert target["obligation_status"] == "confirmed", "the money did arrive"
        assert target["disputed"] is True, "confirming receipt erased the objection"
        assert after["disputed_count"] == 1

    def test_a_guest_can_still_object_after_a_mistaken_confirmation(
        self, client, repository
    ):
        """QA finding 3. A recipient can confirm the wrong obligation. If that
        locked the guest out of objecting, the only person who could report the
        mistake would be the person who made it."""
        batch_id, path = self._published(client, repository)
        row = self._board(client, batch_id)["obligations"][0]

        self._confirm_full_receipt(client, row["obligation_id"], row["amount_vnd"])
        assert self._board(client, batch_id)["disputed_count"] == 0

        client.post(
            f"{path}/doi-so-tien",
            data={"obligation_id": row["obligation_id"], "reason": "already_paid"},
            follow_redirects=False,
        )

        after = self._board(client, batch_id)
        target = [
            item
            for item in after["obligations"]
            if item["obligation_id"] == row["obligation_id"]
        ][0]
        assert target["disputed"] is True, "a guest was locked out of objecting"
        assert target["disputed_reason"] == "already_paid"
        assert after["disputed_count"] == 1


class TestObjectingOnALinkWithTwoDebts:
    """QA found the third way to break this, and it was the worst one.

    The "wrong amount" link carried no obligation id, so the route fell back
    to the first block. On a link with two debts, pressing the button under
    the second card raised an objection against the FIRST -- flagging money
    owed to one person because somebody disagreed about money owed to another,
    while leaving the real one unobjectable.
    """

    @staticmethod
    def _two_debt_link(client, repository):
        join_group(repository, OTHER_ID)
        propose_and_confirm(
            client, total=90_000, participants=[SENDER_ID, OTHER_ID, ADVANCER_ID]
        )
        batch = create_batch(client, repository)
        published = publish_batch(client, batch["batch_id"])
        return batch["batch_id"], published["guest_links"]

    def test_every_objection_link_names_its_own_obligation(self, client, repository):
        _, links = self._two_debt_link(client, repository)
        body = client.get(links[0]["path"]).text

        # One link per obligation on the page, each carrying its own id.
        assert "doi-so-tien?obligation_id=" in body, (
            "the objection link does not say which debt it is about"
        )
        assert body.count("/doi-so-tien\"") == 0, (
            "an objection link with no obligation id would fall back to the first"
        )

    def test_objecting_from_the_second_card_does_not_flag_the_first(
        self, client, repository
    ):
        batch_id, links = self._two_debt_link(client, repository)
        board = client.get(
            f"/batches/{batch_id}/obligations", headers=actor_headers()
        ).json()
        if len(board["obligations"]) < 2:
            raise AssertionError("fixture stopped producing two obligations")

        # Object about the SECOND obligation, naming it explicitly.
        second = board["obligations"][1]["obligation_id"]
        first = board["obligations"][0]["obligation_id"]
        target_link = next(
            link
            for link in links
            if second in client.get(link["path"]).text
        )
        client.post(
            f"{target_link['path']}/doi-so-tien",
            data={"obligation_id": second, "reason": "amount_too_high"},
            follow_redirects=False,
        )

        after = {
            row["obligation_id"]: row
            for row in client.get(
                f"/batches/{batch_id}/obligations", headers=actor_headers()
            ).json()["obligations"]
        }
        assert after[second]["disputed"] is True
        assert after[first]["disputed"] is False, (
            "objecting about one debt flagged a different person's debt"
        )


class TestAClosedLinkIsClosedInBothDirections:
    """QA finding 3. GET refused on a revoked link; POST did not.

    So a guest who had shut their own link down by pressing "I am not this
    person" could still file objections by submitting the form directly.
    """

    def test_posting_to_a_revoked_link_is_refused(self, client, repository):
        propose_and_confirm(client)
        batch = create_batch(client, repository)
        published = publish_batch(client, batch["batch_id"])
        path = published["guest_links"][0]["path"]
        board = client.get(
            f"/batches/{batch['batch_id']}/obligations", headers=actor_headers()
        ).json()
        target = board["obligations"][0]["obligation_id"]

        # "Tôi không phải người này" revokes the link.
        client.post(f"{path}/khong-phai-toi", data={}, follow_redirects=False)

        response = client.post(
            f"{path}/doi-so-tien",
            data={"obligation_id": target, "reason": "amount_too_high"},
            follow_redirects=False,
        )
        assert response.status_code == 409, response.text

        after = client.get(
            f"/batches/{batch['batch_id']}/obligations", headers=actor_headers()
        ).json()
        assert after["disputed_count"] == 0, "a closed link still filed an objection"
