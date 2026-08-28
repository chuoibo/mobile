import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
/** Share one link, to one person, one at a time.
 *
 * Spec section 8.5 is explicit and this screen is built around the absence:
 * there is no "copy all", no bundle export, no bulk share. The organiser can
 * still paste links into a group chat by hand, and the product neither helps
 * with that nor claims to detect it. What it can do is refuse to make it easy.
 */
import { useState } from "react";
import { ScrollView, Share, Text, View } from "react-native";
import { formatVnd } from "../../../../packages/shared/money.mjs.js";
import { radius, space, type, usePalette } from "../theme.js";
import { Button, Card, Screen } from "../ui/Kit.js";
export function ChiaSe({ envelopes, onDone }) {
    const c = usePalette();
    const [shared, setShared] = useState({});
    const [problem, setProblem] = useState(null);
    async function shareOne(envelope) {
        // One capability, one person, one share sheet. The warning goes in the
        // message body so it travels with the link.
        const message = `Phần của ${envelope.senderName}: ${formatVnd(envelope.amountVnd)}đ\n${envelope.url}\n\n` +
            `Link này dành cho ${envelope.senderName}; ai có link đều xem được phần của ${envelope.senderName}.`;
        try {
            const result = await Share.share({ message });
            // A person can open the sheet and back out. That is not sending, and
            // marking it sent would tell the organiser a lie about who has been
            // contacted -- the one thing this screen exists to keep track of.
            if (result.action === Share.dismissedAction)
                return;
            setShared((current) => ({ ...current, [envelope.senderId]: true }));
            setProblem(null);
        }
        catch {
            // There is no share sheet in a desktop browser, and the rejection used
            // to escape as an unhandled promise. Say what to do instead of dying:
            // the link is the deliverable, and it can be copied by hand.
            setProblem(`Máy này không mở được khay chia sẻ. Chép link của ${envelope.senderName} rồi gửi tay: ${envelope.url}`);
        }
    }
    return (_jsxs(Screen, { title: "Chia s\u1EBB", hint: "M\u1ED7i ng\u01B0\u1EDDi m\u1ED9t link ri\u00EAng. G\u1EEDi ri\u00EAng cho t\u1EEBng ng\u01B0\u1EDDi.", footer: _jsxs(_Fragment, { children: [problem ? (_jsx(Text, { style: { ...type.label, color: c.warn }, children: problem })) : null, _jsx(Button, { label: "Xong", tone: "quiet", onPress: onDone })] }), children: [_jsx(Card, { children: _jsx(Text, { style: { ...type.label, color: c.inkSoft }, children: "Kh\u00F4ng c\u00F3 n\u00FAt g\u1EEDi h\u00E0ng lo\u1EA1t. D\u00E1n chung v\u00E0o nh\u00F3m th\u00EC c\u1EA3 nh\u00F3m th\u1EA5y ph\u1EA7n c\u1EE7a nhau, v\u00E0 app kh\u00F4ng bi\u1EBFt \u0111\u01B0\u1EE3c \u0111i\u1EC1u \u0111\u00F3 \u0111\u00E3 x\u1EA3y ra." }) }), _jsx(ScrollView, { contentContainerStyle: { gap: space.sm }, children: envelopes.map((e) => (_jsxs(View, { style: {
                        backgroundColor: c.card, borderColor: c.line, borderWidth: 1,
                        borderRadius: radius.base, padding: space.md, gap: space.sm,
                    }, children: [_jsxs(View, { style: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" }, children: [_jsx(Text, { style: { ...type.body, color: c.ink }, children: e.senderName }), _jsxs(Text, { style: { ...type.amountSmall, color: c.ink }, children: [formatVnd(e.amountVnd), "\u0111"] })] }), _jsx(Button, { label: shared[e.senderId] ? `Gửi lại cho ${e.senderName}` : `Gửi cho ${e.senderName}`, tone: shared[e.senderId] ? "quiet" : "ghost", onPress: () => shareOne(e) }), _jsx(Text, { style: { ...type.label, color: e.opened ? c.accent : c.inkSoft }, children: e.opened ? "Đã mở link" : shared[e.senderId] ? "Đã mở khay chia sẻ, chưa rõ đã mở link chưa" : "Chưa chia sẻ" })] }, e.senderId))) })] }));
}
