/** Organiser flow: enter, review, collect, share.
 *
 * A plain state machine rather than a router. Spec section 14.3 says not to
 * build a Home screen or a tab shell before the actions are known, and this
 * flow is a line, not a graph. A router can arrive when there is a second
 * entry point to route to.
 *
 * That second entry point has now arrived. The flow below is unchanged and
 * still a line; what changed is that it is no longer the whole app. It is
 * reached from the shell's [+] menu as "Tạo khoản chi", and it is handed the
 * way back out as `onExit` rather than reaching for the shell itself -- the
 * shell knows about this flow, this flow does not know about the shell.
 *
 * The line now starts at the camera. "Tạo khoản chi" in the [+] menu says
 * "Chụp bill hoặc nhập tay", and this is the file where that sentence is kept
 * true: the flow opens on the viewfinder, and "Huỷ" there drops to the manual
 * form rather than out of the flow -- the two halves of that promise, in the
 * order the mockup puts them.
 */
import { useCameraPermissions, type CameraView } from "expo-camera";
import { StatusBar } from "expo-status-bar";
import React, { useEffect, useRef, useState } from "react";
import {
  LogBox,
  Pressable,
  SafeAreaView,
  ScrollView,
  Text,
  View,
  useColorScheme,
} from "react-native";
import { AppRoot } from "./src/navigation/AppRoot";
import {
  attemptFor,
  confirmExpense,
  confirmReceipt,
  docSoDu,
  isBankRecipientMissing,
  loadBoard,
  luuGanMon,
  openBatch,
  previewSplit,
  proposeSplit,
  publishBatch,
  registerPeople,
  saveBankRecipient,
  scanReceipt,
  quetAnhChupMan,
  type ScreenshotScanWire,
  taoBill,
  thongDiepNguoiDoc,
  type Attempt,
  type PendingProposal,
  BASE_URL,
  type PublishGates,
  type SavedBankRecipient,
  type SplitPreview,
  type CuocBinhChonWire,
} from "./src/api";
import { BinhChon } from "./src/screens/binh-chon/BinhChon";
import { bangKetQuaTuWire } from "./src/screens/binh-chon/ket-qua";
import { MonCuaToi } from "./src/screens/bill/MonCuaToi";
import { BuocMonCuaToi } from "./src/screens/bill/BuocMonCuaToi";
import { apDungMonCuaToi, khoaMonCuaToi } from "./src/screens/bill/mon-cua-toi";
import { NhanMatTrenAnh } from "./src/screens/nhan-mat/NhanMatTrenAnh";
import { MoiVaoChuyen } from "./src/screens/len-plan/MoiVaoChuyen";
import type { LoiMoiBuoiDi } from "./src/screens/quan-tri/quan-tri";
// Aliased, not imported bare: `App.tsx` already holds a `ThanhVien` from
// `chat/nhom`, and the two are different shapes -- that one is a chat
// participant, this one is the membership row `GET /contexts/{id}/members`
// answers. Importing both under one name compiled as `Duplicate identifier`
// and then mis-typed three unrelated lines further down the file.
import type { ThanhVien as HangThanhVien } from "./src/screens/vao-cua/cong-api";
import type { BillWire, SoDu } from "./src/bill";
import { CoLoi, DangTai, TrongRong } from "./src/ui/TrangThai";
import { moTaLoi } from "./src/ui/loi-tren-man";
import {
  HAS_CAMERA,
  nativeBackend,
  openAppSettings,
  readAccess,
  withBillPhoto,
  type GiaiDoanDocBill,
} from "./src/camera";
import { itemsTotalVnd, readingFromWire, type BillReading } from "./src/receipt";
import {
  addPersonToAll,
  alignToRoster,
  blockingProblem,
  dropPerson,
  everyoneShares,
  itemsForWire,
  signature,
  syncLines,
  toggle,
  type Assignment,
} from "./src/assignment";
import { ChupBill } from "./src/screens/ChupBill";
import { KetQuaQuetAnh } from "./src/screens/KetQuaQuetAnh";
import { GoiYChia } from "./src/screens/GoiYChia";
import { KetQuaNhanDien } from "./src/screens/KetQuaNhanDien";
import { KetQuaThanhToan } from "./src/screens/KetQuaThanhToan";
import { MaVietQr } from "./src/ui/MaVietQr";
import { ChiaSe, type Envelope } from "./src/screens/ChiaSe";
import { DeXuat, type Proposal } from "./src/screens/DeXuat";
import { DotThu, type Obligation } from "./src/screens/DotThu";
import { Draft, NhapKhoanChi } from "./src/screens/NhapKhoanChi";
import { TaiKhoanNhan } from "./src/screens/tai-khoan/TaiKhoanNhan";
import { FORM_TRONG } from "./src/screens/tai-khoan/kiem-tra";
import {
  EMPTY_FORM,
  addMember,
  makeIdFactory,
  removeParticipant,
  type DraftForm,
  type GroupMember,
} from "./src/participants";
import { DEMO_PEOPLE, type DemoPerson } from "./src/navigation/nhom-demo";
import {
  cauBuocNhom,
  moNhomChoMan,
  type NhomMan,
  type NhomPhien,
  type ThanhVien,
} from "./src/screens/chat/nhom";
import { space, type, usePalette } from "./src/theme";
import { Button, Screen } from "./src/ui/Kit";
import {
  DEMO_ADVANCER_ID,
  DEMO_ALLOCATIONS,
  DEMO_ASSIGNMENT,
  DEMO_BILL_WIRE,
  DEMO_ENVELOPES,
  DEMO_ITEM_COUNT,
  DEMO_NHOM,
  DEMO_OBLIGATIONS,
  DEMO_READING,
  DEMO_ROSTER,
  DEMO_SPLIT_PREVIEW,
} from "./src/fixtures/thanh-toan-demo";

/* Keep LogBox's notification strip off the entrance to the hero flow.
 *
 * LogBox pins its strip to the bottom of the screen, which is exactly where
 * the tab bar and its [+] button live. Measured on Expo Go 57 / Android 15 at
 * 1080x2400: the strip covers [26,2146]-[1054,2271]; the four tab labels sit
 * at y~2311 and stay tappable, but the [+] "Tạo mới" button spans y 2195..2337
 * with its centre at 2266 -- inside the strip. Exactly one control is
 * swallowed, and it is the door into capture-bill -> split -> VietQR.
 *
 * Tapping it produced no error, no log and no navigation, which on screen is
 * indistinguishable from "this feature does not exist". It cost two false
 * readings in a single native measurement pass before anyone knew to dismiss
 * the strip first.
 *
 * This is invisible in Chrome: react-native-web exports an inert LogBox, so
 * the strip is never drawn there and no browser-based measurement can reach
 * this bug.
 *
 * `ignoreAllLogs` silences the strip only. React Native's own source says so
 * at Libraries/LogBox/LogBox.js:155 -- "this only disables notifications,
 * uncaught errors will still open a full screen LogBox". Warnings still reach
 * `console` and logcat, so this hides no information; it only stops dev chrome
 * from sitting on the hero entrance. In a release build LogBox is already the
 * no-op branch, and on web the react-native-web stub is a no-op, so the call
 * is inert on both of those and does its work only where the bug is.
 */
LogBox.ignoreAllLogs();

type Step =
  | "chup-bill"
  | "ket-qua"
  | "quet-anh"
  | "goi-y"
  // Not a step on the line either. A detour off "goi-y" where one person tags
  // their own dishes (F22) instead of somebody filling in the whole matrix,
  // and it returns to "goi-y" whether or not anything was saved.
  | "mon-cua-toi"
  | "nhap"
  | "de-xuat"
  // Not a step on the line. A detour off "de-xuat", reached only when the
  // server refuses to open a round for want of somewhere to send the money,
  // and it returns to exactly where it was called from.
  | "tai-khoan-nhan"
  | "dot-thu"
  | "ket-qua-tt"
  | "chia-se";

/**
 * Who the app says it is when it asks for a bill to be read.
 *
 * `POST /receipts/scan` wants an actor like every other route, and the bill is
 * read before anybody has typed a single name -- there is no roster yet to
 * borrow an id from. So one id is minted per launch and used for the scan
 * only. It never reaches an expense, an obligation or an envelope: nothing is
 * stored against it, because reading a photo writes nothing.
 *
 * Module-level rather than in state, so a re-render mid-upload cannot change
 * who is asking halfway through.
 */
const SCAN_ACTOR_ID = makeIdFactory()();

/**
 * The two screens that own their whole pane.
 *
 * Both draw their own top-left control -- "Huỷ" on the viewfinder, "Chụp lại"
 * on the reading -- so the flow's own "← Đóng" row is not drawn above them.
 * Two back-controls in the same corner is one too many, and on the viewfinder
 * the row also painted a cream strip along the top of a black screen, which
 * read as the camera failing to reach the top of the phone.
 */
const TOAN_MAN: Step[] = ["chup-bill", "ket-qua", "quet-anh"];

/**
 * What a press is trying to write, as a string.
 *
 * This is the name an attempt is filed under, so it decides when a key is
 * reused and when a fresh one is minted -- and the server's rule is that a key
 * may be reused only while the bytes stay identical. Every field the expense
 * body carries is in here for that reason: change the total, the occasion, who
 * paid, who is in, or which boxes are ticked, and this is a different write
 * that must not replay the answer to the previous one.
 *
 * The matrix signature used to be missing. Editing who ate what and sending
 * again reused the old key against a new body, which the server answers with
 * 422 `idempotency_key_reuse`.
 */
function expenseIntent(d: Draft, matrixSig: string): string {
  const who = d.participants.map((person) => person.id).join(",");
  return `khoan-chi:${d.advancerId}:${d.totalVnd}:${d.occasion}:${who}:${matrixSig}`;
}

/**
 * The people this flow may charge, read off the group the server holds.
 *
 * Nothing here is minted. `personId` is a `people` row, so an id chosen on the
 * split screen is a person the database has already heard of -- which is the
 * whole of bug-125301. Before that, the split screen asked for a *name* and
 * minted a fresh UUID from it: typing "Hải" created a third row called Hải,
 * the allocator divided 989.000 into 329.667 x2 + 329.666 and filed every dong
 * against that stranger, and the real Hải's Cá nhân tab stayed on the number
 * it had before the meal. The money was right to the dong and belonged to
 * nobody.
 *
 * This used to be `groupMembers(DEMO_PEOPLE)` -- the seven names in
 * `nhom-demo.ts`, offered whether or not the group contained them. The server
 * refuses that outright: `_require_participants_are_members` answers `422
 * participant_not_in_context` for anyone charged who is not an *active*
 * member. Offering a name the bill cannot legally carry is a dead end drawn as
 * a button, so the roster is now the membership itself, filtered to active.
 *
 * `left` and `invited` are excluded for the same reason the server excludes
 * them: an invitation nobody accepted is not consent to be billed.
 *
 * Names come from the server first (`MembershipResponse.display_name`), then
 * from the demo roster, and only then from a neutral label. A person can be in
 * this group without being one of the seeded seven -- `DangKy.tsx` registers
 * real people -- and printing their UUID because this file has not heard of
 * them is bug-213501 all over again.
 */
function nguoiCoTheChia(members: ThanhVien[]): GroupMember[] {
  return members
    .filter((m) => m.state === "active")
    .map((m) => ({
      id: m.personId,
      name:
        m.displayName ??
        DEMO_PEOPLE.find((p) => p.personId === m.personId)?.name ??
        "Chưa có tên",
    }));
}

function LuongKhoanChi({ onExit, nguoi, nhomPhien }: {
  onExit: () => void;
  nguoi: DemoPerson | null;
  /** The group this session opened, from `VoTab`. The bill has to land in the
   *  same group the conversation about it happened in; see `TinNhan`'s copy of
   *  this prop and `nhom.ts` on why one screen resolving the group its own way
   *  is bug-223337. */
  nhomPhien: NhomPhien | null;
}) {
  const c = usePalette();
  const scheme = useColorScheme();
  // The bill comes first. This is the hero path: photograph the paper, let the
  // reader turn it into lines, correct what it misread, and only then talk
  // about who owes what. "Huỷ" on that first screen lands on the old manual
  // entry, which is still the whole flow for a group that has no paper bill.
  const [step, setStep] = useState<Step>("chup-bill");
  // The group this bill belongs to, opened the way chat and Lên plan open it.
  //
  // Held as state rather than taken from a constant because there is no
  // constant that works: the id this file used to send (`CONTEXT_ID` in
  // api.ts) had never had a row in `contexts`, so `confirm` refused every
  // expense in the app with `422 participant_not_in_context` once the server
  // started checking that the people being charged are in the group. A group
  // that does not exist has no members, so everyone is a stranger.
  //
  // `khoiDongNhom` creates or replays the demo group and returns its real id
  // and its real roster, which is what both halves of that check need.
  const [nhom, setNhom] = useState<NhomMan>(nguoi ? { kind: "dang-tai" } : { kind: "chua-chon" });
  const [draft, setDraft] = useState<Draft | null>(null);
  // Held here, not inside the screen. "Sửa lại" unmounts the screen, and a
  // form owned by the screen goes with it -- which erased everything a
  // person had typed the moment they tried to change one number.
  const [form, setForm] = useState<DraftForm>(EMPTY_FORM);
  const [proposal, setProposal] = useState<PendingProposal | null>(null);
  // Held across attempts on purpose. Confirming writes a new expense version
  // every time it is called, and opening the batch right after it can fail --
  // it does today, when nobody owed money has a bank account on file. Without
  // this, pressing "Xác nhận" again wrote a second version of the same expense
  // into the ledger, and a third, each one indistinguishable from a real edit.
  const [written, setWritten] = useState<{
    expenseVersionId: string;
    acknowledged: boolean;
  } | null>(null);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [envelopes, setEnvelopes] = useState<Envelope[]>([]);
  const [published, setPublished] = useState(false);
  // Whose code the settlement screen is showing. One at a time, on purpose:
  // a wall of codes is a wall of other people's bank accounts, and the person
  // holding the phone only ever needs their own.
  const [nguoiDangChon, setNguoiDangChon] = useState<string | null>(null);
  // Spec section 8.3. Reported by the batch, never assumed by the screen.
  const [gates, setGates] = useState<PublishGates>({ payerAcknowledged: false });
  const [error, setError] = useState<string | null>(null);
  // Whether the failure on screen is the one a person can actually do something
  // about from here. Kept beside `error` rather than parsed out of it: the
  // sentence is written for a reader and will be reworded, and a screen that
  // decides whether to offer a way out by matching words in a message breaks
  // the next time somebody improves the wording.
  const [thieuTaiKhoanNhan, setThieuTaiKhoanNhan] = useState(false);
  // Set once the destination is stored, and shown back masked. Only so the
  // proposal screen can say the blocker is gone -- pressing the same button
  // again with no acknowledgement reads as pressing it and hoping.
  const [taiKhoanNhan, setTaiKhoanNhan] = useState<SavedBankRecipient | null>(null);
  const [busy, setBusy] = useState(false);
  // One attempt per thing being written, minted on the first press and kept.
  //
  // A fresh key on every press is the obvious version and it is wrong in the
  // one case that matters: the request reached the server, the reply did not
  // reach us, the person presses again. A new key makes that a second arrival
  // -- a second expense in the ledger, or an obligation pushed to
  // `over_confirmed`, which reads as somebody having paid more than they owed.
  //
  // This covers every write, not just receipts. It used to hold receipt keys
  // alone, which was the only route whose key the server ever saw, because no
  // route sent the header at all.
  //
  // Kept in a ref rather than state so a re-render between the press and the
  // reply cannot lose it. State would be restored asynchronously, and the gap
  // is exactly when a person presses again.
  const attempts = useRef<Record<string, Attempt>>({});
  /** A `POST /bills` is in flight. Guards the late store below, not the one on
   *  "Tiếp tục": adding two people quickly would otherwise fire twice, and the
   *  two calls carry different rosters, so their attempt keys differ and the
   *  server would store two bills for one dinner rather than replaying one. */
  const dangTaoBill = useRef(false);

  // --- reading a bill -------------------------------------------------
  const cameraRef = useRef<CameraView | null>(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [reading, setReading] = useState<BillReading | null>(null);
  // Which half of the read is running. Reported by `withBillPhoto` as it
  // crosses each boundary, never inferred from a clock: a stage line driven by
  // a timer says "đang gửi" while compression is still going on a slow phone,
  // which is the screen making something up.
  const [giaiDoan, setGiaiDoan] = useState<GiaiDoanDocBill | null>(null);
  // Bumped on every accepted scan, and used as the result screen's `key`.
  // That screen keeps per-row drafts of half-typed numbers; without a new key
  // React reuses the mounted instance, and a rescan showed the previous bill's
  // rejected "12x" still sitting in row three of a completely different bill.
  const [scanSeq, setScanSeq] = useState(0);
  const [ketQuaAnh, setKetQuaAnh] = useState<ScreenshotScanWire | null>(null);
  const access = readAccess(permission, HAS_CAMERA);
  // Held here, not inside the screen. The screen unmounts on every step
  // change; a roster or a matrix owned there would vanish the moment someone
  // pressed back, and they would have to name everybody again.
  const [assignment, setAssignment] = useState<Assignment>({});
  const [preview, setPreview] = useState<{
    signature: string;
    split: SplitPreview;
  } | null>(null);
  /**
   * The stored bill, once the reading has been written to the server.
   *
   * Held next to `assignment` rather than inside `GoiYChia` for the same
   * reason: the screen unmounts on every step change, and a bill id owned
   * there would be lost on the way back to fix a misread price -- leaving the
   * next "Tiếp tục" to store a second bill for the same dinner.
   *
   * `null` means the write has not landed. The matrix still works in that
   * state, and says so: what it cannot do is claim the group's ticks are
   * saved anywhere.
   */
  const [bill, setBill] = useState<BillWire | null>(null);
  const [soDu, setSoDu] = useState<SoDu | null>(null);

  /**
   * Take (or pick) one photo, have it read, and show what came back.
   *
   * `withBillPhoto` owns the file: it compresses, hands the bytes to the
   * upload, and deletes both the capture and the compressed copy afterwards --
   * including when the upload throws. Nothing here ever holds a uri, which is
   * the point. A `null` result is somebody backing out of the picker, and
   * backing out is not an error to shout about.
   */
  function scan(source: "camera" | "thu-vien") {
    return guard(async () => {
      // Cleared in `finally` rather than after a success. A failed read that
      // left the stage set would put "AI đang đọc" under an error message.
      let wire;
      try {
        wire = await withBillPhoto(
          nativeBackend(cameraRef),
          source,
          (photo) => scanReceipt(photo, SCAN_ACTOR_ID),
          setGiaiDoan,
        );
      } finally {
        setGiaiDoan(null);
      }
      if (wire === null) return;
      setReading(readingFromWire(wire));
      setAssignment({});
      setPreview(null);
      setScanSeq((n) => n + 1);
      setStep("ket-qua");
    });
  }

  /**
   * Pick a screenshot, have it read, and show the one merchant + one total.
   *
   * Same file ownership as the paper-bill path: `withBillPhoto` deletes the
   * capture even when the read throws. Nothing here holds a uri, and nothing
   * is logged.
   */
  function scanScreenshot() {
    return guard(async () => {
      let wire;
      try {
        wire = await withBillPhoto(
          nativeBackend(cameraRef),
          "thu-vien",
          (photo) => quetAnhChupMan(photo, SCAN_ACTOR_ID),
          setGiaiDoan,
        );
      } finally {
        setGiaiDoan(null);
      }
      if (wire === null) return;
      setKetQuaAnh(wire);
      setStep("quet-anh");
    });
  }

  /**
   * Re-read the board from the server.
   *
   * Nothing here polls. A guest reporting a transfer changes the server, not
   * this screen, and a screen that quietly went stale would show an organiser
   * "chưa chuyển" next to money that arrived an hour ago. The button says out
   * loud that looking is an action.
   */
  async function refreshBoard() {
    if (!batchId || !proposal) return;
    // The group is read here rather than closed over from further down, so the
    // membership this resolves names against is the one loaded right now. The
    // board names people the SERVER picked, so without it every row on a
    // refreshed board reads as a UUID -- see `nameFrom` in `api.ts`.
    if (nhom.kind !== "xong") return;
    const board = await loadBoard(
      proposal.contextId,
      batchId,
      proposal.advancerId,
      proposal.participants,
      nguoiCoTheChia(nhom.members),
    );
    setObligations(board.obligations);
  }

  async function guard(work: () => Promise<void>) {
    setError(null);
    setThieuTaiKhoanNhan(false);
    setBusy(true);
    try {
      await work();
    } catch (problem) {
      // Say what failed and what to do. "Something went wrong" is not an
      // error message, it is an apology.
      // `api.ts` already turns an unreachable server into an ApiError whose
      // message names the address it tried, so there is nothing to add here.
      // The branch that used to sit here looked for "fetch" in the message and
      // could never match -- a fallback that reads as careful and never runs.
      // The non-Error half is `moTaLoi`'s now: `String()` of a thrown DOM node
      // put `[object HTMLCanvasElement]` on this screen (bug-010822).
      setError(moTaLoi(problem));
      // A sentence explaining a refusal is not the same as a way past it. This
      // is the one refusal on the flow whose fix is a screen in this app, so it
      // is the one that gets a button -- see `isBankRecipientMissing`.
      setThieuTaiKhoanNhan(isBankRecipientMissing(problem));
    } finally {
      setBusy(false);
    }
  }

  /**
   * Preview the split ~450ms after the last tick.
   *
   * The attempt is filed under `xem-truoc:` + the matrix signature. The same
   * ticks produce the same key *and* the same body, so the server replays
   * instead of inserting another expense. Ticking back and forth does not
   * fill the ledger with junk.
   *
   * `paid_by_id` is `participantIds[0]`. Nobody has chosen who paid yet --
   * that is the next screen -- and the allocator still needs somewhere to
   * park the leftover dong. That is why the rounding_gainers line is on
   * this screen: the 1đ assignment here is provisional.
   *
   * The timeout is cleared on unmount and on every change. A reply for a
   * signature that is no longer current is dropped, so a slow round-trip
   * cannot overwrite a newer one.
   */
  /**
   * The group's standing position, loaded when the matrix opens.
   *
   * Deliberately *before* this bill rather than after it. What a person wants
   * to know while ticking boxes is the debt this dinner is landing on top of,
   * and by the time the split is confirmed they have left this screen. It also
   * keeps the panel honest about what it is: `/contexts/{id}/balances` is the
   * ledger's net position, which does not include a bill nobody has confirmed
   * yet, and labelling it "trước bữa này" is the only way to show it without
   * implying otherwise.
   *
   * A failure is silent here, and that is a considered choice rather than a
   * swallowed error: this panel is context beside the task, not the task. A
   * red banner over the matrix because a secondary read timed out would block
   * work the person can still do, and `SoDuNhom` renders nothing when it has
   * nothing, so the screen simply does not show the panel.
   */
  useEffect(() => {
    if (step !== "goi-y" || nhom.kind !== "xong") return;
    const nguoiDoc = form.roster.participants[0]?.id;
    if (nguoiDoc === undefined) return;
    let cancelled = false;
    docSoDu(nhom.contextId, nguoiDoc)
      .then((ket) => { if (!cancelled) setSoDu(ket); })
      .catch(() => { if (!cancelled) setSoDu(null); });
    return () => { cancelled = true; };
  }, [step, form.roster, bill, nhom]);

  /**
   * Open the group before anything is written under it.
   *
   * Same call, same order as `TinNhan` and `LenPlan`: those two screens have
   * been doing this since they shipped, and this flow was the last one still
   * addressing a group that did not exist.
   */
  useEffect(() => {
    if (!nguoi) {
      setNhom({ kind: "chua-chon" });
      return;
    }
    let huy = false;
    setNhom({ kind: "dang-tai" });
    moNhomChoMan(nguoi, nhomPhien).then((s) => {
      if (!huy) setNhom(s);
    });
    return () => {
      huy = true;
    };
  }, [nguoi, nhomPhien]);

  useEffect(() => {
    if (step !== "goi-y" || reading === null || nhom.kind !== "xong") return;
    const contextId = nhom.contextId;
    const ids = form.roster.participants.map((person) => person.id);
    const blocked = blockingProblem(reading, ids, assignment);
    if (blocked !== null || ids.length === 0) return;
    const sig = signature(reading, ids, assignment);
    let cancelled = false;
    const timer = setTimeout(() => {
      const payerId = ids[0];
      if (payerId === undefined) return;
      previewSplit(
        {
          contextId,
          participantIds: ids,
          totalVnd: itemsTotalVnd(reading),
          items: itemsForWire(reading, assignment),
          payerId,
          occasion: "xem trước chia",
        },
        attemptFor(attempts.current, `xem-truoc:${sig}`),
      )
        .then((split) => {
          if (cancelled) return;
          setPreview({ signature: sig, split });
        })
        .catch((problem) => {
          if (cancelled) return;
          // The same line as the catch above, and it was still here after that
          // one was fixed. Nobody photographed this one because reaching it
          // needs a preview request to reject, not a file to fail decoding --
          // but the arm it lands in is the identical `String(problem)`, so it
          // was the identical bug waiting on a different trigger (bug-010822).
          setError(moTaLoi(problem));
        });
    }, 450);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [step, reading, form.roster, assignment, nhom]);

  // The viewfinder is the one screen that owns the whole pane. Left on the
  // cream page ground, the shell painted a light strip under a black screen
  // and the server line sat in it, which read as the camera screen failing to
  // reach the bottom of the phone.
  const dark = step === "chup-bill";
  const tuVe = TOAN_MAN.includes(step);
  // Who the money is owed to, by name. Falls back to a role rather than to the
  // id: an id on a button reads as a bug, and this button is offered at the
  // exact moment somebody is already looking at a refusal.
  const tenNguoiUngTien =
    proposal?.participants.find((person) => person.id === proposal.advancerId)?.name ??
    "người ứng tiền";

  /* Nothing below is drawn until the group is open, and that is the point.
   *
   * Every step of this flow writes under a group: the bill, the preview, the
   * expense, the batch, the board. Letting the camera open first and finding
   * out at "Xác nhận" that there is no group is what the previous version did,
   * except it never found out at all -- it sent an id that could not exist and
   * read the server's refusal as an app error, three screens deep, after
   * somebody had photographed a bill and ticked twenty boxes.
   *
   * Waiting costs nothing that was not already being waited for: reading the
   * bill is itself a server call, so this flow has never worked offline. */
  if (nhom.kind !== "xong") {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
        <StatusBar style={scheme === "dark" ? "light" : "dark"} />
        <Screen title="Chia tiền" hint="Khoản chi được ghi vào nhóm bạn đang ở.">
          {nhom.kind === "chua-chon" ? (
            <TrongRong
              tieuDe="Chưa biết bạn là ai"
              than="Chọn tên mình ở màn hình mở đầu rồi quay lại. Khoản chi phải ghi vào một nhóm có thật, và nhóm đó là nhóm của bạn."
              hanhDong={{ nhan: "Quay lại", onPress: onExit }}
            />
          ) : nhom.kind === "dang-tai" ? (
            <DangTai noiDung="Đang mở nhóm" phu="Chỉ mất một lúc, rồi tới phần chụp bill." />
          ) : (
            <CoLoi
              tieuDe={cauBuocNhom(nhom.buoc)}
              than="Chưa mở được nhóm nên chưa ghi khoản chi vào đâu được. Bước đang đứng và địa chỉ đã thử nằm dưới."
              viecTiepTheo="Thử lại. Nếu vẫn vậy thì máy chủ chưa lên, báo cho nhóm kỹ thuật kèm địa chỉ dưới đây."
              diaChi={nhom.url}
              onThuLai={() => {
                if (!nguoi) return;
                setNhom({ kind: "dang-tai" });
                moNhomChoMan(nguoi, nhomPhien).then(setNhom);
              }}
            />
          )}
        </Screen>
      </SafeAreaView>
    );
  }
  const contextId = nhom.contextId;
  const nguoiTrongNhom = nguoiCoTheChia(nhom.members);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: dark ? "#000" : c.ground }}>
      <StatusBar style={dark || scheme === "dark" ? "light" : "dark"} />

      {/* The way back to the tabs. The flow keeps its own "Sửa lại" for moving
          between steps; this is the separate question of leaving entirely, so
          it sits above the steps rather than inside any one of them.

          Not drawn over the two screens that already carry a top-left control
          of their own -- see `TOAN_MAN`. From those, the way out of the flow
          is one step further along: "Huỷ" reaches the manual form, and the
          row is there. */}
      {tuVe ? null : (
        <View style={{ paddingHorizontal: space.md, paddingTop: space.sm }}>
          <Pressable
            onPress={onExit}
            accessibilityRole="button"
            accessibilityLabel="Đóng khoản chi, quay lại các tab"
            style={({ pressed }) => ({
              alignSelf: "flex-start",
              minHeight: 44,
              justifyContent: "center",
              paddingRight: space.sm,
              opacity: pressed ? 0.6 : 1,
            })}
          >
            <Text style={{ ...type.body, color: c.accent }}>← Đóng</Text>
          </Pressable>
        </View>
      )}

      {step === "chup-bill" && (
        <ChupBill
          access={access}
          cameraRef={cameraRef}
          busy={busy}
          giaiDoan={giaiDoan}
          error={error}
          onShutter={() => scan("camera")}
          onPickImage={() => scan("thu-vien")}
          onPickScreenshot={() => scanScreenshot()}
          onRequestPermission={() => guard(async () => {
            await requestPermission();
          })}
          onOpenSettings={() => guard(openAppSettings)}
          // Not every group has a paper bill, and not every phone will open a
          // camera. Cancelling drops into the manual form rather than into a
          // dead end -- and the manual form is where "← Đóng" lives, so this
          // is also the way back out to the tabs.
          onCancel={() => { setError(null); setStep("nhap"); }}
        />
      )}

      {step === "quet-anh" && ketQuaAnh !== null && (
        <KetQuaQuetAnh
          ketQua={ketQuaAnh}
          onHuy={() => { setError(null); setKetQuaAnh(null); setStep("chup-bill"); }}
          onChot={() => {
            // DraftForm holds the occasion as text and the amount as the
            // person's typed string. The wire has `merchant` and `total_vnd`;
            // there is no `title` or `description` field on the form.
            setForm((f) => ({
              ...f,
              occasion: ketQuaAnh.merchant,
              amount: String(ketQuaAnh.total_vnd),
            }));
            setStep("nhap");
          }}
        />
      )}

      {step === "ket-qua" && reading !== null && (
        <KetQuaNhanDien
          key={scanSeq}
          reading={reading}
          onChange={setReading}
          onRetake={() => { setError(null); setStep("chup-bill"); }}
          onContinue={() => {
            // The bill total becomes the expense total, as text, because that
            // is what the form holds -- `parseAmountVnd` reads it back on the
            // other side. Nothing is divided here: the allocator on the server
            // is still the only thing in this product that splits money.
            const ids = form.roster.participants.map((person) => person.id);
            const ganMon = syncLines(assignment, reading.lines, ids);
            setForm((f) => ({ ...f, amount: String(itemsTotalVnd(reading)) }));
            setAssignment(ganMon);
            setStep("goi-y");
            // Store the reading as a bill, and do it without holding the
            // screen. The matrix is usable the moment it paints; what the
            // write buys is that the ticks survive the app closing, and
            // waiting on a round-trip before showing a table nobody needs the
            // server to draw would be paying for that in the wrong place.
            //
            // A failure here is reported and not fatal: `bill` stays null, the
            // matrix keeps working, and the screen says the ticks are not
            // saved rather than pretending they are.
            const nguoiTao = ids[0];
            if (nguoiTao === undefined) return;
            taoBill(
              reading,
              contextId,
              ganMon,
              nguoiTao,
              attemptFor(attempts.current, `tao-bill:${signature(reading, ids, ganMon)}`),
            )
              .then(setBill)
              .catch((problem) => setError(moTaLoi(problem)));
          }}
        />
      )}

      {step === "goi-y" && reading !== null && (
        <GoiYChia
          reading={reading}
          roster={form.roster}
          nhom={nguoiTrongNhom}
          assignment={assignment}
          preview={preview}
          bill={bill}
          soDu={soDu}
          onBack={() => { setError(null); setStep("ket-qua"); }}
          onReset={() => {
            setAssignment(
              everyoneShares(
                reading.lines,
                form.roster.participants.map((person) => person.id),
              ),
            );
          }}
          onToggle={(lineId, personId) => {
            setAssignment((a) => toggle(a, lineId, personId));
          }}
          onAddMember={(member) => {
            const rosterMoi = addMember(form.roster, member);
            // Somebody who just joined the bill starts on every dish, matching
            // the default the screen states out loud ("mặc định là cả nhóm ăn
            // chung"). Ticking them off is one tap; hunting for the dishes they
            // did eat is eight.
            const ganMoi = addPersonToAll(
              assignment,
              reading.lines.map((line) => line.id),
              member.id,
            );
            setForm((f) => ({ ...f, roster: rosterMoi }));
            setAssignment(ganMoi);

            // Store the bill here if "Tiếp tục" could not.
            //
            // `onContinue` needs somebody on the roster to name as author and
            // returns without writing when there is nobody -- and on the real
            // demo path there never is: the bill is read before the group is
            // picked, so the roster is filled on THIS screen, one step after
            // the write was supposed to happen. Measured on the walk in
            // `quet-man-sau-tap.mjs`: `POST /bills` was absent from the whole
            // request log, `bill` stayed null to the end, and the footer said
            // "Chưa lưu được. Ô đã tích chỉ ở máy này." for the entire demo.
            //
            // So this is the retry, not a second way of storing bills: same
            // call, same attempt-key scheme, and it only ever runs while
            // nothing has been stored.
            if (bill === null && !dangTaoBill.current) {
              const ids = rosterMoi.participants.map((person) => person.id);
              const nguoiTao = ids[0];
              if (nguoiTao !== undefined) {
                dangTaoBill.current = true;
                taoBill(
                  reading,
                  contextId,
                  ganMoi,
                  nguoiTao,
                  attemptFor(attempts.current, `tao-bill:${signature(reading, ids, ganMoi)}`),
                )
                  .then(setBill)
                  .catch((problem) => {
                    // Released, so adding the next person tries again. A latch
                    // left closed on a failure would make the first network
                    // blip permanent for the rest of the dinner.
                    dangTaoBill.current = false;
                    setError(moTaLoi(problem));
                  });
              }
            }
          }}
          onRemovePerson={(id) => {
            setForm((f) => ({ ...f, roster: removeParticipant(f.roster, id) }));
            setAssignment((a) => dropPerson(a, id));
          }}
          onSeeResults={() => {
            setForm((f) => ({
              ...f,
              amount: String(itemsTotalVnd(reading)),
            }));
            setStep("nhap");
            // Turn the ticks into decisions on the way out. This is what moves
            // the bill off `ai_suggested`: until it runs, every share the
            // server holds is still labelled as the machine's guess, however
            // many boxes a person ticked.
            //
            // Nothing here waits on it either, and nothing downstream reads
            // the result -- the split a person is about to confirm comes from
            // the allocator over `POST /expenses`, exactly as before. Writing
            // the decisions is a separate promise about a separate question:
            // who claimed what.
            const ids = form.roster.participants.map((person) => person.id);
            const nguoiChot = ids[0];
            if (bill === null || nguoiChot === undefined) return;
            luuGanMon(
              bill.id,
              reading,
              assignment,
              nguoiChot,
              contextId,
              attemptFor(
                attempts.current,
                `gan-mon:${bill.id}:${signature(reading, ids, assignment)}`,
              ),
            )
              .then(setBill)
              .catch((problem) => setError(moTaLoi(problem)));
          }}
          onMonCuaToi={() => { setError(null); setStep("mon-cua-toi"); }}
          khoaMonCuaToi={khoaMonCuaToi(
            bill,
            nguoi?.personId ?? null,
            form.roster.participants.map((person) => person.id),
          )}
        />
      )}

      {/* Guarded on the same two facts `khoaMonCuaToi` reports on, so the step
          cannot render without the bill id it writes to or the identity it
          writes as. Landing back on "goi-y" rather than showing a broken
          screen: the only way to be here with either one missing is a bill
          write that failed while the step was open. */}
      {step === "mon-cua-toi" && bill !== null && nguoi !== null && (
        <BuocMonCuaToi
          bill={bill}
          toiId={nguoi.personId}
          contextId={contextId}
          tenNhom={nhom.kind === "xong" ? nhom.tenNhom : ""}
          onXong={(moi) => {
            setBill(moi);
            // The claim has to reach the local matrix, or the next "Xem kết
            // quả" writes this matrix over the whole bill and erases it --
            // after the screen said it was saved. Only my own shares move;
            // see `apDungMonCuaToi`.
            setAssignment((a) => apDungMonCuaToi(a, moi, nguoi.personId));
            setStep("goi-y");
          }}
          onQuayLai={() => setStep("goi-y")}
        />
      )}

      {step === "nhap" && (
        <NhapKhoanChi
          form={form}
          nhom={nguoiTrongNhom}
          onForm={setForm}
          onNext={(d) => guard(async () => {
            setDraft(d);
            // A new proposal makes any previously written version stale: it
            // belongs to the numbers on the last screen, not these.
            setWritten(null);
            // Names first, and before anything refers to these ids. The server
            // stores participants as ids; the only place a name ever reaches it
            // is this call. Skip it and every screen here still reads correctly
            // off `form.roster`, while the guest page -- the one screen someone
            // outside the group sees, asking them for money -- prints a UUID
            // where the person should be.
            await registerPeople(d.participants, d.advancerId, attempts.current);
            // Pressing again after a failed send reuses the key, so the server
            // replays rather than writing a second expense. Editing a number
            // first changes the intent, so it mints a new one instead of
            // colliding with the old body and earning a 422.
            const ids = d.participants.map((person) => person.id);
            const aligned = reading === null
              ? assignment
              : alignToRoster(assignment, reading.lines, ids);
            const items = reading === null ? [] : itemsForWire(reading, aligned);
            const matrixSig = reading === null ? "" : signature(reading, ids, aligned);
            setProposal(
              await proposeSplit(
                contextId,
                d,
                attemptFor(attempts.current, expenseIntent(d, matrixSig)),
                items,
              ),
            );
            setStep("de-xuat");
          })}
        />
      )}

      {step === "de-xuat" && proposal && (
        <DeXuat
          proposal={proposal}
          // Same reason the batch board below gets it: the odd dong is assigned
          // by the server, against the roster the server holds.
          nhom={nguoiTrongNhom}
          taiKhoanNhan={
            taiKhoanNhan === null
              ? null
              : `${taiKhoanNhan.bankName} ${taiKhoanNhan.accountMasked}`
          }
          onBack={() => setStep("nhap")}
          onConfirm={() => guard(async () => {
            // Confirm writes the split into the ledger and tells us whether
            // the advancer acknowledged; the batch gate reads that answer
            // rather than assuming it. Written once: if opening the batch
            // fails, pressing the button again reuses the version already in
            // the ledger instead of writing another one beside it.
            const ledger =
              written ??
              (await confirmExpense(
                proposal,
                attemptFor(attempts.current, `xac-nhan:${proposal.expenseId}`),
              ));
            setWritten(ledger);
            const batch = await openBatch(
              proposal,
              ledger.expenseVersionId,
              ledger.acknowledged,
              attemptFor(attempts.current, `mo-dot-thu:${ledger.expenseVersionId}`),
              // The server names the people who owe, against the roster it
              // holds, so the group is needed to turn those ids back into
              // names. Without it the board reads "<uuid> gửi Minh".
              nguoiTrongNhom,
            );
            setBatchId(batch.batchId);
            setObligations(batch.obligations);
            setGates(batch.gates);
            setPublished(false);
            setStep("dot-thu");
          })}
        />
      )}

      {step === "dot-thu" && (
        <DotThu
          obligations={obligations}
          published={published}
          gates={gates}
          onPublish={() => guard(async () => {
            const sent = await publishBatch(
              batchId!,
              gates,
              proposal!.advancerId,
              attemptFor(attempts.current, `phat:${batchId}`),
              proposal!.participants,
              nguoiTrongNhom,
            );
            setEnvelopes(sent);
            setPublished(true);
            // Publishing is the moment the codes come into existence, so it is
            // the first moment the settlement screen has anything to draw.
            // Landing on the first envelope rather than on nothing: the common
            // case is one person owing one person, and asking them to pick
            // themselves out of a list of one is a step for the sake of it.
            setNguoiDangChon(sent[0]?.senderId ?? null);
            setStep("ket-qua-tt");
          })}
          onShare={() => setStep("chia-se")}
          busy={busy}
          onRefresh={() => guard(refreshBoard)}
          onConfirmReceipt={(o) => guard(async () => {
            await confirmReceipt(
              o.id,
              o.amountVnd,
              proposal!.advancerId,
              attemptFor(attempts.current, `bao-tien-ve:${o.id}`),
            );
            await refreshBoard();
          })}
        />
      )}

      {step === "ket-qua-tt" && proposal && (
        <KetQuaThanhToan
          roster={form.roster}
          // The same widening the debt panel on `goi-y` needed: envelopes name
          // their sender in an id the server chose, and the bill is not the
          // list to resolve that against.
          nhom={nguoiTrongNhom}
          // Straight from the server's allocator, not from anything this file
          // added up. `proposal.allocations` is what `POST /expenses` returned
          // and what `confirm` was checked against.
          allocations={proposal.allocations}
          obligations={obligations}
          envelopes={envelopes}
          advancerId={proposal.advancerId}
          itemCount={reading === null ? 0 : reading.lines.length}
          nguoiDangChon={nguoiDangChon}
          onChonNguoi={setNguoiDangChon}
          renderMaQr={(senderId) => {
            const envelope = envelopes.find((e) => e.senderId === senderId);
            if (envelope === undefined) return null;
            // One card per debt. A sender with two recipients gets two codes,
            // each labelled with who it pays, because scanning the wrong one
            // sends the right amount to the wrong person.
            return envelope.obligations.map((debt) => (
              <MaVietQr
                key={debt.obligationId}
                payload={debt.vietqrPayload}
                // The amount from the obligation list, not from the payload.
                // Passing the payload's own number would make the check inside
                // `MaVietQr` compare a value against itself and always agree.
                expectedAmountVnd={debt.amountVnd}
                recipientName={
                  obligations.find((o) => o.id === debt.obligationId)?.recipient ??
                  "người nhận"
                }
              />
            ));
          }}
          onShare={() => setStep("chia-se")}
          onDone={() => setStep("dot-thu")}
          onBack={() => setStep("dot-thu")}
        />
      )}

      {step === "chia-se" && (
        <ChiaSe envelopes={envelopes} onDone={() => setStep("dot-thu")} />
      )}

      {/* The detour. `actorId` is the advancer's own id, because the server
          only ever lets a person write their own destination -- section 9.2,
          and the one rule in the spec with no exception for an admin. On this
          phone the organiser and the advancer are the same person; the day
          they stop being, this call starts failing loudly rather than quietly
          writing into somebody else's row. */}
      {step === "tai-khoan-nhan" && proposal && (
        <TaiKhoanNhan
          nguoiNhan={{ id: proposal.advancerId, name: tenNguoiUngTien }}
          busy={busy}
          onBack={() => { setError(null); setStep("de-xuat"); }}
          onLuu={(dichDen) => guard(async () => {
            const saved = await saveBankRecipient(
              proposal.advancerId,
              dichDen,
              proposal.advancerId,
              // Filed under the destination, not under the person. Re-sending
              // the same digits after a dropped reply has to reuse the key so
              // the server replays; correcting a typo and sending again is a
              // different write and must mint a new one, or it collides with
              // the old body and earns a 422.
              attemptFor(
                attempts.current,
                `tai-khoan-nhan:${proposal.advancerId}:${dichDen.bankBin}:${dichDen.accountNumber}`,
              ),
            );
            setTaiKhoanNhan(saved);
            // Back to where the refusal happened, with the button that was
            // refused still under the thumb.
            setStep("de-xuat");
          })}
        />
      )}

      {error && (
        <View style={{ padding: space.md, backgroundColor: c.card, borderTopColor: c.warn, borderTopWidth: 2, gap: space.sm }}>
          <Text style={{ ...type.label, color: c.warn }}>{error}</Text>
          {/* The half that was missing. The sentence above was already right
              about why the round could not open; what QA found was that every
              control still on screen led back into the same wall. A refusal
              this app can fix gets a door next to it. */}
          {thieuTaiKhoanNhan && proposal ? (
            <Button
              label={`Ghi tài khoản nhận cho ${tenNguoiUngTien}`}
              onPress={() => { setError(null); setThieuTaiKhoanNhan(false); setStep("tai-khoan-nhan"); }}
            />
          ) : null}
        </View>
      )}

      {/* The address is on screen at all times, and that is the point. The
          banner used to read "dữ liệu giả, API chưa nối" -- true then, and the
          kind of line that stays after it stops being true. Naming the server
          cannot go stale: either the app is talking to it or it is not. */}
      <View style={{ paddingHorizontal: space.md, paddingBottom: space.sm }}>
        {/* `inkSoft` is measured on the cream ground and is unreadable on the
            viewfinder's black. Measured: white at 0.62 alpha composites to
            #9e9e9e, 7.84:1 on #000. */}
        <Text
          style={{
            ...type.label,
            color: dark ? "rgba(255, 255, 255, 0.62)" : c.inkSoft,
            textAlign: "center",
          }}
        >
          Máy chủ: {BASE_URL}
        </Text>
      </View>
    </SafeAreaView>
  );
}

/**
 * The settlement screen on frozen data, reachable from a URL, web only.
 *
 * Same reason as `tabTuUrl` in `AppRoot`, which the comment there spells out:
 * a detector renders a URL and cannot press anything. The real screen is eight
 * presses and a live server past the opening screen, so without this it never
 * gets scanned, and "the app was checked" quietly means "the opening screen
 * was checked".
 *
 * Narrow on purpose. One exact parameter value, nothing on native, no writes,
 * and every number comes from a fixture that says out loud it is one. It is
 * not a demo mode and not a way into the product: there is no route from here
 * to anything that touches a server.
 */
function manDo(): boolean {
  return manThamSo() === "ket-qua-thanh-toan";
}

function manThamSo(): string | null {
  const loc = (globalThis as { location?: { search?: string } }).location;
  if (!loc?.search) return null;
  return new URLSearchParams(loc.search).get("man");
}

/**
 * The three states, on one page, web only, for the detector and the camera.
 *
 * Same reason as `XemKetQuaThanhToan` above, and the same narrowness: one exact
 * parameter value, nothing on native, no writes, no route from here into the
 * product. What is new is *why* it has to exist for rd-fe-08 specifically.
 *
 * An empty state needs no data, a waiting state lasts about two seconds, and an
 * error state needs the server to be down. None of the three survives long
 * enough for a scan to catch it on the live flow, so without this page "the
 * states were checked" would quietly mean "the states were read in the source",
 * and `imp detect` on a `.tsx` file is close to blind -- it cannot compute
 * contrast or line length on markup it never rendered.
 *
 * These are the real components with the real copy, not mock-ups of them. If
 * the wording here looks wrong, it is wrong on the screens too.
 */
function XemTrangThai() {
  const c = usePalette();
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={{ padding: space.md, gap: space.md }}>
        <Text style={{ ...type.h1, color: c.ink }}>Ba trạng thái</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Trang để soi và chụp ảnh. Không phải một màn của sản phẩm.
        </Text>

        <Text style={{ ...type.title, color: c.ink }}>Đang tải</Text>
        <DangTai
          noiDung="Đang hỏi máy chủ chỗ nào hợp với nhóm"
          phu="Thường mất một, hai giây."
        />

        <Text style={{ ...type.title, color: c.ink }}>Rỗng</Text>
        <TrongRong
          tieuDe="Chưa có ai phải chuyển tiền"
          than="Khoản chi này không sinh nghĩa vụ nào. Thường là vì chỉ có một người trong nhóm, hoặc người ứng tiền cũng là người duy nhất phải trả."
        />
        <TrongRong
          tieuDe="Chưa có lời nhắn nào để gửi"
          than="Đợt thu chưa được phát nên chưa sinh mã cho ai. Quay lại đợt thu, bấm phát, rồi mở lại màn này."
          hanhDong={{ nhan: "Quay lại đợt thu", onPress: () => {} }}
        />

        <Text style={{ ...type.title, color: c.ink }}>Lỗi</Text>
        {/* The exact sentences `thongDiepNguoiDoc` produces, so this page shows
            what a person really reads rather than a friendlier rewrite of it. */}
        <CoLoi
          tieuDe="Không mở được máy chủ"
          than={thongDiepNguoiDoc(0, null)}
          viecTiepTheo="Kiểm tra máy chủ đang chạy chưa, rồi bấm thử lại."
          diaChi={BASE_URL}
          onThuLai={() => {}}
        />
        <CoLoi
          tieuDe="Máy chủ đang gặp sự cố"
          than={thongDiepNguoiDoc(500, { detail: "Internal Server Error" })}
          viecTiepTheo="Chờ một chút rồi bấm thử lại. Không cần chụp lại bill."
          onThuLai={() => {}}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

function XemKetQuaThanhToan() {
  const c = usePalette();
  const [nguoiDangChon, setNguoiDangChon] = useState<string | null>(
    DEMO_ENVELOPES[0]?.senderId ?? null,
  );
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <StatusBar style="dark" />
      <KetQuaThanhToan
        roster={DEMO_ROSTER}
        // The demo publishes against exactly the people on its own bill, so
        // the two lists are the same one here.
        nhom={DEMO_ROSTER.participants}
        allocations={DEMO_ALLOCATIONS}
        obligations={DEMO_OBLIGATIONS}
        envelopes={DEMO_ENVELOPES}
        advancerId={DEMO_ADVANCER_ID}
        itemCount={DEMO_ITEM_COUNT}
        nguoiDangChon={nguoiDangChon}
        onChonNguoi={setNguoiDangChon}
        renderMaQr={(senderId) => {
          const envelope = DEMO_ENVELOPES.find((e) => e.senderId === senderId);
          if (envelope === undefined) return null;
          return envelope.obligations.map((debt) => (
            <MaVietQr
              key={debt.obligationId}
              payload={debt.vietqrPayload}
              expectedAmountVnd={debt.amountVnd}
              recipientName={
                DEMO_OBLIGATIONS.find((o) => o.id === debt.obligationId)?.recipient ??
                "người nhận"
              }
            />
          ));
        }}
        onShare={() => {}}
        onDone={() => {}}
        onBack={() => {}}
      />
    </SafeAreaView>
  );
}

/**
 * The app root: the opening screen, then the five-tab shell.
 *
 * The flow above is passed down rather than imported by the shell, so the
 * import graph stays one-directional (`App` → `navigation`, never back) and
 * this file remains the only place that knows both halves exist.
 */
/**
 * The bill-reading wait, held still so it can be seen.
 *
 * The real `ChupBill` with `busy` pinned on, not a drawing of it: same
 * component, same props the flow passes, same copy. On the live flow this state
 * lasts about as long as a model takes to read a photo, which is too short to
 * scan and too dependent on a camera to reach in a headless browser at all.
 *
 * `giaiDoan` comes from the query string so both halves are reachable, since
 * they say different things and only one of them can be on screen at a time.
 */
function XemDocBill() {
  const giaiDoan: GiaiDoanDocBill =
    manThamSo() === "doc-bill-chuan-bi" ? "chuan-bi-anh" : "dang-gui";
  // Hoisted out of the JSX below: a hook called in a prop position still runs
  // unconditionally, but it reads like a conditional one and lint treats it so.
  const cameraRef = useRef<CameraView | null>(null);
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: "#000" }}>
      <StatusBar style="light" />
      <ChupBill
        access={{
          state: "cho-phep",
          nextAction: "mo-camera",
          message: "Camera đã sẵn sàng.",
        }}
        cameraRef={cameraRef}
        busy
        giaiDoan={giaiDoan}
        error={null}
        onShutter={() => {}}
        onPickImage={() => {}}
        onPickScreenshot={() => {}}
        onRequestPermission={() => {}}
        onOpenSettings={() => {}}
        onCancel={() => {}}
      />
    </SafeAreaView>
  );
}

/* A destination that is not one. Invented digits, no bank behind them, and the
 * only place they are ever rendered is a scan target that writes nothing. */
// repo-guard: allow=long-number reason=synthetic-scan-fixture-account-number
const SO_TAI_KHOAN_DO = "1904567890123";

/**
 * The bank-destination screen at both of its steps, from a URL, web only.
 *
 * Same reason as `XemTrangThai` above, and the sharper version of it. This
 * screen is where somebody commits money to a destination that cannot be
 * verified by anybody, and it sits four fields and a press past a live server,
 * a 409, and eight presses of the flow. Without this it never gets scanned,
 * and the review step -- the half that actually guards the money -- never gets
 * scanned at all.
 *
 * `?man=tai-khoan-nhan` is the empty form, `?man=tai-khoan-nhan-duyet` is the
 * review step. Nothing here writes: `onLuu` and `onBack` are empty, and there
 * is no route from this page to anything that touches a server.
 */
function XemTaiKhoanNhan() {
  const c = usePalette();
  const duyet = manThamSo() === "tai-khoan-nhan-duyet";
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <StatusBar style="dark" />
      <TaiKhoanNhan
        nguoiNhan={{ id: "p1", name: "Hà" }}
        banDau={{
          dangDuyet: duyet,
          form: duyet
            ? {
                bin: "970436",
                soTaiKhoan: SO_TAI_KHOAN_DO,
                nhapLai: SO_TAI_KHOAN_DO,
                tenChuTaiKhoan: "NGUYEN THI HA",
              }
            : FORM_TRONG,
        }}
        onLuu={() => {}}
        onBack={() => {}}
      />
    </SafeAreaView>
  );
}

/**
 * The two screens between the photograph and the money, from a URL, web only.
 *
 * `KetQuaNhanDien` (AI đọc từng món) and `GoiYChia` (gán món cho người, AI
 * chia) are the middle of the demo path and were the last two screens on it
 * that no machine could open. `tests/moi-man-co-duong-do.test.mjs` had them
 * both as `chuaDo`: reachable only after a photograph has been taken and read,
 * which a headless browser cannot do. So every "the app was scanned" report
 * this repo has produced was silent about them -- not wrong, just narrower
 * than it sounded.
 *
 * Same contract as the four scan targets above: one exact parameter value,
 * nothing on native, the real components with the real copy, no writes, and no
 * route from here into the product. `onChange` and the toggles are wired to
 * local state rather than to `() => {}` on purpose -- a matrix whose ticks do
 * not move is a screen a keyboard pass cannot walk, and half of what these two
 * screens are is what happens when you press something.
 *
 * The fixture is `DEMO_READING` + `DEMO_ASSIGNMENT`, which sum to the same
 * four allocations `?man=ket-qua-thanh-toan` settles. That agreement is what
 * lets `GoiYChia` paint real dong under the avatars instead of "...", and
 * `tests/fixture-hai-man-giua.test.mjs` holds it.
 */
function XemNhanDien() {
  const c = usePalette();
  const [reading, setReading] = useState<BillReading>(DEMO_READING);
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <StatusBar style="dark" />
      <KetQuaNhanDien
        reading={reading}
        onChange={setReading}
        onRetake={() => {}}
        onContinue={() => {}}
      />
    </SafeAreaView>
  );
}

function XemGoiYChia() {
  const c = usePalette();
  const [assignment, setAssignment] = useState<Assignment>(DEMO_ASSIGNMENT);
  const ids = DEMO_ROSTER.participants.map((p) => p.id);

  // Recomputed from the live matrix rather than stored beside it. `GoiYChia`
  // only paints a preview while the signature matches, so ticking a box here
  // must drop the dong back to "..." exactly as it does in the product -- a
  // fixture that kept painting stale numbers after an edit would be showing a
  // money error the real screen refuses to show.
  const preview =
    signature(DEMO_READING, ids, assignment) === signature(DEMO_READING, ids, DEMO_ASSIGNMENT)
      ? { signature: signature(DEMO_READING, ids, assignment), split: DEMO_SPLIT_PREVIEW }
      : null;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <StatusBar style="dark" />
      <GoiYChia
        reading={DEMO_READING}
        roster={DEMO_ROSTER}
        nhom={DEMO_NHOM}
        assignment={assignment}
        preview={preview}
        bill={DEMO_BILL_WIRE}
        soDu={null}
        // Locked, and not with a no-op `onMonCuaToi`. This door renders one
        // screen for a scanner and has no step to move to, so an enabled
        // button here would be a control that does nothing -- exactly the
        // shape `duong-vao-mon-cua-toi.test.mjs` exists to catch. Saying WHY
        // it is locked keeps the scanned pixels honest about it.
        onMonCuaToi={() => {}}
        khoaMonCuaToi="Cửa quét: màn này không đi đâu được."
        onBack={() => {}}
        onReset={() => setAssignment(DEMO_ASSIGNMENT)}
        onToggle={(lineId, personId) =>
          setAssignment((cu) => {
            const dang = cu[lineId] ?? [];
            return {
              ...cu,
              [lineId]: dang.includes(personId)
                ? dang.filter((id) => id !== personId)
                : [...dang, personId],
            };
          })
        }
        onAddMember={() => {}}
        onRemovePerson={() => {}}
        onSeeResults={() => {}}
      />
    </SafeAreaView>
  );
}

/* ---- F17 and F22, from a URL, web only ------------------------------------
 *
 * Same contract as the scan targets above: one exact parameter value, nothing
 * on native, the real components with the real copy, no writes, and no route
 * from here into the product. These three are the newest screens in the app
 * and the ones a headless browser could otherwise never open -- a vote needs a
 * group with a vote in it, and both F22 screens need a photograph somebody
 * took. Without a door, "the app was scanned" would be silent about all three.
 *
 * `?man=binh-chon-hoa` exists as its own value rather than a toggle because a
 * TIE is the state the whole surface is built around, it cannot be reached by
 * pressing anything from the open state, and it is the one a reviewer most
 * needs to see. The two vote fixtures go through `bangKetQuaTuWire` rather
 * than being hand-written view models, so a door that renders is also evidence
 * the translation runs -- a fixture typed straight into `BangKetQua` would
 * keep painting after the wire changed shape underneath it.
 */
const WIRE_BINH_CHON: CuocBinhChonWire = {
  id: "d1d1d1d1-aaaa-4aaa-8aaa-d1d1d1d1d1d1",
  context_id: "d2d2d2d2-bbbb-4bbb-8bbb-d2d2d2d2d2d2",
  outing_id: null,
  created_by_id: "d3d3d3d3-cccc-4ccc-8ccc-d3d3d3d3d3d3",
  question: "Tối nay nhóm mình ăn ở đâu?",
  created_at: "2026-08-30T12:00:00Z",
  closed_at: null,
  is_closed: false,
  options: [
    { id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", position: 0, label: "Lẩu Cô Ba", place_name: "Lẩu Cô Ba, Bàn Cờ", ballot_count: 3 },
    { id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", position: 1, label: "Nướng Ngói", place_name: "Nướng Ngói, Quận 3", ballot_count: 2 },
    { id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc", position: 2, label: "Cơm tấm bà Tư", place_name: null, ballot_count: 1 },
  ],
  total_ballots: 6,
  leading_option_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
  is_tie: false,
  decided_option_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  my_option_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
};

/* Closed, and tied three-all. `decided_option_id` is null because the server
 * refuses to name a winner here, and the screen must refuse too. */
const WIRE_BINH_CHON_HOA: CuocBinhChonWire = {
  ...WIRE_BINH_CHON,
  is_closed: true,
  closed_at: "2026-08-30T13:30:00Z",
  options: WIRE_BINH_CHON.options.map((o, i) => ({ ...o, ballot_count: [3, 3, 0][i] })),
  total_ballots: 6,
  leading_option_ids: [
    "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  ],
  is_tie: true,
  decided_option_id: null,
};

function XemBinhChon() {
  const c = usePalette();
  const hoa = manThamSo() === "binh-chon-hoa";
  const wire = hoa ? WIRE_BINH_CHON_HOA : WIRE_BINH_CHON;
  // Local, so a keyboard pass can actually move the ballot. A radio group whose
  // selection never changes is a control a walk-through cannot exercise.
  const [phieu, setPhieu] = useState<string | null>(wire.my_option_id);
  const bang = bangKetQuaTuWire({ ...wire, my_option_id: phieu });
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <StatusBar style="dark" />
      <BinhChon
        bang={bang}
        dangGui={null}
        loi={null}
        laNguoiMo={!hoa}
        onChonPhieu={setPhieu}
        onDong={() => {}}
        onQuayLai={() => {}}
      />
    </SafeAreaView>
  );
}

const MON_DEMO = [
  { itemKey: "lau-thai", ten: "Lẩu Thái chua cay", soLuong: 1, tienVnd: 320000 },
  { itemKey: "bo-my", ten: "Bò Mỹ cuộn nấm", soLuong: 2, tienVnd: 240000 },
  { itemKey: "rau", ten: "Rau nhúng thập cẩm", soLuong: 1, tienVnd: 60000 },
  { itemKey: "bia", ten: "Bia Sài Gòn", soLuong: 6, tienVnd: 150000 },
  { itemKey: "trang-mieng", ten: "Chè khúc bạch", soLuong: 3, tienVnd: 75000 },
];

function XemMonCuaToi() {
  const c = usePalette();
  const [daChon, setDaChon] = useState<string[]>(["lau-thai", "bia"]);
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <StatusBar style="dark" />
      <MonCuaToi
        tenNhom="Hội bạn Bàn Cờ"
        mon={MON_DEMO}
        daChon={daChon}
        dangLuu={false}
        loi={null}
        onBat={(key) =>
          setDaChon((cu) =>
            cu.includes(key) ? cu.filter((k) => k !== key) : [...cu, key],
          )
        }
        onLuu={() => {}}
        onQuayLai={() => {}}
      />
    </SafeAreaView>
  );
}

/**
 * The stand-in photograph, drawn rather than taken.
 *
 * A real file at a real URL, served next to the bundle from `public/`. The
 * first attempt was an inline `data:` SVG, which is smaller and commits no
 * asset -- and it renders as NOTHING. react-native-web's image loader leaves
 * the backdrop div's inline style empty for a data URI, with no failed request
 * and no console error, so the screen came out as three boxes floating on a
 * blank white card. Measured, not guessed: the same door pointed at an ordinary
 * http URL emits both the `img` element and the `background-image`, which is
 * how the component was cleared of the fault.
 *
 * It is a drawing, and `anh-nhom-dung-san.svg` says why it must stay one.
 */
const ANH_NHOM_DEMO = "/anh-nhom-dung-san.svg";

/* Boxes as the server would return them: fractions of the frame, never pixels.
 * These three sit over the three shapes drawn above. */
const O_DEMO = [
  { boxKey: "0", x: 0.08, y: 0.18, width: 0.22, height: 0.3 },
  { boxKey: "1", x: 0.4, y: 0.12, width: 0.2, height: 0.28 },
  { boxKey: "2", x: 0.68, y: 0.22, width: 0.21, height: 0.29 },
];

function XemNhanMat() {
  const c = usePalette();
  const [oCuaToi, setOCuaToi] = useState<string | null>(null);
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <StatusBar style="dark" />
      <NhanMatTrenAnh
        anhUri={ANH_NHOM_DEMO}
        o={O_DEMO}
        dangTim={false}
        oCuaToi={oCuaToi}
        loi={null}
        onTim={() => {}}
        onChonO={setOCuaToi}
        onXong={() => {}}
        onQuayLai={() => {}}
      />
    </SafeAreaView>
  );
}

/* ---- F14, from a URL, web only --------------------------------------------
 *
 * Same contract as the scan targets above: one exact parameter value, the real
 * component with the real copy, no writes, and no route from here into the
 * product. This screen needs a group, a trip in it, and a roster read before
 * it can exist inside the app, so a headless browser could otherwise never
 * open it -- and "the app was scanned" would be silent about the one screen
 * F14 adds.
 *
 * The fixture carries all four row states on purpose: one member who may be
 * invited, one already invited in this session, one whose invite was revoked
 * (which is a one-way door -- see `moi-vao-chuyen.ts`), and one who has not
 * accepted the group yet. A door that only rendered the happy row would leave
 * the three sentences this screen exists to say unmeasured.
 */
const NGUOI_QUET = "e1e1e1e1-aaaa-4aaa-8aaa-e1e1e1e1e1e1";
const CHUYEN_QUET = "e2e2e2e2-bbbb-4bbb-8bbb-e2e2e2e2e2e2";

const THANH_VIEN_QUET: HangThanhVien[] = [
  { id: "m1", context_id: "c1", person_id: NGUOI_QUET, display_name: "Minh", state: "active", role: "admin", invited_by_id: null, joined_at: "2026-08-01T00:00:00Z", left_at: null, created_at: "2026-08-01T00:00:00Z" },
  { id: "m2", context_id: "c1", person_id: "e3e3e3e3-cccc-4ccc-8ccc-e3e3e3e3e3e3", display_name: "Quyên", state: "active", role: "member", invited_by_id: null, joined_at: "2026-08-01T00:00:00Z", left_at: null, created_at: "2026-08-01T00:00:00Z" },
  { id: "m3", context_id: "c1", person_id: "e4e4e4e4-dddd-4ddd-8ddd-e4e4e4e4e4e4", display_name: "Hà", state: "active", role: "member", invited_by_id: null, joined_at: "2026-08-01T00:00:00Z", left_at: null, created_at: "2026-08-01T00:00:00Z" },
  { id: "m4", context_id: "c1", person_id: "e5e5e5e5-eeee-4eee-8eee-e5e5e5e5e5e5", display_name: "Tú", state: "active", role: "member", invited_by_id: null, joined_at: "2026-08-01T00:00:00Z", left_at: null, created_at: "2026-08-01T00:00:00Z" },
  { id: "m5", context_id: "c1", person_id: "e6e6e6e6-ffff-4fff-8fff-e6e6e6e6e6e6", display_name: "Sơn", state: "invited", role: "member", invited_by_id: NGUOI_QUET, joined_at: null, left_at: null, created_at: "2026-08-01T00:00:00Z" },
];

const MOI_QUET: LoiMoiBuoiDi[] = [
  { id: "i1", outing_id: CHUYEN_QUET, source: "link", invited_person_id: null, invited_by_id: NGUOI_QUET, created_at: "2026-08-31T00:00:00Z", expires_at: "2026-09-07T00:00:00Z", revoked_at: null, invite_token: "quet-khong-phai-token-that", invite_path: "/outing-invites/quet-khong-phai-token-that" },
  { id: "i2", outing_id: CHUYEN_QUET, source: "group", invited_person_id: "e3e3e3e3-cccc-4ccc-8ccc-e3e3e3e3e3e3", invited_by_id: NGUOI_QUET, created_at: "2026-08-31T00:00:00Z", expires_at: "2026-09-07T00:00:00Z", revoked_at: null, invite_token: null, invite_path: null },
  { id: "i3", outing_id: CHUYEN_QUET, source: "group", invited_person_id: "e4e4e4e4-dddd-4ddd-8ddd-e4e4e4e4e4e4", invited_by_id: NGUOI_QUET, created_at: "2026-08-31T00:00:00Z", expires_at: "2026-09-07T00:00:00Z", revoked_at: "2026-08-31T00:10:00Z", invite_token: null, invite_path: null },
];

function XemMoiVaoChuyen() {
  const c = usePalette();
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <StatusBar style="dark" />
      <MoiVaoChuyen
        buoi={{
          id: CHUYEN_QUET,
          context_id: "c1",
          created_by_id: NGUOI_QUET,
          title: "Đà Lạt cuối tuần",
          starts_on: "2026-10-17",
          ends_on: "2026-10-19",
          headcount: 8,
          budget_per_person_vnd: 2500000,
          created_at: "2026-08-31T00:00:00Z",
          stops: [],
        }}
        roster={{ kind: "xong", ds: THANH_VIEN_QUET }}
        toiId={NGUOI_QUET}
        daMoi={MOI_QUET}
        // Frozen, so two screenshots of this door are the same screenshot.
        // `Date.now()` here would make "còn hiệu lực" flip to "đã hết hạn" on
        // whatever day somebody next runs the scan.
        bayGio={Date.parse("2026-08-31T00:30:00Z")}
        onMoiThanhVien={() => {}}
        onTaoLink={() => {}}
        onThuHoi={() => {}}
        onTaiLaiRoster={() => {}}
        onQuayLai={() => {}}
      />
    </SafeAreaView>
  );
}

/* ---- Khoản chi mới and Đợt thu, from a URL, web only ----------------------
 *
 * The last two screens on the money path that no detector had ever opened.
 * Both sat in `moi-man-co-duong-do.test.mjs` as `chuaDo` with an honest reason
 * -- one is only reachable from inside a group, the other only after a
 * confirmed split has produced obligations to collect -- and a disclosure is
 * not a measurement. A screen nothing can open scores zero findings for the
 * same reason a clean screen does, and these two are the first and third steps
 * of the walk the standing checklist asks for.
 *
 * Same contract as the doors above: one exact parameter value, web only
 * (`manThamSo` reads `location.search`, which native does not have), the real
 * components with the real copy, no writes, and no route from here back into
 * the product.
 *
 * `?man=dot-thu-da-phat` is its own value rather than a toggle, for the reason
 * `binh-chon-hoa` is: publishing is the thing the screen exists to do, it
 * swaps the entire footer, drops the "Trước khi phát" card and grows a button
 * on every unsettled row. Nothing a headless browser can press turns one state
 * into the other without a server behind it, so a single address would leave
 * half the surface unmeasured while the row read green.
 */
const NHOM_QUET_CHI: GroupMember[] = [
  { id: "f1f1f1f1-aaaa-4aaa-8aaa-f1f1f1f1f1f1", name: "Minh" },
  { id: "f2f2f2f2-bbbb-4bbb-8bbb-f2f2f2f2f2f2", name: "Hà" },
  { id: "f3f3f3f3-cccc-4ccc-8ccc-f3f3f3f3f3f3", name: "Bảo" },
  { id: "f4f4f4f4-dddd-4ddd-8ddd-f4f4f4f4f4f4", name: "Ngọc" },
  // Two left over on purpose: `availableMembers` drives the "add someone"
  // choices, and an exhausted roster hides that whole control from the scan.
  { id: "f5f5f5f5-eeee-4eee-8eee-f5f5f5f5f5f5", name: "Quân" },
  { id: "f6f6f6f6-ffff-4fff-8fff-f6f6f6f6f6f6", name: "Thu" },
];

/* Filled rather than blank. An empty form is the cheapest thing to render and
 * the least informative to measure: no participant chips, no advancer choice,
 * no formatted amount, and every rule that counts characters on a laid-out
 * line has nothing to count. */
const FORM_QUET: DraftForm = {
  occasion: "Lẩu Thái tối thứ Sáu",
  pending: "",
  amount: "1840000",
  roster: {
    participants: NHOM_QUET_CHI.slice(0, 4).map((m) => ({ id: m.id, name: m.name })),
    advancerId: NHOM_QUET_CHI[0].id,
  },
};

function XemNhapKhoanChi() {
  const c = usePalette();
  // Local, for the same reason the ballot is: a form whose fields cannot move
  // is a form a keyboard pass cannot walk.
  const [form, setForm] = useState<DraftForm>(FORM_QUET);
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <StatusBar style="dark" />
      <NhapKhoanChi
        form={form}
        nhom={NHOM_QUET_CHI}
        onForm={setForm}
        onNext={() => {}}
      />
    </SafeAreaView>
  );
}

/* Five transfers, and deliberately not five distinct people: Minh owes two
 * different recipients. That is the exact case `DotThu`'s own header says the
 * counters are built around -- transfers first, people second -- so a fixture
 * of one-each would render the two numbers identical and prove nothing about
 * either. Every status that colours a row differently appears once. */
const NGHIA_VU_QUET: Obligation[] = [
  { id: "g1", senderId: "f1f1f1f1-aaaa-4aaa-8aaa-f1f1f1f1f1f1", senderName: "Minh", recipient: "Thu", amountVnd: 460000, status: "outstanding" },
  { id: "g2", senderId: "f2f2f2f2-bbbb-4bbb-8bbb-f2f2f2f2f2f2", senderName: "Hà", recipient: "Thu", amountVnd: 320000, status: "confirmed" },
  { id: "g3", senderId: "f3f3f3f3-cccc-4ccc-8ccc-f3f3f3f3f3f3", senderName: "Bảo", recipient: "Thu", amountVnd: 285000, status: "disputed" },
  { id: "g4", senderId: "f1f1f1f1-aaaa-4aaa-8aaa-f1f1f1f1f1f1", senderName: "Minh", recipient: "Quân", amountVnd: 175000, status: "partially_confirmed" },
  { id: "g5", senderId: "f4f4f4f4-dddd-4ddd-8ddd-f4f4f4f4f4f4", senderName: "Ngọc", recipient: "Thu", amountVnd: 240000, status: "waived" },
];

function XemDotThu() {
  const c = usePalette();
  const daPhat = manThamSo() === "dot-thu-da-phat";
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <StatusBar style="dark" />
      <DotThu
        obligations={NGHIA_VU_QUET}
        published={daPhat}
        // Unpublished is shown with the gate still open, because that is the
        // state carrying the refusal copy and the disabled button. Ticked, the
        // card says one word and the button is ordinary.
        gates={{ payerAcknowledged: daPhat }}
        busy={false}
        onPublish={() => {}}
        onShare={() => {}}
        onRefresh={() => {}}
        onConfirmReceipt={() => {}}
      />
    </SafeAreaView>
  );
}

export default function App() {
  if (manDo()) return <XemKetQuaThanhToan />;
  if (manThamSo() === "trang-thai") return <XemTrangThai />;
  if (manThamSo() === "nhan-dien") return <XemNhanDien />;
  if (manThamSo() === "goi-y-chia") return <XemGoiYChia />;
  if (manThamSo()?.startsWith("binh-chon")) return <XemBinhChon />;
  if (manThamSo() === "mon-cua-toi") return <XemMonCuaToi />;
  if (manThamSo() === "nhan-mat") return <XemNhanMat />;
  if (manThamSo() === "moi-vao-chuyen") return <XemMoiVaoChuyen />;
  if (manThamSo() === "nhap-khoan-chi") return <XemNhapKhoanChi />;
  if (manThamSo()?.startsWith("dot-thu")) return <XemDotThu />;
  if (manThamSo()?.startsWith("doc-bill")) return <XemDocBill />;
  if (manThamSo()?.startsWith("tai-khoan-nhan")) return <XemTaiKhoanNhan />;
  return (
    <AppRoot
      renderKhoanChi={(onExit, nguoi, nhomPhien) => (
        <LuongKhoanChi onExit={onExit} nguoi={nguoi} nhomPhien={nhomPhien} />
      )}
    />
  );
}
