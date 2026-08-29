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

/** The direction contract for the group chat screens (rd-fe-07).
 *
 * Its own contract again, and the failure mode it guards is new: the other
 * three screens are about a number, this one is about *who is speaking*. A
 * group thread where the machine's voice is indistinguishable from a friend's
 * is the defect, and it is the reason the one deliberate departure from the
 * mockup is written into the OWN-WORLD block rather than left in a commit
 * message.
 *
 * That departure: the mockup paints the screen header purple. Here it is
 * `accent` orange like the rest of the shell, because `ai` purple has exactly
 * one meaning in this palette -- "a machine made this" -- and spending it on
 * the header would say the whole conversation was machine-written.
 */
export const DIRECTION_CONTRACT_NHOM_CHAT = `
THESIS: AI ngoi trong nhom chu khong dung ngoai. No doc ngu canh roi tu len
tieng, va thu no noi ra la mot ke hoach bam vao duoc, khong phai chu tron.

OWN-WORLD: The gioi Ru Di, khong them mau. Dan cam "accent" nhu vo tab. Tim
"ai" cham dung ba cho: avatar AI, nhan "Ru Di AI", the ke hoach. Mockup ve dau
man tim; o day khong, vi tim trong he nay co nghia la "may sinh ra", va mot dau
man tim lam ca doan chat trong nhu do may viet.

STORY: Cuon nguoc len thay nhom ban gi. Go mot cau, gui. AI tu noi, khong ai
goi ten no. Cau cua no la mot the lich trinh, bam vao la sang man ke hoach.

FIRST VIEWPORT: Avatar nhom + so thanh vien that, hang bon chip Chat/Plan/Thanh
vien/File, ba bong bong cuoi cua dong tin, o nhap ghim day man.

FORM: Bong bong cua minh lech phai nen "accentSoft"; cua nguoi khac lech trai
nen "card" vien "line"; cua AI rong het be ngang nen "aiSoft" vien "ai". Vien
cua thu bam duoc la "lineStrong". Gio o moi bong bong, co "micro". Bam >= 44.

FINISH: build fully, then hand off to the finish reviewer with captures.
`.trim();

/** The direction contract for the group vote (rd-fe-13, F17).
 *
 * An EXTENSION of the chat world, not a new one. The vote lives inside the
 * thread because that is where the argument it settles is happening, and a
 * decision moved to its own tab stops being part of the conversation.
 *
 * The one hard rule this surface exists to hold: a TIE IS A RESULT. The
 * mockup crowns a single winner, which is the easy case. When two options
 * tie, this screen says so and crowns neither. Picking one -- by list order,
 * by who voted first, by anything -- would be the app casting the deciding
 * vote, and nobody asked it to. Hiding the tie behind a rounded percentage
 * would be worse: it would look decided.
 */
export const DIRECTION_CONTRACT_BINH_CHON = `
THESIS: Nhom tu quyet, may chi dem. Man nay dem phieu that va noi ro ket qua,
ke ca khi ket qua la HOA.

OWN-WORLD: The gioi Ru Di, khong them mau. Dan tim "ai" vi cau hoi thuong do
Ru Di dat ra tu the dia diem no vua goi y. KHONG dan teal: teal nghia la tien
dang duoc chia, ma o day chua ai tra dong nao.

STORY: AI goi y may quan, ai do mo binh chon tu chinh nhung the do. Moi nguoi
bam mot lua chon, doi y thi bam lai. Ai cung thay so phieu, ngay lap tuc.

FIRST VIEWPORT: Cau hoi in dam, roi tung lua chon mot hang: vong tron chon,
ten quan, thanh phan tram, so phieu. Hang dang dan co vien tim va vuong mien.
Chan the: "N/M thanh vien da bo phieu".

FORM: So phieu la su that, phan tram chi la nhan. Phan tram lam tron theo du
lon nhat nen tong luon dung 100. Hoa thi hien chip "Hoa" va KHONG vuong mien
cho ai. Vong bam >= 44. Thanh phan tram khong bao gio la thu duy nhat mang
thong tin -- so phieu luon in ra bang chu.

FINISH: build fully, then hand off to the finish reviewer with captures.
`.trim();

/** The direction contract for the outing screens (rd-fe-12, F13 + F15).
 *
 * An EXTENSION again: no new colour, radius or type step. The one decision
 * worth writing down is the lead tone, because two of the three carry a
 * meaning that would be wrong here.
 *
 * DESIGN.md gives teal "split" to money being divided or settled, and purple
 * "ai" to what a machine produced. A budget per person on this screen is
 * neither: nobody owes it, and a person typed it. Leading teal would say the
 * group is settling up on a screen where no money has moved, and leading
 * purple would say the plan was generated when a member wrote it. So the lead
 * is orange "accent", the same tone the tab bar and every other
 * human-authored action already use.
 *
 * That is also why the budget is never drawn in "warn". The brief calls it a
 * reference figure rather than a cap, and a red number is an assertion that
 * something is wrong -- here, nothing is.
 */
export const DIRECTION_CONTRACT_BUOI_DI = `
THESIS: Mot dia diem da chon chua phai mot chuyen di. Man nay bien no thanh
chuyen di: co ten, co ngay, co so nguoi, va co gio giac bam vao duoc.

OWN-WORLD: The gioi Ru Di, khong them mau. Dan cam "accent". KHONG dan teal,
vi teal trong he nay nghia la tien dang duoc chia hay quyet toan, ma o day
chua ai no ai dong nao. KHONG dan tim, vi tim nghia la may sinh ra, ma lich
trinh nay do nguoi trong nhom go.

STORY: Tu Kham pha bam sang, ten quan da nam san trong o dau tien. Dien ten,
khoang ngay, so nguoi, ngan sach. Tao xong thi chuyen hien ra rong, va tung
chang duoc them vao theo gio.

FIRST VIEWPORT: Tieu de man, the chuyen dang mo voi ten va khoang ngay, hang
"N nguoi" va "ngan sach moi nguoi", roi dau duong thoi gian. Nut tao ghim
duoi.

FORM: Duong thoi gian la mot ray doc: cham tron ben trai, gio chu so tabular,
nhan va ten quan ben phai. Ngan sach dinh dang tien Viet co dau cham nghin,
kem chu "tham chieu"; khong to mau canh bao du vuot. Bam >= 44.

FINISH: build fully, then hand off to the finish reviewer with captures.
`.trim();
