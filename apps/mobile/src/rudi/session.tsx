import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import {
  BILL_ITEMS,
  COLLECTOR_INDEX,
  DEMO_GROUP,
  MEMORY_PHOTOS,
  MEMORY_VIDEO_INDEXES,
  OTHER_TRIP_ITEMS,
  PEOPLE,
  PLACES,
  VOTE_PLACE_IDS,
  cloneItinerary,
  type ItineraryDay,
} from "./fixtures";
import { datTokenPhien } from "../api";
import { dangXuat, khoiPhucPhien, type Phien } from "../phien";
import { docPhienThoAsync, ghiPhienThoAsync, xoaPhienAsync } from "./kho";
import { dongGoi, moGoi } from "./luu-tru";
import { nguonHienTai, type Nguon } from "./nguon";
import { draftPicture, type DraftPicture } from "./money";
import { visibleVoteTallies } from "./vote";

export type RudiSession = {
  displayName: string;
  bio: string;
  interests: string[];
  vibes: string[];
  savedPlaceIds: string[];
  itinerary: ItineraryDay[];
  itineraryEditing: boolean;
  tripName: string;
  destination: string;
  startDate: string;
  endDate: string;
  selectedMemberIds: string[];
  aiSuggest: boolean;
  chatMessages: string[];
  voteChoice: number | null;
  voteConfirmed: boolean;
  assignments: number[][];
  paidFromIndexes: number[];
  remindedPending: boolean;
  checkedInIds: string[];
  locationSharing: boolean;
  receiptPicked: boolean;
  profileNotice: string | null;
  inboxOpen: boolean;
};

const defaultAssignments = () => BILL_ITEMS.map((item) => [...item.people]);

function seed(): RudiSession {
  return {
    displayName: PEOPLE[COLLECTOR_INDEX].name,
    bio: "Đi để nhớ, tụ họp để thương 🌿",
    interests: ["Ăn ngon", "Cafe chill", "Khám phá"],
    vibes: ["Ngoài trời", "Có gu"],
    savedPlaceIds: ["still-cafe"],
    itinerary: cloneItinerary(),
    itineraryEditing: false,
    tripName: DEMO_GROUP.tripName,
    destination: "Đà Lạt, Lâm Đồng",
    startDate: "17/10/2026",
    endDate: "19/10/2026",
    selectedMemberIds: PEOPLE.map((person) => person.id),
    aiSuggest: true,
    chatMessages: [],
    voteChoice: null,
    voteConfirmed: false,
    assignments: defaultAssignments(),
    paidFromIndexes: [1, 2],
    remindedPending: false,
    checkedInIds: PEOPLE.slice(0, 4).map((person) => person.id),
    locationSharing: true,
    receiptPicked: false,
    profileNotice: null,
    inboxOpen: false,
  };
}

type RudiSessionApi = RudiSession & {
  money: DraftPicture;
  photoCount: number;
  videoCount: number;
  checkInCount: number;
  /**
   * Whose data the screens are showing.
   *
   * `trai-nghiem` is the fixture: Team Đà Lạt, eight people, a bill nobody
   * paid. `live` means a session token exists, so every number on screen came
   * from the server. Derived from the token and nothing else -- the field it
   * replaces, `enteredAsDemo`, was set by the login screen and read by nowhere,
   * which is a promise of a gate rather than a gate.
   *
   * ADR-0014 section 9: the 21 screens stay on the experience build until there
   * IS a token, and the copy says so.
   */
  cheDo: "live" | "trai-nghiem";
  /**
   * The same decision with its reason attached, and the identity to read with.
   *
   * `cheDo` is what a badge needs; this is what a screen that actually loads
   * data needs. Both come from `nguonHienTai`, so a screen cannot end up live
   * while the badge says demo.
   */
  nguon: Nguon;
  /** Still reading the disk. Screens must not write over what has not arrived. */
  dangNapPhien: boolean;
  /** The bearer session as restored or just minted; `null` while signed out. */
  phien: Phien | null;
  /** Whether SecureStore has answered. Until then `phien === null` means nothing. */
  phienDaDoc: boolean;
  /**
   * Whether the last write reached the disk.
   *
   * The screens read this to decide whether they may say "lưu trên máy". Before
   * AsyncStorage landed, four sentences said it while nothing was written
   * anywhere; a flag that can be false is what keeps that from happening again
   * when a write fails on a full or restricted device.
   */
  luuTruSong: boolean;
  /**
   * A session that just arrived, put into force without a relaunch.
   *
   * `src/phien.ts` owns the disk and the bearer, so signing in already writes
   * both. What it cannot do is tell this provider, and this provider is what
   * `nguon` is derived from -- so before this existed, somebody could redeem a
   * real invitation, land on the group, and read FIXTURES until they killed
   * the app and opened it again. Two copies of "who is signed in", which is
   * the same fault every other screen on this branch was built to stop.
   *
   * Takes the whole record rather than a flag, so accepting a membership
   * (`membership_state` goes `invited` -> `active`) travels through the same
   * one door as signing in.
   */
  datPhien: (phien: Phien) => void;
  resetSession: () => void;
  setDisplayName: (value: string) => void;
  setBio: (value: string) => void;
  setInterests: (value: string[]) => void;
  setVibes: (value: string[]) => void;
  toggleSaved: (placeId: string) => void;
  addPlaceToTrip: (placeId: string) => boolean;
  removeItinerarySlot: (day: number, index: number) => void;
  moveItinerarySlot: (day: number, index: number, direction: -1 | 1) => void;
  setItineraryEditing: (value: boolean) => void;
  setTripName: (value: string) => void;
  setDestination: (value: string) => void;
  toggleMember: (id: string) => void;
  selectAllMembers: () => void;
  setAiSuggest: (value: boolean) => void;
  sendChat: (message: string) => void;
  setVoteChoice: (index: number) => void;
  confirmVote: () => void;
  voteTallies: number[];
  toggleAssignment: (itemIndex: number, personIndex: number) => void;
  markPaid: (fromIndex: number) => void;
  remindPending: () => void;
  toggleCheckIn: (personId: string) => void;
  checkInSelf: () => void;
  setLocationSharing: (value: boolean) => void;
  setReceiptPicked: (value: boolean) => void;
  setProfileNotice: (value: string | null) => void;
  setInboxOpen: (value: boolean) => void;
  tripPath: (suffix: string) => string;
};

const RudiSessionContext = createContext<RudiSessionApi | null>(null);

export function RudiSessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<RudiSession>(seed);
  const [dangNapPhien, setDangNapPhien] = useState(true);
  const [phien, setPhien] = useState<Phien | null>(null);
  // SecureStore and AsyncStorage are two reads; `dangNapPhien` above covers the
  // draft blob only. The entry decision (`manDau`) needs THIS one.
  const [phienDaDoc, setPhienDaDoc] = useState(false);
  // One decision, derived once. `cheDo` used to be its own piece of state,
  // which is how a badge and a data loader end up disagreeing.
  const nguon = useMemo(() => nguonHienTai(phien), [phien]);
  const cheDo = nguon.kieu === "live" ? "live" : "trai-nghiem";
  const [luuTruSong, setLuuTruSong] = useState(false);
  const hen = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Read once, at mount. `moGoi` validates every field against this seed, so a
  // blob from an older build degrades field by field instead of crashing a
  // money screen on launch.
  useEffect(() => {
    let song = true;
    void docPhienThoAsync().then((raw) => {
      if (!song) return;
      setState((hien) => moGoi(raw, hien));
      setDangNapPhien(false);
    });
    return () => {
      song = false;
    };
  }, []);

  // The session, restored at launch by the module that owns it. `src/phien.ts`
  // (ADR-0014, PR #514) reads SecureStore, drops an expired record rather than
  // sending it, and hands the bearer to `src/api.ts`. This provider only needs
  // to know WHETHER there is one, and who it says we are.
  //
  // An earlier draft of this branch had its own token store and its own bearer
  // plumbing in `api.ts`. Both shipped on main first, and two implementations
  // of one credential is the shape that leaves a tree unable to say which one
  // is in force -- so this reads theirs instead of merging beside it.
  useEffect(() => {
    let song = true;
    void khoiPhucPhien()
      .then((phien) => {
        if (!song) return;
        if (phien !== null) datTokenPhien(phien.token);
        setPhien(phien);
        setPhienDaDoc(true);
      })
      .catch(() => {
        // An unreadable store is indistinguishable from a first launch, and
        // both answers are the same: no session, experience build.
        if (!song) return;
        setPhien(null);
        setPhienDaDoc(true);
      });
    return () => {
      song = false;
    };
  }, []);

  // Write on change, debounced. `setDisplayName` fires once per keystroke, and
  // one AsyncStorage round trip per character is a real cost on a slow device.
  useEffect(() => {
    // Writing before the read lands would put the seed on top of the real data.
    if (dangNapPhien) return undefined;
    if (hen.current !== null) clearTimeout(hen.current);
    hen.current = setTimeout(() => {
      void ghiPhienThoAsync(dongGoi(state)).then((ketQua) => setLuuTruSong(ketQua.ok));
    }, 400);
    return () => {
      if (hen.current !== null) clearTimeout(hen.current);
    };
  }, [state, dangNapPhien]);

  const money = useMemo(
    () =>
      draftPicture({
        billLines: BILL_ITEMS.map((item, index) => ({
          amount: item.amount,
          personIndexes: state.assignments[index] ?? [...item.people],
        })),
        otherLines: OTHER_TRIP_ITEMS.map((item) => ({
          amount: item.amount,
          personIndexes: [...item.people],
        })),
        personIds: PEOPLE.map((person) => person.id),
        collectorIndex: COLLECTOR_INDEX,
      }),
    [state.assignments],
  );

  const voteTallies = useMemo(
    () => visibleVoteTallies(VOTE_PLACE_IDS.length, state.voteChoice, state.voteConfirmed),
    [state.voteChoice, state.voteConfirmed],
  );

  const api: RudiSessionApi = useMemo(() => ({
    ...state,
    cheDo,
    nguon,
    dangNapPhien,
    phien,
    phienDaDoc,
    luuTruSong,
    money,
    photoCount: MEMORY_PHOTOS.length,
    videoCount: MEMORY_VIDEO_INDEXES.length,
    checkInCount: state.checkedInIds.length,
    voteTallies,
    // "Đăng xuất" used to be `router.replace("/welcome")` and nothing else, so
    // the next person to tap "Vào bản trải nghiệm" on the same process got the
    // previous person's name, chat, check-ins and saved places. Measured on the
    // emulator before this line existed. Seeding fresh is the whole of logout
    // while there is no server session to end.
    datPhien: (moi: Phien) => {
      // `datTokenPhien` too, not just the state: `phien.ts` already set it on
      // the way in, but a caller that reached here with a record read from
      // somewhere else must not leave the bearer pointing at the old one.
      datTokenPhien(moi.token);
      setPhien(moi);
    },
    resetSession: () => {
      setState(seed());
      // The debounced write above would land on the seed anyway; this is for
      // the case where the app is killed inside those 400ms. "Đăng xuất xoá
      // mọi lựa chọn" has to be true even then.
      void xoaPhienAsync();
      // And the session itself. `dangXuat` calls the server FIRST and forgets
      // locally in a `finally`, which is the order that matters: a session only
      // the phone forgets is still a live credential on the server, and a phone
      // somebody else is holding is exactly when that matters. Clearing local
      // state here regardless is right for the same reason -- somebody who
      // pressed sign-out has said what they want.
      const dangCo = phien;
      setPhien(null);
      if (dangCo !== null) void dangXuat(dangCo.person_id);
    },
    setDisplayName: (displayName) => setState((current) => ({ ...current, displayName })),
    setBio: (bio) => setState((current) => ({ ...current, bio })),
    setInterests: (interests) => setState((current) => ({ ...current, interests })),
    setVibes: (vibes) => setState((current) => ({ ...current, vibes })),
    toggleSaved: (placeId) =>
      setState((current) => ({
        ...current,
        savedPlaceIds: current.savedPlaceIds.includes(placeId)
          ? current.savedPlaceIds.filter((id) => id !== placeId)
          : [...current.savedPlaceIds, placeId],
      })),
    addPlaceToTrip: (placeId) => {
      const place = PLACES.find((item) => item.id === placeId);
      if (!place) return false;
      setState((current) => {
        const itinerary = cloneItinerary(current.itinerary);
        const dinner = itinerary[0]?.items.find((item) => item.time === "18:00");
        if (dinner) {
          dinner.title = place.name;
          dinner.placeId = place.id;
        } else if (itinerary[0]) {
          itinerary[0].items.push({
            time: "18:00",
            title: place.name,
            icon: "restaurant-outline",
            color: "#E11D48",
            placeId: place.id,
          });
        }
        return { ...current, itinerary };
      });
      return true;
    },
    removeItinerarySlot: (day, index) =>
      setState((current) => {
        const itinerary = cloneItinerary(current.itinerary);
        itinerary[day]?.items.splice(index, 1);
        return { ...current, itinerary };
      }),
    moveItinerarySlot: (day, index, direction) =>
      setState((current) => {
        const itinerary = cloneItinerary(current.itinerary);
        const items = itinerary[day]?.items;
        if (!items) return current;
        const next = index + direction;
        if (next < 0 || next >= items.length) return current;
        const swap = items[index];
        items[index] = items[next];
        items[next] = swap;
        return { ...current, itinerary };
      }),
    setItineraryEditing: (itineraryEditing) => setState((current) => ({ ...current, itineraryEditing })),
    setTripName: (tripName) => setState((current) => ({ ...current, tripName })),
    setDestination: (destination) => setState((current) => ({ ...current, destination })),
    toggleMember: (id) =>
      setState((current) => ({
        ...current,
        selectedMemberIds: current.selectedMemberIds.includes(id)
          ? current.selectedMemberIds.filter((item) => item !== id)
          : [...current.selectedMemberIds, id],
      })),
    selectAllMembers: () =>
      setState((current) => ({ ...current, selectedMemberIds: PEOPLE.map((person) => person.id) })),
    setAiSuggest: (aiSuggest) => setState((current) => ({ ...current, aiSuggest })),
    sendChat: (message) =>
      setState((current) => ({ ...current, chatMessages: [...current.chatMessages, message] })),
    setVoteChoice: (voteChoice) => setState((current) => ({ ...current, voteChoice, voteConfirmed: false })),
    confirmVote: () =>
      setState((current) =>
        current.voteChoice === null ? current : { ...current, voteConfirmed: true },
      ),
    toggleAssignment: (itemIndex, personIndex) =>
      setState((current) => {
        const assignments = current.assignments.map((people, index) => {
          if (index !== itemIndex) return [...people];
          return people.includes(personIndex)
            ? people.filter((person) => person !== personIndex)
            : [...people, personIndex];
        });
        return { ...current, assignments };
      }),
    markPaid: (fromIndex) =>
      setState((current) => ({
        ...current,
        paidFromIndexes: current.paidFromIndexes.includes(fromIndex)
          ? current.paidFromIndexes
          : [...current.paidFromIndexes, fromIndex],
      })),
    remindPending: () => setState((current) => ({ ...current, remindedPending: true })),
    toggleCheckIn: (personId) =>
      setState((current) => ({
        ...current,
        checkedInIds: current.checkedInIds.includes(personId)
          ? current.checkedInIds.filter((id) => id !== personId)
          : [...current.checkedInIds, personId],
      })),
    checkInSelf: () =>
      setState((current) =>
        current.checkedInIds.includes(PEOPLE[COLLECTOR_INDEX].id)
          ? current
          : { ...current, checkedInIds: [...current.checkedInIds, PEOPLE[COLLECTOR_INDEX].id] },
      ),
    setLocationSharing: (locationSharing) => setState((current) => ({ ...current, locationSharing })),
    setReceiptPicked: (receiptPicked) => setState((current) => ({ ...current, receiptPicked })),
    setProfileNotice: (profileNotice) => setState((current) => ({ ...current, profileNotice })),
    setInboxOpen: (inboxOpen) => setState((current) => ({ ...current, inboxOpen })),
    tripPath: (suffix) => `/trips/${DEMO_GROUP.id}${suffix}` as const,
  }), [state, money, voteTallies, cheDo, nguon, phien, phienDaDoc, dangNapPhien, luuTruSong]);

  return <RudiSessionContext.Provider value={api}>{children}</RudiSessionContext.Provider>;
}

export function useRudiSession(): RudiSessionApi {
  const value = useContext(RudiSessionContext);
  if (!value) {
    throw new Error("useRudiSession must be used inside RudiSessionProvider");
  }
  return value;
}
