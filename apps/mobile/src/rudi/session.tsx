import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

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
import { draftPicture, type DraftPicture } from "./money";
import { visibleVoteTallies } from "./vote";

export type RudiSession = {
  enteredAsDemo: boolean;
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
    enteredAsDemo: false,
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
  enterDemo: () => void;
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
        personCount: PEOPLE.length,
        collectorIndex: COLLECTOR_INDEX,
      }),
    [state.assignments],
  );

  const voteTallies = useMemo(
    () => visibleVoteTallies(VOTE_PLACE_IDS.length, state.voteChoice, state.voteConfirmed),
    [state.voteChoice, state.voteConfirmed],
  );

  const api: RudiSessionApi = {
    ...state,
    money,
    photoCount: MEMORY_PHOTOS.length,
    videoCount: MEMORY_VIDEO_INDEXES.length,
    checkInCount: state.checkedInIds.length,
    voteTallies,
    enterDemo: () => setState((current) => ({ ...current, enteredAsDemo: true })),
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
  };

  return <RudiSessionContext.Provider value={api}>{children}</RudiSessionContext.Provider>;
}

export function useRudiSession(): RudiSessionApi {
  const value = useContext(RudiSessionContext);
  if (!value) {
    throw new Error("useRudiSession must be used inside RudiSessionProvider");
  }
  return value;
}
