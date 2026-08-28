import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Pressable, Text, TextInput, View } from "react-native";
import { radius, space, type, usePalette } from "../theme.js";
export function Screen({ title, hint, children, footer }) {
    const c = usePalette();
    return (_jsxs(View, { style: { flex: 1, backgroundColor: c.ground, padding: space.md, gap: space.md }, children: [_jsxs(View, { style: { gap: space.xs }, children: [_jsx(Text, { style: { ...type.title, color: c.ink }, children: title }), hint ? _jsx(Text, { style: { ...type.label, color: c.inkSoft }, children: hint }) : null] }), _jsx(View, { style: { flex: 1, gap: space.md }, children: children }), footer ? _jsx(View, { style: { gap: space.sm }, children: footer }) : null] }));
}
export function Card({ children, style }) {
    const c = usePalette();
    return (_jsx(View, { style: [{
                backgroundColor: c.card, borderColor: c.line, borderWidth: 1,
                borderRadius: radius.base, padding: space.md, gap: space.sm,
            }, style], children: children }));
}
export function Button({ label, onPress, tone = "primary", disabled }) {
    const c = usePalette();
    const skin = {
        primary: { backgroundColor: c.accent, borderColor: c.accent },
        ghost: { backgroundColor: "transparent", borderColor: c.accent },
        quiet: { backgroundColor: "transparent", borderColor: c.line },
    };
    const ink = tone === "primary" ? c.accentInk : tone === "ghost" ? c.accent : c.inkSoft;
    return (_jsx(Pressable, { onPress: onPress, disabled: disabled, accessibilityRole: "button", style: ({ pressed }) => [{
                borderWidth: 1, borderRadius: radius.base,
                paddingVertical: 14, paddingHorizontal: space.md,
                alignItems: "center",
                opacity: disabled ? 0.4 : pressed ? 0.85 : 1,
            }, skin[tone]], children: _jsx(Text, { style: { ...type.body, fontWeight: "600", color: ink }, children: label }) }));
}
export function Field({ label, value, onChangeText, keyboardType, placeholder }) {
    const c = usePalette();
    return (_jsxs(View, { style: { gap: space.xs }, children: [_jsx(Text, { style: { ...type.label, color: c.inkSoft }, children: label }), _jsx(TextInput, { value: value, onChangeText: onChangeText, keyboardType: keyboardType ?? "default", placeholder: placeholder, placeholderTextColor: c.inkSoft, style: {
                    ...type.body, color: c.ink, backgroundColor: c.card,
                    borderColor: c.line, borderWidth: 1, borderRadius: radius.base,
                    paddingHorizontal: space.md, paddingVertical: 12,
                } })] }));
}
export function Row({ left, right, muted }) {
    const c = usePalette();
    return (_jsxs(View, { style: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", gap: space.sm }, children: [_jsx(Text, { style: { ...type.body, color: muted ? c.inkSoft : c.ink, flexShrink: 1 }, children: left }), _jsx(Text, { style: { ...type.amountSmall, color: muted ? c.inkSoft : c.ink }, children: right })] }));
}
/** Pick one of a few people. A free-text field cannot name a person when two
 *  of them are called Nam, so anywhere identity matters this replaces typing. */
export function Choice({ label, options, value, onChange }) {
    const c = usePalette();
    return (_jsxs(View, { style: { gap: space.xs }, children: [_jsx(Text, { style: { ...type.label, color: c.inkSoft }, children: label }), _jsxs(View, { style: { flexDirection: "row", flexWrap: "wrap", gap: space.xs }, children: [options.length === 0 ? (_jsx(Text, { style: { ...type.body, color: c.inkSoft }, children: "Nh\u1EADp t\u00EAn ph\u00EDa tr\u00EAn tr\u01B0\u1EDBc." })) : null, options.map((o) => {
                        const on = o.id === value;
                        return (_jsx(Pressable, { onPress: () => onChange(o.id), accessibilityRole: "radio", accessibilityState: { selected: on }, style: ({ pressed }) => ({
                                borderWidth: 1, borderRadius: radius.base,
                                paddingVertical: 10, paddingHorizontal: space.md,
                                borderColor: on ? c.accent : c.line,
                                backgroundColor: on ? c.accent : "transparent",
                                opacity: pressed ? 0.85 : 1,
                            }), children: _jsx(Text, { style: { ...type.body, fontWeight: on ? "600" : "400", color: on ? c.accentInk : c.ink }, children: o.label }) }, o.id));
                    })] })] }));
}
