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

/** The direction contract for the per-person split screen (rd-fe-04).
 *
 * Its own contract rather than an extra paragraph in the one above, because it
 * is a different surface with a different failure mode: those two screens are
 * about a number being read correctly, this one is about a number being
 * attributed to the right person. Same world, same tokens, same lead tone.
 */
export const DIRECTION_CONTRACT_GOI_Y = `
THESIS: May doc tien in tren giay, khong doc duoc ai da an gi. Nguoi noi dieu
do; may chu moi chia tien.

OWN-WORLD: The gioi Ru Di, khong them mau. Dan teal "split". Tim "ai" chi danh
dau do tin cay cua ban doc va goi y mac dinh.

STORY: Hang avatar: ai o day, moi nguoi chiu bao nhieu. Ma tran mon x nguoi.
Tich mot o, so tren dau doi; so do cua may chu, khong phai app tu tinh.

FIRST VIEWPORT: Hang avatar kem so, chip "Theo mon" / "Theo %", cau "Chon nguoi
da an mon nay", ba dong mon dau.

FORM: Cot co dinh, khong cuon ngang. Buoc cot >= 44. Dong qua thi chip "n/m"
mo bang chon toan man.

FINISH: build fully, then hand off to the finish reviewer with captures.
`.trim();

/** The direction contract for the settlement screen (rd-fe-05).
 *
 * Its own contract for the same reason the previous two have theirs: the
 * failure mode is different again. The bill screens are about reading a number
 * correctly, the matrix is about attributing it to the right person, and this
 * one is about a number LEAVING somebody's bank account. Nothing on it may be
 * computed here, and nothing on it may look more settled than it is.
 */
export const DIRECTION_CONTRACT_KET_QUA = `
THESIS: Toi chuyen bao nhieu, cho ai, bang cach nao. Ba cau tra loi, dung thu
tu do. Moi con so tren man deu do may chu gui ve; app khong cong tru gi.

OWN-WORLD: The gioi Ru Di, khong them mau. Dan bang teal "split" -- day la buoc
quyet toan. Khong dung tim "ai": khong con gi tren man nay do may doan.

STORY: Tong hoa don o tren. Roi phan cua tung nguoi. Roi ai chuyen cho ai. Roi
mot ma quet duy nhat, cua dung nguoi dang chon. Di tu nhom ve mot nguoi.

FIRST VIEWPORT: So tong co display tren nen kem, dong "N mon - M nguoi", roi
the "So tien moi nguoi phai tra" voi ba dong dau nhin thay duoc.

FORM: The trang tren nen kem, so tabular canh phai. QR la o vuong den trang co
le trang 4 module, khong bo goc, khong long logo vao giua. So tai khoan che het
tru bon so cuoi.

FINISH: build fully, then hand off to the finish reviewer with captures.
`.trim();
