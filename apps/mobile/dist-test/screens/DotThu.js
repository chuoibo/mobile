import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { ScrollView, Text, View } from "react-native";
import { formatVnd } from "../../../../packages/shared/money.mjs.js";
import { radius, space, type, usePalette } from "../theme.js";
import { canPublish } from "../api.js";
import { Button, Card, Screen } from "../ui/Kit.js";
const TRANSFERRED = new Set(["confirmed", "over_confirmed"]);
const NOTHING_LEFT = new Set([...TRANSFERRED, "waived"]);
const WORDING = {
    outstanding: "chưa gửi",
    partially_confirmed: "gửi một phần",
    confirmed: "đã nhận",
    over_confirmed: "nhận dư",
    waived: "được bỏ qua",
    disputed: "đang thắc mắc",
};
export function DotThu({ obligations, published, gates, onPublish, onShare, onAcknowledge, onSetRecipient, }) {
    const c = usePalette();
    const ready = canPublish(gates);
    const done = obligations.filter((o) => TRANSFERRED.has(o.status)).length;
    const senders = new Set(obligations.map((o) => o.senderId));
    const peopleDone = [...senders].filter((id) => obligations.filter((o) => o.senderId === id).every((o) => NOTHING_LEFT.has(o.status))).length;
    return (_jsxs(Screen, { title: "\u0110\u1EE3t thu", hint: published ? "Đã phát. Ai cũng xem được phần của mình." : "Chưa phát. Chưa ai bị nhắn gì.", footer: published ? (_jsx(Button, { label: "Chia s\u1EBB cho t\u1EEBng ng\u01B0\u1EDDi", onPress: onShare })) : (_jsxs(_Fragment, { children: [_jsx(Button, { label: "Ph\u00E1t \u0111\u1EE3t thu", disabled: !ready, onPress: onPublish }), !ready ? (_jsx(Text, { style: { ...type.label, color: c.inkSoft }, children: "C\u00F2n c\u1ED5ng ch\u01B0a qua. Kh\u00F4ng ai b\u1ECB nh\u1EAFn g\u00EC cho t\u1EDBi khi c\u1EA3 hai xong." })) : null] })), children: [_jsxs(Card, { children: [_jsxs(Text, { style: { ...type.amount, color: c.ink }, children: [done, "/", obligations.length, _jsx(Text, { style: { ...type.body, color: c.inkSoft }, children: "  l\u01B0\u1EE3t chuy\u1EC3n xong" })] }), _jsxs(Text, { style: { ...type.label, color: c.inkSoft }, children: [peopleDone, "/", senders.size, " ng\u01B0\u1EDDi \u0111\u00E3 xong to\u00E0n b\u1ED9"] })] }), !published ? (_jsxs(Card, { children: [_jsx(Text, { style: { ...type.label, color: c.inkSoft }, children: "Tr\u01B0\u1EDBc khi ph\u00E1t" }), _jsxs(View, { style: { gap: 2 }, children: [_jsxs(Text, { style: { ...type.body, color: gates.payerAcknowledged ? c.accent : c.ink }, children: [gates.payerAcknowledged ? "✓" : "○", " Ng\u01B0\u1EDDi \u1EE9ng ti\u1EC1n \u0111\u00E3 x\u00E1c nh\u1EADn"] }), !gates.payerAcknowledged ? (_jsxs(_Fragment, { children: [_jsx(Text, { style: { ...type.label, color: c.inkSoft }, children: "App kh\u00F4ng g\u1EEDi g\u00EC d\u01B0\u1EDBi t\u00EAn m\u1ED9t ng\u01B0\u1EDDi tr\u01B0\u1EDBc khi h\u1ECD \u0111\u1ED3ng \u00FD." }), _jsx(Button, { label: "T\u00F4i l\u00E0 ng\u01B0\u1EDDi \u1EE9ng ti\u1EC1n, t\u00F4i x\u00E1c nh\u1EADn", tone: "quiet", onPress: onAcknowledge })] })) : null] }), _jsxs(View, { style: { gap: 2 }, children: [_jsxs(Text, { style: { ...type.body, color: gates.recipientReady ? c.accent : c.ink }, children: [gates.recipientReady ? "✓" : "○", " C\u00F3 t\u00E0i kho\u1EA3n nh\u1EADn"] }), !gates.recipientReady ? (_jsxs(_Fragment, { children: [_jsx(Text, { style: { ...type.label, color: c.inkSoft }, children: gates.recipientProblem ?? "Chưa rõ chuyển tiền về đâu." }), _jsx(Button, { label: "Nh\u1EADp t\u00E0i kho\u1EA3n nh\u1EADn", tone: "quiet", onPress: onSetRecipient })] })) : null] })] })) : null, _jsx(ScrollView, { contentContainerStyle: { gap: space.sm }, children: obligations.map((o) => {
                    const settled = TRANSFERRED.has(o.status);
                    const flagged = o.status === "disputed";
                    return (_jsxs(View, { style: {
                            backgroundColor: c.card, borderColor: flagged ? c.warn : c.line,
                            borderWidth: 1, borderRadius: radius.base,
                            padding: space.md, flexDirection: "row",
                            justifyContent: "space-between", alignItems: "center", gap: space.sm,
                        }, children: [_jsxs(View, { style: { flexShrink: 1, gap: 2 }, children: [_jsxs(Text, { style: { ...type.body, color: c.ink }, children: [o.senderName, " ", _jsx(Text, { style: { color: c.inkSoft }, children: "g\u1EEDi" }), " ", o.recipient] }), _jsx(Text, { style: { ...type.label, color: flagged ? c.warn : settled ? c.accent : c.inkSoft }, children: WORDING[o.status] })] }), _jsxs(Text, { style: { ...type.amountSmall, color: settled ? c.accent : c.ink }, children: [formatVnd(o.amountVnd), "\u0111"] })] }, o.id));
                }) })] }));
}
