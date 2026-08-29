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

export type CreateAction = {
  id: CreateActionId;
  label: string;
  /** One line under the label. A menu of four bare verbs is a guessing game. */
  hint: string;
  /** True when pressing it reaches real behaviour rather than a shell. */
  built: boolean;
};

/**
 * What [+] opens.
 *
 * Three of these reach real behaviour today, and the menu says so out loud
 * rather than letting four identical rows imply four working features. Spec
 * section 14.3's rule about not designing ahead of the actions cuts both ways:
 * the action that does not exist yet must not pretend to.
 */
export const CREATE_ACTIONS: CreateAction[] = [
  {
    id: "tao-chuyen",
    label: "Tạo chuyến",
    hint: "Rủ nhóm đi đâu đó, chọn ngày",
    built: true,
  },
  {
    id: "tao-khoan-chi",
    label: "Tạo khoản chi",
    hint: "Chụp bill hoặc nhập tay, AI chia tiền",
    built: true,
  },
  {
    id: "dang-ky-niem",
    // Renamed from "Đăng kỷ niệm" because what exists is the wall, not the
    // posting. F30's read side is built -- `screens/ky-niem/KyNiem.tsx` opens
    // `GET /contexts/{id}/recap` and shows the trips that are over, where they
    // went and what they cost. Uploading a photo (F35) is not built and there
    // is no photo store to put one in, so a menu row saying "Đăng" would
    // promise the half that does not exist. The label names the half that does.
    label: "Kỷ niệm nhóm",
    hint: "Xem lại chuyến đã đi, chỗ đã tới, tiền đã chia",
    built: true,
  },
  {
    id: "tao-nhom",
    label: "Tạo nhóm",
    hint: "Lập hội mới, mời bạn vào",
    // F03/F04 built this: the action opens `screens/vao-cua/Nhom.tsx`, which
    // sends `POST /contexts`, `PUT /people/{id}` and
    // `POST /contexts/{id}/members` for real. `tests/navigation.test.mjs`
    // reads this flag, so flipping it without wiring the screen fails there
    // rather than in front of somebody pressing the menu.
    built: true,
  },
];

/** The tab the app opens on. Named rather than assumed to be index 0. */
export const DEFAULT_TAB = "kham-pha";

export function tabById(id: string): Tab | null {
  return TABS.find((t) => t.id === id) ?? null;
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
