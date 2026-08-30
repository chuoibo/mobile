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
"ai" cham dung bon cho: avatar AI, nhan "Ru Di AI", the ke hoach, va nut "Hoi
Ru Di AI" -- nut goi may thi mang mau may, khong thi no lan giua ba nut chua
dung. Vien va nen nhat, khong phai thanh tim dac: dac se lan at nut Gui.
Mockup ve dau man tim; o day khong, vi tim trong he nay co nghia la "may sinh
ra", va mot dau man tim lam ca doan chat trong nhu do may viet.

STORY: Cuon nguoc len thay nhom ban gi. Go mot cau, gui. AI tu noi, khong ai
goi ten no. Hoi ai muon hoi thang thi co nut, va luot do AI luon tra loi mot
cau -- ke ca cau tu choi. Cau cua no la mot the lich trinh, bam vao la sang
man ke hoach.

FIRST VIEWPORT: Avatar nhom + so thanh vien that, hang bon chip Chat/Plan/Thanh
vien/File, ba bong bong cuoi cua dong tin, nut "Hoi Ru Di AI" va o nhap ghim
day man.

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
 *
 * AMENDED BY rd-fe-17 (F34), and the amendment is to that last paragraph.
 *
 * "Here, nothing is" was true of rd-fe-12 because the screen had no spend
 * figure: a budget on its own can be large or small but it cannot be exceeded,
 * so red would have been an assertion with nothing behind it. F34 puts the
 * ledger's own `split_total_vnd` next to it, and once a measured total is
 * larger than the figure the group agreed on, something IS wrong, and it is
 * exactly the kind of wrong this product exists to surface early.
 *
 * So "warn" is now earned, under one condition and no other: the ledger
 * returned a total for this trip AND that total is greater than
 * `budget_per_person_vnd * headcount`. The budget by itself is still never
 * drawn in warn, an unread or absent spend figure is never drawn in warn, and
 * no new colour enters the world -- "warn" is already in the palette, and this
 * is still an extension rather than a second identity.
 *
 * Colour is never the only carrier. The overspend is written out in words and
 * đồng ("Vượt ngân sách. Vượt 1.200.000đ"), because red is invisible to some
 * of the people holding this phone and survives no screenshot at all.
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
kem chu "tham chieu". Bam >= 44.

NGAN SACH (rd-fe-17, F34): duoi hang tham chieu la mot khoi ngan cach bang
mot duong ke, ghi "Da tieu X / ngan sach Y" roi mot dong ket luan. So da tieu
doc tu so cai qua recap, khong tinh lai tren may. Chi to "warn" khi so cai CO
so va so do LON HON ngan sach; ban than ngan sach va truong hop thieu so thi
khong bao gio to warn. Khong phan tram, khong thanh bar: ca hai deu can phep
chia, ma luat tien cam so thuc ke ca o gia tri trung gian. Muc vuot luon
viet ra bang chu va bang dong, mau chi la kenh thu hai.

FINISH: build fully, then hand off to the finish reviewer with captures.
`.trim();

/** The direction contract for the group map screens (rd-fe-33: F43, F44, F45).
 *
 * An EXTENSION of Khám phá, not a new world. The three routes behind it landed
 * in the same PR (`/contexts/{id}/map`, `/heatmap`, `/meet`), and the screens
 * exist so those routes are not four addresses nobody calls.
 *
 * The hard part here is not the drawing. It is that every one of these screens
 * summarises where a group of people physically was, so each block below is as
 * much a privacy decision as a visual one.
 */
export const DIRECTION_CONTRACT_BAN_DO = `
THESIS: Ban do nay khong noi AI da o dau. No noi NHOM hay lui toi cho nao, va
noi luon no da dem tu bao nhieu lan check-in de ra con so do.

OWN-WORLD: The gioi Ru Di, khong them mau. Dan cam "accent" nhu Kham pha, vi
day van la mat di kham pha. KHONG dan teal (teal la tien dang chia) va KHONG
dan tim (tim la may sinh ra) -- ba man nay chi dem hang co that trong so.

STORY: Tu dai ban do o Kham pha bam vao. Ba lop hien theo thu tu chac chan
giam dan: da di (dem duoc), dang hot (may xep), nen thu (may goi y). Lop thu
tu "da luu" duoc GOI TEN la chua dung, khong ve mang rong.

FIRST VIEWPORT: Tieu de man, mot dong noi ro da quet bao nhieu check-in, roi
lop "Da di" voi so lan ben canh tung cho. Cau tiet lo di TRUOC danh sach chu
khong phai chu thich duoi chan.

FORM: Danh sach chu khong phai chum cham -- o do phan giai nay tin that la
"quan nay N lan", khong phai "cho nay o day". Nhiet do ve bang thanh ngang
theo share_percent, nhung SO LAN moi la phan doc duoc: ADR-0009 cam phan tram
noi voi nguoi dung, nen share_percent chi vao BE RONG cua thanh chu khong bao
gio thanh chu. So lan dung chu so tabular. Bam >= 44.

DIEM HEN (F45): man DUY NHAT co canh bao truoc khi thu thap. Khi nguoi dung
moi chon dung hai khu vuc, may chu tra co two_origin_inversion, va man phai
noi "hai dau thi suy nguoc duoc" TRUOC khi ai do dua ket qua cho nguoi thu
hai xem. Ket qua xep theo quang duong NGUOI XA NHAT phai di, va con so do in
ra canh ten quan de nguoi doc kiem duoc, chu khong bat tin chu "can bang".

FINISH: build fully, then hand off to the finish reviewer with captures.
`.trim();

/** The direction contract for the three routes nothing on the phone called
 *  (rd-fe-37): F24 chat expense draft, F14 outing invite accept, F26
 *  screenshot scan.
 *
 * One contract for three surfaces because they share the failure they exist to
 * avoid, and it is a wording failure rather than a drawing one. Each of these
 * three routes gives back LESS than the screen would like to say:
 *
 *  - `expense-draft` returns a draft and writes nothing. Its own docstring
 *    says so: "this route never creates or allocates an expense."
 *  - `outing-invites/{token}/accept` deliberately withholds the group name and
 *    the trip name, because the person redeeming a link is not a member yet.
 *  - `screenshots/scan` returns one merchant and one total, never a line-item
 *    breakdown and never a person.
 *
 * So the design job here is subtraction. A card that fills those holes with
 * something reassuring is the defect, not the empty space.
 */
export const DIRECTION_CONTRACT_BA_ROUTE = `
THESIS: Ba man nay deu la MAY DA DOC XONG, NGUOI CHUA CHOT. Moi man phai noi
duoc cai no chua lam, bang chu, o cho nguoi doc truoc khi bam.

OWN-WORLD: Ke thua the gioi Ru Di, khong them mau nao. Tim "ai" cho hai ban doc
cua may (nhap tu chat, quet anh chup) vi DESIGN.md dinh nghia tim la "thu do
may sinh ra, nguoi con sua duoc" -- dung dinh nghia cua mot ban nhap. Cam
"accent" cho man nhan loi moi, vi do la hanh dong cua NGUOI chu khong phai ban
doc cua may. Teal "split" chi cham vao con so tien, khong bao gio dan man.

STORY: F24 -- duoi moi tin nhan chu co nut "Tach tien"; bam thi the tim moc
ngay duoi DUNG tin do, khong nhay man. F26 -- tu khung den cua Chup bill, nut
thu hai "Anh chup man hinh"; doc xong ra the tim, chot thi roi vao form nhap
tay da dien san. F14 -- link mo thang mot the giua man: mot cau, mot nut.

FIRST VIEWPORT: F24 va F26 khong co first viewport rieng, chung moc trong man
da co. F14 mo bang dung mot the: "Ban duoc moi vao mot buoi di", nut "Nhan loi
moi", va mot cau noi ro app chua biet do la buoi di nao.

FORM: The, khong phai bang -- ba ban doc nay deu it dong. Con so tien dung chu
so tabular nhu moi cho khac. Bam >= 44. Cau "chua ghi gi" nam TRONG the, tren
nut, chu khong phai chu thich duoi chan: no la dieu kien de bam nut chu khong
phai ghi chu ve nut.

FINISH: build fully, then hand off to the finish reviewer with captures.
`.trim();

/** The direction contract for the two self-tagging screens, F22 (rd-fe-22).
 *
 * F17's server-backed vote screen deliberately has NO contract of its own: it
 * runs under `DIRECTION_CONTRACT_BINH_CHON` above, unchanged. That contract was
 * written for the message-backed card, and every line of it is about the
 * surface rather than the transport -- a tie is a result, no teal because
 * nobody has paid anything yet, the count is visible to everyone at once. None
 * of that changes when the tally starts arriving from `GET /votes/{id}` instead
 * of being folded out of chat messages. Writing a second contract here would
 * have been a second answer to a question already answered, which is the same
 * mistake as a second vote counter.
 *
 * These two screens do need their own, because their failure mode is new. The
 * vote screen must not break a tie; these must not let the MACHINE say who a
 * person is. A rectangle is a rectangle, and a dish is claimed by whoever is
 * holding the phone. Both are undecided on purpose, and both look unfinished
 * because of it, which is exactly the pressure this contract exists to resist.
 *
 * An EXTENSION. No colour, radius or type step that `packages/shared/tokens.json`
 * does not already own.
 */
export const DIRECTION_CONTRACT_NHAN_PHAN_MINH = `
THESIS: May khoanh, nguoi tu nhan. O vuong tren anh la mot hinh chu nhat, khong
phai mot cai ten. Mon an la cua nguoi dang cam may, khong phai cua ai khac.

OWN-WORLD: Ke thua the gioi Ru Di, khong them mau. Cam "accent" dan man anh: day
la hanh dong cua NGUOI. Teal "split" chi cham vao dong tien cua mon da nhan, va
chi o man mon. Tim "ai" chi dat len o vuong may khoanh, khong bao gio len phan
nguoi da tu nhan.

STORY: May khoanh cac o vuong vo danh tren anh nhom, toi bam o cua toi. O man
bill, toi tich nhung mon toi da an; danh sach gui di la TOAN BO phan toi nhan,
nen bo tich la nha mon ra chu khong phai giu lai.

FIRST VIEWPORT: Man anh mo bang chinh tam anh, o vuong ve ngay tren no, mot cau
noi ro may khong biet ai la ai. Man mon mo bang ba dong mon dau va dong "Phan
cua ban" ghim duoi.

FORM: O vuong ve theo ti le anh, khong theo pixel -- box_key khong on dinh giua
hai lan goi nen khong duoc luu. Bam >= 44. So tien dung chu so tabular, canh
phai. Trang thai da chon mang ca dau tich lan chu, khong chi mau.

FINISH: build fully, then hand off to the finish reviewer with captures.
`.trim();
