"""The Gemini half: a real model, asked an open question, checked before it ships.

Two failure modes are designed against here, and they are not the same failure.

**Leading the witness.** Ask a model "explain why this place suits the group"
and it will always find a reason -- including for the 450k rooftop 5.2km away
that the group of six cannot afford and does not want. The answer was inside
the question. So this module does three things instead:

* the prompt asks *whether* it fits, not why it fits;
* the model must return a `verdict` from a closed set that includes
  `khong-hop`, so refusing is a first-class answer and not an act of defiance;
* **the computed score is never sent.** The route knows the place scored 41,
  the model does not. If the score went into the prompt the reason would be a
  rationalisation of a number this file already had, and the two would agree by
  construction rather than by observation.

The prompt also says out loud that the list is unfiltered and that all-`hop`
is a sign of flattery. That line is there because it is cheaper than
discovering the same thing from a demo audience.

**Fabrication that reads well.** "Quán nổi tiếng với món bò nướng lá lốt và
từng lên báo năm 2023" is a fluent sentence about a place that does not exist.
`ungrounded_numbers` is a deterministic, non-LLM gate: every number in the
reason has to be traceable to the row the model was given. A reason that fails
it is dropped, and the place falls back to a score with no AI label. Cheap,
checkable in a unit test, no second model in the loop to also be wrong.

The gate catches invented *numbers*, which is the fabrication that does
concrete damage on a screen about money. It does not catch an invented
adjective, and this docstring is the wrong place to pretend otherwise.

**Collateral damage.** Both gates above drop one place and leave the rest
alone, which is only worth anything if the batch survives long enough to reach
them. It did not: the model quotes a trait inside a reason string without
escaping the quote marks in roughly one call in ten, and `json.loads` on the
whole array used to turn that into twelve cards with no AI label. Decoding is
therefore item-by-item on the recovery path -- see `_salvage_objects`. Every
drop in this module costs exactly the row that earned it.

Key handling: `GEMINI_API_KEY` travels in a header, never in a URL, and is
never logged, echoed, or put in an exception message. Failures report the HTTP
status and the exception type -- nothing that could carry the key or the
response body.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Literal

from app.places.catalog import GroupProfile

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
GEMINI_TIMEOUT_SECONDS = 60

Verdict = Literal["hop", "tam", "khong-hop"]
VERDICTS: tuple[Verdict, ...] = ("hop", "tam", "khong-hop")


@dataclass(frozen=True, slots=True)
class ReasonRow:
    """One place put to the model.

    Carries the place and nothing else. There is no `score` field, and that
    absence is the anti-anchoring rule made structural rather than remembered:
    a future edit cannot casually add the answer to the question without
    changing this class first.
    """

    place: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PlaceReason:
    verdict: Verdict
    reason: str


def _k(vnd: int) -> int:
    return vnd // 1000


def build_prompt(rows: list[ReasonRow], group: GroupProfile) -> str:
    """The open question.

    Read the negative instructions as the specification: each one is a way the
    output has been observed to go wrong when the instruction is absent.
    """

    lines = [
        "Bạn giúp một nhóm bạn Việt Nam quyết định nên đi đâu. Viết tiếng Việt tự nhiên.",
        "",
        "Hồ sơ nhóm:",
        f"- {group['size']} người, {group['age_range']} tuổi",
        f"- Ngân sách mỗi người khoảng {_k(group['budget_per_person_vnd'])}k",
        f"- Nhóm thích: {', '.join(group['likes'])}",
        f"- Không muốn đi xa quá {group['max_distance_km']}km",
        f"- Thời điểm: {group['when']}",
        "",
        "Dưới đây là danh sách địa điểm ở dạng JSON. Với MỖI địa điểm, tự đánh giá",
        "xem nó CÓ HỢP với nhóm này không, rồi viết 1-2 câu nói rõ kết luận đó.",
        "",
        "Điều quan trọng nhất:",
        '- Câu hỏi là "chỗ này có hợp không". KHÔNG phải "hãy khen chỗ này".',
        "- Danh sách này CHƯA được lọc. Trong đó có chỗ hợp và có chỗ không hợp.",
        '  Nếu bạn trả về toàn "hop", đó là dấu hiệu bạn đang chiều người hỏi',
        "  chứ không đọc dữ liệu.",
        '- Chỗ nào không hợp thì trả "khong-hop" và nói thẳng vướng ở đâu',
        "  (quá tiền, quá xa, quá nhỏ so với nhóm, sai kiểu nhóm thích).",
        "",
        "Luật về dữ kiện:",
        "- Chỉ dùng con số và dữ kiện có trong dòng của chính địa điểm đó và trong",
        "  hồ sơ nhóm ở trên. Không thêm món ăn, giải thưởng, bài báo, sự kiện,",
        "  tên người, hay bất kỳ chi tiết nào không được cho.",
        "- Nêu số cụ thể (khoảng giá, khoảng cách, số người) khi nó chính là lý do.",
        "- Đừng nhắc tới điểm số hay phần trăm; bạn không được cho con số đó.",
        '- Không xưng "tôi", không chào hỏi, không emoji.',
        "",
        'Trả về JSON: mảng các object {"id": ..., "verdict": ..., "reason": ...}.',
        'verdict là một trong "hop", "tam", "khong-hop".',
        "",
        "Địa điểm:",
    ]
    for row in rows:
        place = row.place
        fit = place.get("group_fit") or {}
        lines.append(
            json.dumps(
                {
                    "id": place["id"],
                    "ten": place["name"],
                    "loai": place["kinds"],
                    "khoang_gia_moi_nguoi": _khoang_gia(place),
                    "dac_diem": place["traits"],
                    "khoang_cach_km": place["distance_km"],
                    "so_nguoi_hop": (
                        f"{fit.get('min_people')}-{fit.get('max_people')}"
                        if fit
                        else "không ghi"
                    ),
                    "dang_mo": place["open_now"],
                    "gio_mo": place["open_hours"],
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Grounding gate
# ---------------------------------------------------------------------------

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def _candidate_values(token: str) -> set[Fraction]:
    """Every reading of a numeric token a Vietnamese sentence could intend.

    "250.000" is two hundred fifty thousand to a Vietnamese reader and two
    hundred fifty to `Fraction`. Both readings are offered, and the token is
    grounded if *either* matches a real figure. Being generous here is correct:
    a false rejection silently drops a good reason, and this gate exists to
    catch invented facts, not to police punctuation.
    """

    values: set[Fraction] = set()
    plain = token.replace(",", ".")
    try:
        values.add(Fraction(plain))
    except (ValueError, ZeroDivisionError):
        pass
    # Thousands separators: 250.000 / 1.234.567 / 250,000
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", token):
        try:
            values.add(Fraction(re.sub(r"[.,]", "", token)))
        except ValueError:
            pass
    return values


def _khoang_gia(place: dict[str, Any]) -> str:
    """The price band as the prompt shows it, or the words «chưa có».

    Never a formatted `None`: a model shown «None-Nonek» will write a sentence
    about it.
    """

    low = place.get("price_min_vnd")
    high = place.get("price_max_vnd")
    if low is None or high is None:
        return "chưa có"
    return f"{_k(low)}-{_k(high)}k"


def allowed_numbers(place: dict[str, Any], group: GroupProfile) -> set[Fraction]:
    """Every figure the model was actually shown, in every unit it might quote.

    A field the row does not have contributes nothing -- which makes the gate
    STRICTER for an imported place, not looser: a price the model quotes for a
    place with no price is a number it invented, and there is now no entry in
    this set for it to match.
    """

    fit = place.get("group_fit") or {}
    low = place.get("price_min_vnd")
    high = place.get("price_max_vnd")
    raw: list[float | int | None] = [
        low,
        high,
        None if low is None else _k(low),
        None if high is None else _k(high),
        None if low is None or high is None else (low + high) // 2,
        None if low is None or high is None else _k((low + high) // 2),
        place.get("distance_km"),
        place.get("travel_minutes"),
        place.get("rating"),
        place.get("rating_count"),
        place.get("photo_count"),
        group["size"],
        group["budget_per_person_vnd"],
        _k(group["budget_per_person_vnd"]),
        group["max_distance_km"],
    ]
    if fit:
        raw.extend([fit["min_people"], fit["max_people"]])

    values = {Fraction(str(value)) for value in raw if value is not None}
    # Opening hours, the age band and the street number all appear verbatim in
    # the row, so a reason quoting them is quoting given data.
    for text in (place.get("open_hours"), group["age_range"], place.get("address")):
        if not text:
            continue
        for token in _NUMBER.findall(text):
            values |= _candidate_values(token)
    return values


def ungrounded_numbers(
    reason: str, place: dict[str, Any], group: GroupProfile
) -> list[str]:
    """Numeric tokens in the reason that trace back to nothing the model was given.

    Non-empty means the sentence asserts a figure out of thin air, and the
    caller drops it rather than serving it under an `ai` label.
    """

    permitted = allowed_numbers(place, group)
    stray = []
    for token in _NUMBER.findall(reason):
        if not (_candidate_values(token) & permitted):
            stray.append(token)
    return stray


# How many `{` that fail to decode we are willing to step over before giving
# up on a document. Bounds the rescan on a response that is not really a list
# of items at all; a genuine batch misses once per broken reason.
_MAX_SALVAGE_MISSES = 32


def _salvage_objects(text: str) -> list[Any]:
    """Top-level JSON objects still readable in a document that will not parse.

    Measured, not hypothetical: over 23 real calls, 3 came back with a trait
    quoted inside a reason string and the quote marks left unescaped --

        "reason": "Quán cafe này có đặc điểm "yên tĩnh" không phù hợp..."

    -- with `finishReason: STOP` and a well-formed closing `]`. Not truncation,
    just one bad string. `json.loads` on the whole array dies at that quote,
    which used to take the eleven well-formed siblings down with it and leave
    the screen with no AI label on any card.

    So each object is decoded on its own terms with `raw_decode`, and a failure
    resynchronises at the next `{` instead of ending the document. This is a
    *recovery* path, not a lenient parser: every object it returns still goes
    through the same field, verdict and grounding checks as one that arrived in
    a clean batch. Nothing is repaired or guessed at -- an item that will not
    decode is dropped, and only that item.
    """

    decoder = json.JSONDecoder()
    found: list[Any] = []
    misses = 0
    at = 0
    while misses <= _MAX_SALVAGE_MISSES:
        start = text.find("{", at)
        if start < 0:
            break
        try:
            obj, end = decoder.raw_decode(text, start)
        except ValueError:
            misses += 1
            at = start + 1
            continue
        found.append(obj)
        at = end
    return found


def parse_reasons(
    text: str, rows: list[ReasonRow], group: GroupProfile
) -> dict[str, PlaceReason]:
    """Model output to `{place_id: PlaceReason}`, dropping anything unusable.

    Silently lossy on purpose. A row the model skipped, mislabelled, or made up
    a number for simply does not get an AI reason; it does not get a
    substituted one, and it does not take the other eleven down with it.

    That last clause used to be true per *item* and false per *batch*: a single
    unescaped quote anywhere in the array cost every reason in it. The strict
    whole-document parse is still tried first and still owns the happy path;
    only when it raises does `_salvage_objects` pick the readable items back
    out, and they face exactly the same checks either way.
    """

    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError:
        parsed = _salvage_objects(text)
        if not parsed:
            logger.warning("Gemini places: response was not JSON")
            return {}
        # Counts only. The response body can carry model text and is never
        # logged, on the same rule that keeps the key out of the logs.
        logger.warning(
            "Gemini places: response was not valid JSON, recovered %d item(s) of %d asked",
            len(parsed),
            len(rows),
        )
    if not isinstance(parsed, list):
        logger.warning("Gemini places: response was not a JSON array")
        return {}

    by_id = {row.place["id"]: row.place for row in rows}
    out: dict[str, PlaceReason] = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        place_id = item.get("id")
        place = by_id.get(place_id) if isinstance(place_id, str) else None
        if place is None:
            # A place id nobody asked about. Hallucinated rows are dropped
            # rather than served: there is no row to check them against.
            continue
        verdict = item.get("verdict")
        reason = item.get("reason")
        if verdict not in VERDICTS or not isinstance(reason, str) or not reason.strip():
            continue
        reason = reason.strip()
        stray = ungrounded_numbers(reason, place, group)
        if stray:
            logger.warning(
                "Gemini places: dropped reason for %s, ungrounded figures %s",
                place_id,
                stray,
            )
            continue
        out[place_id] = PlaceReason(verdict=verdict, reason=reason)
    return out


# ---------------------------------------------------------------------------
# The call
# ---------------------------------------------------------------------------


def _post(prompt: str, api_key: str) -> str | None:
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            # Production temperature, and the tests assert against this value
            # rather than dropping to 0 to make a run reproducible. A reason
            # written at 0.4 is the reason a person will read.
            "temperature": 0.4,
            "responseMimeType": "application/json",
        },
    }
    request = urllib.request.Request(
        GEMINI_ENDPOINT.format(model=GEMINI_MODEL),
        data=json.dumps(body).encode("utf-8"),
        # Header, not query string: a key in a URL ends up in access logs,
        # proxy logs and exception messages that quote the URL.
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request, timeout=GEMINI_TIMEOUT_SECONDS
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        # Status only. The error body can echo request detail back, so it is
        # not read and not logged.
        logger.warning("Gemini places: HTTP %s", error.code)
        return None
    except Exception as error:  # noqa: BLE001 - a catalogue must not 500 on this
        logger.warning("Gemini places: call failed (%s)", type(error).__name__)
        return None

    try:
        return payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        logger.warning("Gemini places: unexpected response shape")
        return None


def gemini_reasons(
    rows: list[ReasonRow], group: GroupProfile
) -> dict[str, PlaceReason]:
    """One batched call for the whole catalogue. Never raises.

    Returning `{}` is a valid, honest outcome: the route then serves scores
    with no AI label, which is what the screen is built to show when the model
    could not be reached.
    """

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.info("Gemini places: GEMINI_API_KEY not set, serving scores only")
        return {}
    if not rows:
        return {}

    text = _post(build_prompt(rows, group), api_key)
    if text is None:
        return {}
    return parse_reasons(text, rows, group)
