import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { ScrollView, Text, View } from "react-native";
import { formatVnd } from "../../../../packages/shared/money.mjs.js";
import { space, type, usePalette } from "../theme.js";
import { Button, Card, Row, Screen } from "../ui/Kit.js";
export function DeXuat({ proposal, onConfirm, onBack }) {
    const c = usePalette();
    // Iterate people, not allocation keys: the key is an id, and only the
    // participant list can turn it back into a name to show.
    const people = proposal.participants;
    const advancerName = people.find((p) => p.id === proposal.advancerId)?.name ?? proposal.advancerId;
    // roundingGainers holds ids; ids are never shown to anyone.
    const gainerNames = proposal.roundingGainers.map((id) => people.find((p) => p.id === id)?.name ?? id);
    const owed = people.filter((p) => p.id !== proposal.advancerId && proposal.allocations[p.id] > 0);
    return (_jsx(Screen, { title: `Chia ${proposal.occasion}`, hint: `${advancerName} đã trả trước ${formatVnd(proposal.totalVnd)}đ.`, footer: _jsxs(_Fragment, { children: [_jsx(Button, { label: "\u0110\u00FAng r\u1ED3i, ghi v\u00E0o s\u1ED5", onPress: onConfirm }), _jsx(Button, { label: "S\u1EEDa l\u1EA1i", tone: "quiet", onPress: onBack })] }), children: _jsxs(ScrollView, { contentContainerStyle: { gap: space.md }, children: [_jsxs(Card, { children: [people.map((person) => (_jsx(Row, { left: person.id === proposal.advancerId ? `${person.name} (trả trước)` : person.name, right: `${formatVnd(proposal.allocations[person.id])}đ`, muted: person.id === proposal.advancerId }, person.id))), _jsx(View, { style: { height: 1, backgroundColor: c.line, marginVertical: space.xs } }), _jsx(Row, { left: "T\u1ED5ng", right: `${formatVnd(proposal.totalVnd)}đ` })] }), proposal.roundingGainers.length > 0 ? (_jsx(Card, { children: _jsxs(Text, { style: { ...type.label, color: c.inkSoft }, children: ["Chia kh\u00F4ng h\u1EBFt ch\u1EB5n. ", gainerNames.join(", "), " ch\u1ECBu th\u00EAm 1\u0111 l\u1EBB, v\u00EC ", proposal.advancerId === proposal.roundingGainers[0] ? "là người trả trước" : "theo thứ tự cố định", "."] }) })) : null, _jsx(Card, { children: _jsxs(Text, { style: { ...type.label, color: c.inkSoft }, children: [owed.length, " ng\u01B0\u1EDDi s\u1EBD c\u1EA7n g\u1EEDi ti\u1EC1n cho ", advancerName, ". Ch\u01B0a ai b\u1ECB nh\u1EAFn g\u00EC cho t\u1EDBi khi b\u1EA1n ph\u00E1t \u0111\u1EE3t thu."] }) })] }) }));
}
