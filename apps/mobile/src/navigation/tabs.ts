/** What the shell can show, as data rather than as JSX.
 *
 * Kept free of React on purpose. The acceptance criterion for this shell is
 * "every one of the five tabs reaches its screen", and a criterion checked by
 * clicking five times in a simulator is checked once, by one person, and never
 * again. As plain data it is checked by `tests/navigation.test.mjs` on every
 * run -- including the case nobody clicks, which is a tab whose destination
 * was deleted out from under it.
 *
 * Nothing here decides what a screen looks like. It decides what exists.
 */

/** The four things the centre [+] can start. */
export type CreateActionId = "tao-chuyen" | "tao-khoan-chi" | "dang-ky-niem" | "tao-nhom";

/** Where a tab sends you. `shell` is a screen that is honestly still a shell. */
export type Destination =
  | { kind: "built"; screen: string }
  | { kind: "shell"; screen: string; owner: string; work: string };

export type Tab = {
  id: string;
  /** Label under the icon. Short: the bar has five slots on a 390pt screen. */
  label: string;
  /** Spoken by a screen reader, where "Khám phá" alone is not a destination. */
  a11yLabel: string;
  destination: Destination;
};

/**
 * The five slots, in bar order, with the [+] sitting third.
 *
 * The [+] is in this list rather than beside it because the bar renders five
 * slots and the middle one has to be *somewhere*. It is not a tab -- selecting
 * it never changes which screen is showing -- so it carries its own kind and
 * the shell refuses to treat it as a destination.
 */
export const TABS: Tab[] = [
  {
    id: "kham-pha",
    label: "Khám phá",
    a11yLabel: "Khám phá — gợi ý chỗ đi cho nhóm",
    // rd-do-fe-06 fills this in. Today it renders its own honest shell.
    destination: { kind: "shell", screen: "KhamPha", owner: "devops", work: "rd-do-fe-06" },
  },
  {
    id: "len-plan",
    label: "Lên plan",
    a11yLabel: "Lên plan — chuyến đi của nhóm",
    destination: { kind: "built", screen: "LenPlan" },
  },
  {
    id: "tin-nhan",
    label: "Tin nhắn",
    a11yLabel: "Tin nhắn — chat nhóm và AI",
    destination: { kind: "built", screen: "TinNhan" },
  },
  {
    id: "ca-nhan",
    label: "Cá nhân",
    a11yLabel: "Cá nhân — hồ sơ và tài chính của bạn",
    // rd-do-fe-09 fills this in.
    destination: { kind: "shell", screen: "CaNhan", owner: "devops", work: "rd-do-fe-09" },
  },
];

/** The whole-screen tasks the shell knows how to take over with.
 *
 * A closed union rather than a string, so `VoTab` can hold a
 * `Record<CreateFlowId, ...>` and adding a flow here without teaching the
 * shell to open it is a compile error rather than a menu row that quietly
 * does nothing.
 */
export type CreateFlowId = "khoan-chi" | "nhom";

/**
 * How the shell reaches a create action -- as data the shell reads, not as a
 * branch inside it.
 *
 * `null` means nothing is wired: pressing the row explains itself instead of
 * navigating. This field is what makes `built` checkable. `built` is a claim
 * made to the reader (`MenuTao` drops the "vỏ" chip when it is true); `route`
 * is the mechanism that has to exist for the claim to hold. Two independent
 * statements about the same thing, cross-checked in
 * `tests/navigation.test.mjs`, replace what used to be one statement here and
 * a hand-copied list of ids over there -- which every UI branch rewrote, and
 * which passed just as happily when the copy was updated and the wiring was
 * not.
 */
export type CreateRoute =
  | { kind: "tab"; tab: string }
  | { kind: "flow"; flow: CreateFlowId };

export type CreateAction = {
  id: CreateActionId;
  label: string;
  /** One line under the label. A menu of four bare verbs is a guessing game. */
  hint: string;
  /** True when pressing it reaches real behaviour rather than a shell. */
  built: boolean;
  /** Where pressing it goes. `null` for an action nobody has wired yet. */
  route: CreateRoute | null;
};

/**
 * What [+] opens.
 *
 * Three of these reach real behaviour today, and the menu says so out loud
 * rather than letting four identical rows imply four working features. Spec
 * section 14.3's rule about not designing ahead of the actions cuts both ways:
 * the action that does not exist yet must not pretend to.
 *
 * Wiring a new one is two edits in this list -- `built: true` and a `route` --
 * and no edit to the suite. Leaving either one out is a red run.
 */
export const CREATE_ACTIONS: CreateAction[] = [
  {
    id: "tao-chuyen",
    label: "Tạo chuyến",
    hint: "Rủ nhóm đi đâu đó, chọn ngày",
    // F13/F15. Not a flow of its own: it lands on the Lên plan tab, whose own
    // destination therefore has to be a built screen and not a shell.
    built: true,
    route: { kind: "tab", tab: "len-plan" },
  },
  {
    id: "tao-khoan-chi",
    label: "Tạo khoản chi",
    hint: "Chụp bill hoặc nhập tay, AI chia tiền",
    built: true,
    route: { kind: "flow", flow: "khoan-chi" },
  },
  {
    id: "dang-ky-niem",
    label: "Đăng kỷ niệm",
    hint: "Ảnh và khoảnh khắc của chuyến vừa rồi",
    // No route, and the missing route is the honest part: there is no photo
    // store to put a memory in yet. The row says "vỏ" because of this `null`,
    // not in spite of it.
    built: false,
    route: null,
  },
  {
    id: "tao-nhom",
    label: "Tạo nhóm",
    hint: "Lập hội mới, mời bạn vào",
    // F03/F04 built this: the action opens `screens/vao-cua/Nhom.tsx`, which
    // sends `POST /contexts`, `PUT /people/{id}` and
    // `POST /contexts/{id}/members` for real.
    built: true,
    route: { kind: "flow", flow: "nhom" },
  },
];

/** The tab the app opens on. Named rather than assumed to be index 0. */
export const DEFAULT_TAB = "kham-pha";

export function tabById(id: string): Tab | null {
  return TABS.find((t) => t.id === id) ?? null;
}

/**
 * Where an action's `built` claim and its `route` disagree, in words.
 *
 * Three ways a menu row can lie, and this reports all three rather than the
 * first, so one run names every row that needs fixing:
 *
 *   - claims built, goes nowhere -- the row loses its "vỏ" chip and then does
 *     nothing when pressed;
 *   - wears "vỏ" while a route exists -- working behaviour hidden behind a
 *     mark that tells people not to bother;
 *   - lands on a tab that is itself a shell -- reachable, and still nothing
 *     there. This is the one a rebase produces on its own: a branch cut before
 *     the Lên plan screen landed carries `destination: shell` for it, Git
 *     merges that against a `built: true` action without a word, and the
 *     result is a menu row pointing at a placeholder.
 *
 * Returned rather than thrown: this is a fact about the table, and the suite
 * is where a fact about the table should stop a change.
 */
export function misroutedActions(): string[] {
  const problems: string[] = [];
  for (const a of CREATE_ACTIONS) {
    if (a.built && a.route === null) {
      problems.push(`${a.id}: nhận là đã nối nhưng không có route`);
      continue;
    }
    if (!a.built && a.route !== null) {
      problems.push(`${a.id}: còn đeo nhãn vỏ trong khi route đã có`);
      continue;
    }
    if (a.route?.kind !== "tab") continue;
    const tab = tabById(a.route.tab);
    if (!tab) {
      problems.push(`${a.id}: route trỏ tới tab "${a.route.tab}" không có thật`);
    } else if (tab.destination.kind !== "built") {
      problems.push(`${a.id}: route trỏ tới tab "${tab.id}", mà tab đó còn là vỏ`);
    }
  }
  return problems;
}

/**
 * Every tab resolves to a screen name.
 *
 * A tab whose destination is missing renders nothing, and nothing on a phone
 * looks like a slow network rather than a bug -- so this is asserted in the
 * suite instead of being discovered by a person tapping around.
 */
export function unreachableTabs(): string[] {
  return TABS.filter((t) => !t.destination.screen.trim()).map((t) => t.id);
}
