/** The direction contract for the bill-reading screens.
 *
 * Impeccable asks for this before the first line of UI code, as a comment the
 * build emits so a reviewer can audit the artifact against what it promised.
 * An Expo app has no HTML shell of its own to put it in, so it is emitted into
 * `dist/index.html` by `public/index.html`, and it is repeated here because
 * this is the file the people writing the screens actually open.
 *
 * These two screens are an EXTENSION, not a new world. The identity was
 * already decided and measured -- `packages/shared/tokens.json`, DESIGN.md --
 * and nothing here introduces a colour, a radius or a type step that the
 * system does not already own.
 */
export const DIRECTION_CONTRACT = `
THESIS: May doc bill; nguoi chiu trach nhiem ve con so. Man hinh cho thay ca hai.

OWN-WORLD: Ke thua the gioi Ru Di. Man 1 dan bang den cua khung ngam. Man 2 dan
bang teal "split" theo DESIGN.md, nen nut chinh teal chu khong cam. Tim chi danh
dau phan may sinh ra.

STORY: Dua bill vao khung, may doc, moi con so go lai duoc, khoang lech so voi
dong Tong cong in tren giay hien ngay.

FIRST VIEWPORT: Man 1 chi co bon goc khung ngam, mot cau huong dan, mot nut tron
trang. Man 2 mo bang chip "Da nhan dien N mon", roi den bang nhap duoc.

FORM: Bang thay vi the. Chu so tabular. Cham vao con so la sua duoc no. Tong cong
va khoang lech ghim ngoai vung cuon.

FINISH: build fully, then hand off to the finish reviewer with captures.
`.trim();
