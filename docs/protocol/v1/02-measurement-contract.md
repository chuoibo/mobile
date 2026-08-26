# Protocol v1 — Measurement contract

`protocol_version: v1` · **DRAFT** · DRI Claude · Reviewer Codex

> **Đây là thứ W1 phải hiện thực.** Study instrument log **sự kiện quan sát được**, không log trạng thái sản phẩm giả định. Nếu instrument tự phát minh thêm trường, protocol đã bị công cụ viết lại — đúng chế độ hỏng mà ADR-0001 cố tránh.

## 1. Ranh giới không được vượt

### ✅ Log cái này — sự kiện quan sát được
`operator_action_started` · `organizer_input_submitted` · `organizer_edit` · `proposal_shown_to_organizer`

### ❌ KHÔNG log cái này — trạng thái sản phẩm giả định
`CollectionBatch.published` · `SkillInvocation.succeeded` · `Proposal.confirmed` · `Envelope.opened` · bất kỳ tên thực thể nào trong mục 6 của spec

Lý do: đặt tên sự kiện theo ontology sản phẩm biến bản ghi nghiên cứu thành bằng chứng ủng hộ chính mô hình dữ liệu chưa được kiểm chứng. Dữ liệu sau đó sẽ "xác nhận" schema mà không ai từng kiểm chứng nó.

## 2. Trường bắt buộc trên MỌI sự kiện

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `event_id` | uuid | |
| `schema_version` | string | Version của chính contract này |
| `protocol_version` | string | `v1` |
| `occurred_at` | ISO8601 + offset | Lúc việc **xảy ra** |
| `recorded_at` | ISO8601 + offset | Lúc việc **được ghi**. Chênh lệch lớn = tín hiệu ghi log muộn, dữ liệu kém tin |
| `study_group_id` | pseudonym | **Không bao giờ** là tên nhóm thật |
| `study_subject_id` | pseudonym \| null | |
| `actor_role` | enum | `organizer` · `sender` · `operator` · `system` · `researcher` |
| `cohort` | enum | Khoá lúc intake |
| `lane` | enum | `v1_scope` · `exploration` |
| `cycle` | enum | `baseline` · `concierge_1` · `concierge_2` · … |

Múi giờ chuẩn `Asia/Ho_Chi_Minh`, lưu UTC kèm offset.

## 3. Trường BỊ CẤM trong log

❌ Tên thật · số điện thoại · email · số tài khoản · tên ngân hàng gắn với người · ảnh bill · text thô tin nhắn của participant · tên nhóm chat.

Text tự do (lý do rescue, ghi chú operator) sống ở **kho dữ liệu ngoài repo**, tham chiếu bằng `note_ref`. Log mang **mã lý do có enum**, không mang câu chữ.

Lý do: log là thứ sẽ được copy, export, đưa vào script phân tích, dán vào issue. Mỗi lần copy là một cơ hội rò.

## 4. Danh mục sự kiện

### Vòng đời nhóm
`group_enrolled` · `consent_recorded` *(consent_scope, consent_version)* · `cohort_locked` · `withdrawal_requested` *(reason_code)* · `group_attrited` *(attrition_reason)*

### Cơ hội
`opportunity_registered` — đường A, lúc intake. `expected_window_start/end`, `opportunity_source: prescheduled`
`opportunity_resolved` — `status: confirmed | did_not_occur | indeterminate`, `resolution_method: prescheduled_followup | neutral_checkin`

> `indeterminate` **bắt buộc tồn tại**. Ép nhị phân sẽ đẩy mọi ca mơ hồ về phía có lợi cho sản phẩm.

### Phiên làm việc
`session_started` / `session_ended`
`organizer_input_submitted` — `input_modality: vi_text | bill_image | structured_form`, `input_seq`
`operator_action_started` / `operator_action_ended` — `action_type`, `label` *(1 trong 4)*, `label_basis` *(nhánh nào của cây quyết định)*, `reason_code`, `note_ref`
`proposal_shown_to_organizer` — `proposal_seq`
`organizer_edit` — `edit_kind: total | advancer | participants | allocation | other`, `is_material: bool`

> `is_material` chỉ true khi sửa **tổng · người ứng tiền · người tham gia · phân bổ**. Sửa chính tả không phải material. Chỉ số chất lượng AI ở spec mục 15 dựa trực tiếp vào trường này.

`organizer_confirmed` · `organizer_shared` *(share_count)* · `organizer_reminder_sent` *(recipient_ref, reminder_seq)*
`unsupported_intent` — `intent_category`, `refusal_script_id`

### Tiền
`obligation_declared` — `amount_vnd: int`, `direction`. **Số nguyên đồng. Không có số thực ở bất kỳ đâu.**
`receiver_confirmed_reported` — ai báo, lúc nào
`near_miss_logged` — `caught_at_stage`, `cause_code`
`serious_error_logged` — `error_type`, `reached_participant: true`

### Kiểm toán
`label_corrected` — **audit event, KHÔNG ghi đè nhãn cũ.** `original_label`, `new_label`, `corrected_by`, `corrected_at`
`protocol_deviation` — `deviation_code`, `protocol_version_at_time`
`independent_relabel` — `auditor_ref`, `original_label`, `auditor_label`
`harm_reported` — `severity`, `stop_rule_triggered: bool`
`diary_entry` — thời gian ngoài công cụ tự khai. `minutes: int`, `activity_code`, `entered_same_day: bool`

> `entered_same_day = false` → mục đó **bị loại** khỏi chỉ số chính, báo cáo riêng.

## 5. Log là append-only

Không `UPDATE`, không `DELETE`. Sửa = thêm sự kiện kiểm toán mới.

Lý do: nếu operator sửa được nhãn tại chỗ, danh sách `out_of_contract_rescue` sẽ teo dần một cách vô thức — và đó chính là con số quyết định "đây là phần mềm hay là dịch vụ vận hành".

Ngoại lệ duy nhất: **xoá theo yêu cầu rút lui của participant.** Thực hiện bằng quy trình xoá có ghi nhận (`erasure_executed` với `study_subject_id` và phạm vi), không phải sửa lén.

## 6. Mẫu số — chốt trước, không chốt sau

| Chỉ số | Tử số | Mẫu số |
|---|---|---|
| Tự khởi tạo | Nhóm có ≥1 `self_initiated` | Nhóm `evaluable` có `opportunity_resolved.status = confirmed` |
| Vòng thu tiền | Nghĩa vụ đạt `receiver_confirmed` trong 7 ngày | Nghĩa vụ đã tới tay, **trừ** `waived` và huỷ hợp lệ. **Tranh chấp vẫn ở mẫu số** |
| Chất lượng AI | Đề xuất được xác nhận **không có sửa material** | Mọi đề xuất đã hiển thị |
| Hiểu đúng năng lực | Trả lời đúng bot hiện chỉ làm tiền | Người đã qua onboarding |

Vòng thu tiền báo **cả** theo nghĩa vụ **và** theo nhóm. Chỉ báo theo nghĩa vụ thì ba nhóm đông người chi phối toàn bộ kết quả.

## 7. Dữ liệu thiếu

**Không bao giờ impute im lặng.** Mọi chỉ số báo kèm `N` và `N_missing`.

`N_missing / N > 20%` → chỉ số đó **không dùng để mở cổng**, chỉ mô tả.

Nhóm `attrited` và `indeterminate` báo cáo riêng, **không hoà vào mẫu số cũng không xoá**.

## 8. Khoá cohort

Gán theo **ý định lúc thu nạp**, khoá lại, **không gán lại theo hành vi**. Nhóm dùng chéo (tuyển là ở trọ nhưng dùng cho đi chơi) ghi riêng bằng `cross_use_observed`, giữ nguyên cohort gốc.

Gán lại cohort theo hành vi sẽ tạo đúng vòng luẩn quẩn spec đã cấm: dùng hành vi của mẫu thiên lệch để biện minh cho kết luận về cohort khác.
