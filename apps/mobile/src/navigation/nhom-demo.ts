/** The demo group the opening screen signs you in as.
 *
 * There is no OAuth here and there is not going to be one before the deadline.
 * Google and Apple sign-in are a console project, a redirect scheme, a consent
 * screen and a native rebuild each, and none of that is visible in the thing
 * being demonstrated: the person watching sees a name appear. So the buttons
 * are drawn to spec and pressing one picks a member of this group instead.
 *
 * That trade is only acceptable while it is *stated*, so it is stated in three
 * places that cannot drift apart from the code: the sheet's own heading, the
 * caption under the buttons, and the PR description. A shell is not a defect.
 * A shell that presents itself as working is.
 *
 * Names match `scripts/seed_demo_data.py` ("Team Đà Lạt") so the person picked
 * here is a person the seeded database has actually heard of.
 *
 * `personId` is the row in the seeded database, and it arrived with the Cá
 * nhân screen -- the first screen that sends a real request on this person's
 * behalf, which this file's earlier note predicted would be the one to need
 * it. Before that, nothing here wrote or read money and a slug was enough.
 *
 * The two ids are kept apart rather than merged. `id` stays a slug because it
 * is what a human reads in this file and what `personById` is called with;
 * `personId` is what the API is asked about. Collapsing them would mean either
 * UUIDs in every call site or a lookup on every render, and the seed script's
 * own comment rules out a third option -- a padded UUID literal is a long
 * digit run and the repo guard blocks it on sight, unable to tell a demo id
 * from an account number. These derive from `uuid5` and carry no such run.
 *
 * Copied values in two files drift, so they are not trusted to match by care:
 * `tests/test_demo_identity_matches_seed.py` re-derives every one of them from
 * `scripts/seed_demo_data.py` and fails if a single character moves. Getting
 * this wrong is silent -- the screen would ask about a person who does not
 * exist and render a truthful, correct, entirely empty answer.
 */

export type DemoPerson = {
  /** Slug. Stable, readable, and never sent anywhere. */
  id: string;
  /** The `people` row this person is, in the seeded database. */
  personId: string;
  name: string;
  /** Two-letter monogram for the avatar. No photos of real people in Git. */
  initials: string;
};

export const DEMO_GROUP_NAME = "Team Đà Lạt";

export const DEMO_PEOPLE: DemoPerson[] = [
  { id: "minh", personId: "46b55e67-932b-5415-a5ee-08fb2641a4ff", name: "Minh", initials: "M" },
  { id: "trang", personId: "49871dab-3bf9-5140-acf3-6c9736b31e8f", name: "Trang", initials: "Tr" },
  { id: "hai", personId: "be2389f9-62cb-5b28-8e5f-874768e9fb75", name: "Hải", initials: "H" },
  { id: "ngoc", personId: "e3a44e25-4547-508a-8f4d-9b2495c3325f", name: "Ngọc", initials: "Ng" },
  { id: "duc", personId: "4421b3f8-26a6-5827-a7e7-548c5a4a10f9", name: "Đức", initials: "Đ" },
  { id: "linh", personId: "cdadf49b-b6a8-5631-8b9d-aee6a7d532de", name: "Linh", initials: "L" },
  { id: "quan", personId: "93c153f7-042a-556d-b227-7b1e54f2d50b", name: "Quân", initials: "Q" },
];

export function personById(id: string): DemoPerson | null {
  return DEMO_PEOPLE.find((p) => p.id === id) ?? null;
}
