"""The place catalogue behind `GET /places` (rd-be-05).

Three modules, split by what can be wrong with each:

* `catalog` -- seed data. Wrong here means a typo in a demo fixture.
* `scoring` -- deterministic arithmetic over that data. Wrong here means a
  number on screen nobody can reproduce, which the work item exists to prevent.
* `reasons` -- the Gemini call. Wrong here means a sentence that reads well and
  is not true, which is the expensive kind.

Only `reasons` touches the network, and only it can fail in a way the other two
cannot check. That is why it is the one part the route treats as optional.
"""
