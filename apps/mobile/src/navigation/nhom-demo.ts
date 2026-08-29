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
 * The ids do NOT match the seeded rows yet. The seed derives uuid5 ids, and
 * reproducing that here would mean either a SHA-1 implementation or pasted
 * UUID literals -- and the seed script's own comment records why the second
 * one is out: a padded UUID literal is a long digit run and the repo guard
 * blocks it on sight, unable to tell a demo id from an account number. So
 * these are slugs, and the screen that first sends a real request on this
 * person's behalf is the screen that has to map them. Nothing here writes
 * money, so nothing here needs the real id yet.
 */

export type DemoPerson = {
  id: string;
  name: string;
  /** Two-letter monogram for the avatar. No photos of real people in Git. */
  initials: string;
};

export const DEMO_GROUP_NAME = "Team Đà Lạt";

export const DEMO_PEOPLE: DemoPerson[] = [
  { id: "minh", name: "Minh", initials: "M" },
  { id: "trang", name: "Trang", initials: "Tr" },
  { id: "hai", name: "Hải", initials: "H" },
  { id: "ngoc", name: "Ngọc", initials: "Ng" },
  { id: "duc", name: "Đức", initials: "Đ" },
  { id: "linh", name: "Linh", initials: "L" },
  { id: "quan", name: "Quân", initials: "Q" },
];

export function personById(id: string): DemoPerson | null {
  return DEMO_PEOPLE.find((p) => p.id === id) ?? null;
}
