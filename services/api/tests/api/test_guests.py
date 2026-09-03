"""GET /g/{token} and POST /g/{token}/da-chuyen."""

from __future__ import annotations

from .helpers import create_batch, propose_and_confirm, publish_batch


def _published_flow(client, repository):
    propose_and_confirm(client)
    batch = create_batch(client, repository)
    published = publish_batch(client, batch["batch_id"])
    return batch, published["guest_links"][0]["path"]


def test_guest_route_renders_only_closed_guest_view(client, repository):
    _, path = _published_flow(client, repository)

    response = client.get(path)

    assert response.status_code == 200
    assert "Chỉ hiển thị phần của bạn" in response.text
    # The page names who is owed, from `people`. It used to name the holder of
    # a bank account instead, which is what a bank prints rather than what the
    # group calls somebody.
    assert "Nam" in response.text
    assert "RuDi chỉ tính phần của bạn" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_raw_group_data_is_rejected_before_template_render(client, repository):
    _, path = _published_flow(client, repository)
    repository.leak_guest_input = True

    response = client.get(path)

    assert response.status_code == 409
    assert response.json()["code"] == "FORBIDDEN_FIELD_IN_INPUT"
    assert "someone_else" not in response.text


def test_sender_self_report_is_an_event_and_never_closes_obligation(client, repository):
    batch, path = _published_flow(client, repository)
    obligation_id = batch["obligations"][0]["obligation_id"]

    response = client.post(path + "/da-chuyen", data={"obligation_id": obligation_id})

    assert response.status_code == 201
    assert response.json()["obligation_status"] == "outstanding"
    assert len(repository.reports) == 1
    assert repository.receipts == {}
    page = client.get(path)
    assert "Đang chờ Nam xác nhận" in page.text


def test_browser_payment_form_uses_post_redirect_get(client, repository):
    batch, path = _published_flow(client, repository)
    obligation_id = batch["obligations"][0]["obligation_id"]

    response = client.post(
        path + "/da-chuyen",
        headers={"Accept": "text/html"},
        data={"obligation_id": obligation_id},
    )

    assert response.status_code == 303
    assert response.headers["location"] == path
    assert len(repository.reports) == 1


def test_guest_link_cannot_report_an_obligation_outside_its_scope(client, repository):
    batch, path = _published_flow(client, repository)
    del batch

    response = client.post(
        path + "/da-chuyen",
        data={"obligation_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"},
    )

    assert response.status_code == 404
    assert repository.reports == {}
