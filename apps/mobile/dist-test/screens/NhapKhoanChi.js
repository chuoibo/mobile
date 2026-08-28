import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { ScrollView, Text, View } from "react-native";
import { FIXTURES } from "../api.js";
import { addParticipant, advancer, duplicateNames, makeIdFactory, removeParticipant, } from "../participants.js";
import { MAX_AMOUNT_VND, formatVnd, parseAmountVnd, } from "../../../../packages/shared/money.mjs.js";
import { space, type, usePalette } from "../theme.js";
import { Button, Card, Choice, Field, Screen } from "../ui/Kit.js";
/** Monotonic, never reused, never derived from anything the user can reorder.
 *  Module-level so ids stay unique across remounts of the screen. */
const nextParticipantId = makeIdFactory();
export function NhapKhoanChi({ form, onForm, onNext, }) {
    const c = usePalette();
    const { occasion, pending, amount, roster } = form;
    const participants = roster.participants;
    const advancerId = roster.advancerId;
    const setOccasion = (value) => onForm({ ...form, occasion: value });
    const setPending = (value) => onForm({ ...form, pending: value });
    const setAmount = (value) => onForm({ ...form, amount: value });
    const setAdvancerId = (id) => onForm({ ...form, roster: { ...roster, advancerId: id } });
    const parsed = parseAmountVnd(amount);
    const totalVnd = parsed.ok ? parsed.value : 0;
    const amountProblem = !parsed.ok && amount.trim() !== "" ? parsed.reason : null;
    const chosen = advancer(roster) !== null;
    const ready = participants.length > 0 && totalVnd > 0 && chosen;
    function addPending() {
        if (!pending.trim())
            return;
        onForm({ ...form, pending: "", roster: addParticipant(roster, pending, nextParticipantId) });
    }
    function dropPerson(id) {
        // Removing anyone can only ever clear a selection, never move it: the id
        // stays attached to the person it was minted for.
        onForm({ ...form, roster: removeParticipant(roster, id) });
    }
    /** Load a situation the offline demo actually has a precomputed answer for. */
    function loadFixture(fixtureId) {
        const fixture = FIXTURES.find((f) => f.id === fixtureId);
        if (!fixture)
            return;
        onForm({
            occasion: fixture.occasion,
            pending: "",
            amount: String(fixture.totalVnd),
            roster: {
                participants: fixture.participants.map((p) => ({ id: p.id, name: p.name })),
                advancerId: fixture.advancerId,
            },
        });
    }
    const duplicated = duplicateNames(roster);
    return (_jsx(Screen, { title: "Kho\u1EA3n chi m\u1EDBi", hint: "Ai c\u00F3 m\u1EB7t, h\u1EBFt bao nhi\u00EAu, ai tr\u1EA3 tr\u01B0\u1EDBc.", footer: _jsxs(_Fragment, { children: [duplicated.length > 0 ? (_jsxs(Text, { style: { ...type.label, color: c.warn }, children: ["C\u00F3 hai ng\u01B0\u1EDDi t\u00EAn ", duplicated.join(", "), ". Chia ti\u1EC1n v\u1EABn \u0111\u00FAng v\u00EC m\u1ED7i ng\u01B0\u1EDDi c\u00F3 m\u00E3 ri\u00EAng, nh\u01B0ng th\u00EAm g\u00EC \u0111\u00F3 \u0111\u1EC3 ph\u00E2n bi\u1EC7t s\u1EBD d\u1EC5 \u0111\u1ECDc h\u01A1n \u2014 v\u00ED d\u1EE5 Nam A v\u00E0 Nam B."] })) : null, _jsx(Button, { label: "Chia ti\u1EC1n", disabled: !ready, onPress: () => onNext({
                        participants,
                        totalVnd,
                        advancerId: advancerId,
                        occasion: occasion.trim() || "khoản chi",
                    }) })] }), children: _jsxs(ScrollView, { contentContainerStyle: { gap: space.md }, keyboardShouldPersistTaps: "handled", children: [_jsxs(Card, { children: [_jsx(Text, { style: { ...type.label, color: c.inkSoft }, children: "B\u1EA3n ch\u1EA1y th\u1EED n\u00E0y kh\u00F4ng t\u1EF1 t\u00EDnh ti\u1EC1n \u2014 n\u00F3 ph\u00E1t l\u1EA1i \u0111\u00E1p \u00E1n \u0111\u00E3 t\u00EDnh s\u1EB5n t\u1EEB b\u1ED9 vector ki\u1EC3m th\u1EED. Ch\u1ECDn m\u1ED9t t\u00ECnh hu\u1ED1ng \u0111\u1EC3 xem:" }), _jsx(View, { style: { flexDirection: "row", flexWrap: "wrap", gap: space.sm }, children: FIXTURES.map((fixture) => (_jsx(Button, { label: `${fixture.id} · ${formatVnd(fixture.totalVnd)}đ / ${fixture.participants.length}`, tone: "quiet", onPress: () => loadFixture(fixture.id) }, fixture.id))) })] }), _jsx(Card, { children: _jsx(Field, { label: "\u0110i \u0111\u00E2u, \u0103n g\u00EC", value: occasion, onChangeText: setOccasion, placeholder: "b\u1EEFa l\u1EA9u t\u1ED1i th\u1EE9 b\u1EA3y" }) }), _jsxs(Card, { children: [_jsx(Field, { label: "Th\u00EAm ng\u01B0\u1EDDi", value: pending, onChangeText: setPending, placeholder: "H\u00E0" }), _jsx(Button, { label: "Th\u00EAm", tone: "quiet", disabled: !pending.trim(), onPress: addPending }), participants.length === 0 ? (_jsx(Text, { style: { ...type.label, color: c.inkSoft }, children: "Ch\u01B0a c\u00F3 ai." })) : (participants.map((person) => (_jsxs(View, { style: { flexDirection: "row", alignItems: "center", gap: space.sm }, children: [_jsx(Text, { style: { ...type.body, color: c.ink, flex: 1 }, children: person.name }), _jsx(Button, { label: "B\u1ECF", tone: "quiet", onPress: () => dropPerson(person.id) })] }, person.id))))] }), _jsxs(Card, { children: [_jsx(Field, { label: "T\u1ED5ng ti\u1EC1n", value: amount, onChangeText: setAmount, keyboardType: "number-pad", placeholder: "480000" }), amountProblem === "too-large" ? (_jsxs(Text, { style: { ...type.label, color: c.warn }, children: ["S\u1ED1 n\u00E0y l\u1EDBn h\u01A1n ", formatVnd(MAX_AMOUNT_VND), "\u0111. \u1EE8ng d\u1EE5ng t\u1EEB ch\u1ED1i thay v\u00EC l\u00E0m tr\u00F2n \u00E2m th\u1EA7m."] })) : null, amountProblem === "not-a-number" ? (_jsx(Text, { style: { ...type.label, color: c.warn }, children: "Ch\u1EC9 nh\u1EADp ch\u1EEF s\u1ED1. D\u1EA5u ch\u1EA5m, ph\u1EA9y v\u00E0 kho\u1EA3ng tr\u1EAFng th\u00EC \u0111\u01B0\u1EE3c." })) : null, totalVnd > 0 ? (_jsxs(Text, { style: { ...type.amount, color: c.ink }, children: [formatVnd(totalVnd), _jsx(Text, { style: { ...type.body, color: c.inkSoft }, children: " \u0111" })] })) : null] }), _jsxs(Card, { children: [_jsx(Choice, { label: "Ai tr\u1EA3 tr\u01B0\u1EDBc", options: participants.map((p) => ({ id: p.id, label: p.name })), value: advancerId, onChange: setAdvancerId }), _jsx(Text, { style: { ...type.label, color: c.inkSoft }, children: "Ng\u01B0\u1EDDi n\u00E0y s\u1EBD ph\u1EA3i x\u00E1c nh\u1EADn tr\u01B0\u1EDBc khi app g\u1EEDi l\u1EDDi nh\u1EAFc d\u01B0\u1EDBi t\u00EAn h\u1ECD." })] })] }) }));
}
