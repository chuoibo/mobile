# Measurement contract `mc-1`

- **`measurement_contract_version`:** `mc-1` — **DRAFT**
- **`protocol_version`:** `v1` — DRAFT
- DRI Claude · Reviewer Codex

> **Viết lại toàn bộ theo blocker W0-02 của Codex.** Bản đầu tham chiếu `self_initiated` và `evaluable` mà **không định nghĩa event hay phép suy ra**; thiếu khoá join; thiếu `obligation_id`, `due_at`, `capability_exposed_at`; `organizer_active_time` không có khoảng thời gian; `schema_version` không có giá trị; `cohort` không có enum; `cycle` dùng dấu `…`.
> Hậu quả: **W1 buộc phải tự phát minh field và logic join** — tức là chuyển quyền viết protocol từ Claude sang code của W1, đúng chế độ hỏng mà ADR-0001 dựng lên để chặn.

## 0. Hai version, tách bạch

Mọi event mang **cả hai**:

| Trường | Nghĩa | Đổi khi nào |
|---|---|---|
| `measurement_contract_version` | Hình dạng dữ liệu — event, field, enum, phép suy ra | Đổi schema |
| `protocol_version` | Cách chạy thực địa — script, SLA, cohort, ngưỡng | Đổi giao thức |

Tách ra vì chúng đổi vì lý do khác nhau. Sửa câu chữ script không được ép migrate schema; thêm một field không được vô hiệu hoá dữ liệu thực địa đã thu.

> ⚠️ **Đóng băng `mc-1` chỉ mở đúng một thứ: build và test W1 trên FIXTURE TỔNG HỢP.**
> Nó **KHÔNG** mở W3 · **KHÔNG** mở dữ liệu thật · **KHÔNG** thoả FIELD-GATE.

## 1. Ranh giới không được vượt

✅ **Log sự kiện quan sát được:** `operator_action_started` · `organizer_input_submitted` · `organizer_edit` · `proposal_shown_to_organizer`

❌ **KHÔNG log trạng thái sản phẩm giả định:** `CollectionBatch.published` · `SkillInvocation.succeeded` · `Proposal.confirmed` · bất kỳ tên thực thể nào ở mục 6 của spec

Đặt tên sự kiện theo ontology sản phẩm biến bản ghi nghiên cứu thành bằng chứng ủng hộ chính mô hình dữ liệu chưa được kiểm chứng.

## 2. Khoá định danh và khoá join

Không có những khoá này thì không join được, và "người thứ hai chỉ đọc log cũng phán quyết được" là lời hứa suông.

```
study_group_id ─┬─ cycle_id ─┬─ session_id ─┬─ action_id        (operator)
                │            │              ├─ proposal_id
                │            │              └─ activity_id      (khoảng thời gian organizer)
                │            └─ obligation_id                   (thuộc session sinh ra nó)
                ├─ opportunity_id
                ├─ contact_id                                   (liên hệ từ phía nghiên cứu)
                └─ study_subject_id                             (thành viên, bút danh)
```

| Khoá | Kiểu | Bắt buộc trên |
|---|---|---|
| `study_group_id` | pseudonym | **mọi** event |
| `study_subject_id` | pseudonym \| null | event gắn với một người |
| `cycle_id` | id | mọi event trong một chu kỳ |
| `session_id` | id | event trong một phiên làm việc |
| `opportunity_id` | id | event vòng đời cơ hội |
| `action_id` | id | thao tác operator, và mọi event tham chiếu nó |
| `proposal_id` | id | đề xuất và mọi sửa đổi lên nó |
| `activity_id` | id | khoảng thời gian chủ động của organizer |
| `obligation_id` | id | nghĩa vụ và mọi event về nó |
| `contact_id` | id | liên hệ từ phía nghiên cứu |
| `note_ref` | id ngoài repo | text tự do — **nội dung KHÔNG nằm trong log** |

## 3. Envelope — bắt buộc trên MỌI event

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `event_id` | uuid | |
| `event_type` | enum đóng | mục 5 |
| `measurement_contract_version` | `"mc-1"` | |
| `protocol_version` | `"v1"` | |
| `occurred_at` | ISO8601 + offset | lúc việc **xảy ra** |
| `recorded_at` | ISO8601 + offset | lúc việc **được ghi** |
| `study_group_id` | pseudonym | |
| `actor_role` | enum | `organizer` · `sender` · `operator` · `system` · `researcher` |
| `cohort` | enum | mục 4 |
| `lane` | enum | `v1_scope` · `exploration` |
| `cycle_kind` | enum | `baseline` · `concierge` |
| `cycle_index` | int ≥ 0 | thay cho `concierge_1, concierge_2, …` |
| `provenance` | enum | `instrument` · `operator_entry` · `participant_selfreport` · `researcher_entry` |
| `retention_class` | enum | `study_metrics` · `operational` · `incident` |

Múi giờ chuẩn `Asia/Ho_Chi_Minh`; lưu UTC kèm offset.

`recorded_at − occurred_at` lớn là **tín hiệu chất lượng dữ liệu**, phải báo cáo, không được im lặng bỏ qua.

## 4. Enum hữu hạn

```
cohort            : hangout_students | cohousing
                    ⚠️ superset. protocol_version quy định cohort nào ĐANG hoạt động.
                    Chờ ADR-0002. Schema KHÔNG bị chặn bởi việc đó.
lane              : v1_scope | exploration
cycle_kind        : baseline | concierge
actor_role        : organizer | sender | operator | system | researcher
provenance        : instrument | operator_entry | participant_selfreport | researcher_entry
retention_class   : study_metrics | operational | incident
input_modality    : vi_text | structured_form | bill_image
                    ⚠️ bill_image chỉ hợp lệ nếu đường ảnh còn sống sau cổng OCR 13.4
contract_authority   : permitted | not_permitted
input_provenance     : in_session | outside_session_obtainable | outside_session_impossible
generation_mechanism : deterministic_rule | model_replayable | human_judgment
operator_label    : deterministic_automatable | model_plausible | human_judgment_required
                    | out_of_contract_rescue | missing_input_deviation
opportunity_status: confirmed | did_not_occur | indeterminate
opportunity_source: prescheduled | neutral_checkin
edit_kind         : total | advancer | participants | allocation | other
error_type        : wrong_recipient | wrong_amount | wrong_obligor | phantom_obligation
attrition_reason  : withdrew | lost_contact | protocol_violation | study_ended
```

## 5. Danh mục event

### Vòng đời nhóm
| Event | Field riêng |
|---|---|
| `group_enrolled` | `enrollment_order: int` — **thứ tự đăng ký trước**, dùng để chọn nhóm evaluable |
| `consent_recorded` | `consent_scope`, `consent_version`, `covers_wizard_of_oz: bool` |
| `consent_withdrawn` | |
| `cohort_locked` | `cohort` |
| `cycle_started` / `cycle_ended` | `cycle_id` |
| `group_attrited` | `attrition_reason` |
| `erasure_executed` | `study_subject_id`, `scope` |

### Liên hệ từ phía nghiên cứu — **bắt buộc, không tuỳ chọn**
| Event | Field riêng |
|---|---|
| `research_contact` | `contact_id`, `channel`, **`mentions_service: bool`**, `script_id`, `opportunity_id` \| null |

> Không có event này thì **không thể** phán quyết "không do nhắc" ở `00-` mục 1.2, và mọi `voluntary_start` trở thành `indeterminate`.

### Cơ hội
| Event | Field riêng |
|---|---|
| `opportunity_registered` | `opportunity_id`, `window_start`, `window_end`, `opportunity_source` |
| `opportunity_evidence_recorded` | 4 cờ bằng chứng: `has_3plus_people` · `has_real_advance` · `has_real_obligation` · `cost_type_in_baseline_set`, mỗi cờ `true\|false\|unknown` |
| `opportunity_resolved` | `opportunity_status`, `resolved_by`, **`resolver_blind_to_usage: bool`**, `checkin_exposed: bool` |

> `opportunity_status = confirmed` **chỉ hợp lệ khi cả bốn cờ = true**. Bất kỳ cờ nào `unknown` ⇒ **bắt buộc** `indeterminate`. Đây là quy tắc máy kiểm tra được, không phải phán đoán.

### Phiên làm việc
| Event | Field riêng |
|---|---|
| `session_started` / `session_ended` | `session_id`, `opportunity_id` \| null |
| `organizer_activity_started` / `organizer_activity_ended` | `activity_id`, `attributed_to: cost_splitting \| other`, `source: instrument \| diary` |
| `organizer_input_submitted` | `input_modality`, `input_seq` |
| `operator_action_started` / `operator_action_ended` | `action_id`, `action_type`, `contract_authority`, `input_provenance`, `generation_mechanism`, `operator_label`, `reason_code`, `note_ref` |
| `proposal_shown_to_organizer` | `proposal_id`, `proposal_seq` |
| `organizer_edit` | `proposal_id`, `edit_kind`, `is_material: bool` |
| `organizer_confirmed` | `proposal_id` |
| `organizer_shared` | `proposal_id`, `share_count: int` |
| `organizer_reminder_sent` | `obligation_id`, `reminder_seq` |
| `unsupported_intent` | `intent_category`, `refusal_script_id` |

### Nghĩa vụ và thu tiền
| Event | Field riêng |
|---|---|
| `obligation_declared` | `obligation_id`, `proposal_id`, `amount_vnd: int`, `from_subject`, `to_subject`, `due_at` |
| `obligation_capability_exposed` | `obligation_id`, `capability_exposed_at` — **lúc nghĩa vụ TỚI TAY người gửi** |
| `receipt_confirmed` | `obligation_id`, `confirmed_by`, `confirmed_at` |
| `obligation_disputed` | `obligation_id` |
| `obligation_waived` | `obligation_id`, `waived_by` |
| `obligation_cancelled_valid` | `obligation_id`, `reason_code` |

> **Tiền là số nguyên đồng.** Không có số thực ở bất kỳ đâu.

### An toàn
| Event | Field riêng |
|---|---|
| `near_miss_logged` | `caught_at_stage`, `cause_code` |
| `serious_error_logged` | `error_type`, `reached_participant: true`, `obligation_id` \| null |
| `harm_reported` | `severity`, `stop_rule_triggered: bool` |

### Kiểm toán
| Event | Field riêng |
|---|---|
| `label_corrected` | **`action_id`** (bắt buộc), `original_label`, `new_label`, `corrected_by` |
| `independent_relabel` | **`action_id`** (bắt buộc), `auditor_ref`, `auditor_label`, `sampling_seed`, `sampling_stratum` |
| `protocol_deviation` | `deviation_code`, `protocol_version_at_time` |

## 6. Bất biến máy kiểm tra được

1. **Consent đi trước.** Không event nghiên cứu nào của một nhóm có `occurred_at` sớm hơn `consent_recorded` của nhóm đó. Vi phạm ⇒ dữ liệu **không dùng được**, không phải cảnh báo.
2. **Append-only.** Không `UPDATE`, không `DELETE`. Sửa = thêm event kiểm toán. Ngoại lệ duy nhất: `erasure_executed` theo yêu cầu rút lui.
3. **Khoá tham chiếu tồn tại.** Mọi `action_id`, `proposal_id`, `obligation_id`, `opportunity_id` được tham chiếu phải có event tạo tương ứng.
4. `obligation_capability_exposed.occurred_at` ≥ `obligation_declared.occurred_at`.
5. `cohort` không đổi sau `cohort_locked`.
6. `opportunity_status = confirmed` ⟺ cả bốn cờ bằng chứng = true.

> Bất biến 1 và 2 là lý do log phải append-only: nếu operator sửa được nhãn tại chỗ, danh sách `out_of_contract_rescue` sẽ teo dần một cách vô thức — mà đó chính là con số quyết định "phần mềm hay dịch vụ vận hành".

## 7. Bảng suy ra — mỗi chỉ số ở `03-` một dòng

| Chỉ số | Suy ra từ | Mẫu số |
|---|---|---|
| `voluntary_start` | `organizer_input_submitted` đầu tiên trong `opportunity_id`, **không có** `research_contact` nào `mentions_service=true` sớm hơn trong cùng cơ hội | — |
| **`qualifying_repeat`** | tồn tại chuỗi trong cùng `opportunity_id`: `voluntary_start` → `organizer_confirmed` → `organizer_shared` → ≥1 `obligation_declared` **không** bị `obligation_cancelled_valid` | nhóm `evaluable` có `opportunity_status = confirmed` |
| `evaluable_group` | có `cycle_ended` cho baseline **và** ≥1 concierge, **và** có `opportunity_resolved` với status ≠ `indeterminate` | mọi nhóm đã `group_enrolled` |
| `organizer_active_time` | Σ (`organizer_activity_ended` − `organizer_activity_started`) với `attributed_to = cost_splitting`. Khoảng không đóng trong `T_idle = 120s` kể từ event cuối thì **đóng tại event cuối** | median theo nhóm |
| Thu tiền 7 ngày | `receipt_confirmed` với `confirmed_at` ≤ `max(due_at, capability_exposed_at) + 7 ngày` | nghĩa vụ đã `obligation_capability_exposed`, **trừ** `waived` và `cancelled_valid`. **`disputed` VẪN ở mẫu số** |
| Chất lượng AI | `organizer_confirmed` mà `proposal_id` đó **không** có `organizer_edit` nào `is_material=true` | mọi `proposal_shown_to_organizer` |
| Tỉ lệ can thiệp | action có `operator_label ∈ {human_judgment_required, out_of_contract_rescue}` | mọi `operator_action_started` |
| `serious_error` | đếm `serious_error_logged` | phải bằng **0** |
| Đồng thuận nhãn | join `independent_relabel` với `operator_action_started` qua `action_id`; confusion matrix + đồng thuận **theo từng lớp** | mẫu phân tầng theo `sampling_stratum` |

**`T_idle = 120 giây` là hằng số của hợp đồng, không phải chi tiết hiện thực.** Để W1 tự chọn thì hai lần phân tích trên cùng log sẽ ra hai con số.

## 8. Dữ liệu thiếu

**Không bao giờ impute im lặng.** Mọi chỉ số báo kèm `N` và `N_missing`.

`N_missing / N > 20%` → chỉ số đó **không dùng để mở cổng**, chỉ mô tả.

Nhóm `attrited` và cơ hội `indeterminate` báo cáo **riêng** — không hoà vào mẫu số, không xoá.

Mất liên lạc nên không biết nhóm có cơ hội hay không → báo missing và chạy **best/worst-case bounds**. Chỉ GO nếu kết luận **không đảo** dưới giả định bảo thủ.

## 9. Khoá cohort

Gán theo **ý định lúc thu nạp**, khoá bằng `cohort_locked`, **không gán lại theo hành vi**. Nhóm dùng chéo ghi `cross_use_observed`, giữ nguyên cohort gốc.

## 10. Trường BỊ CẤM trong log

❌ Tên thật · điện thoại · email · số tài khoản · tên ngân hàng gắn với người · ảnh bill · text thô tin nhắn participant · tên nhóm chat.

Text tự do sống ở **kho ngoài repo**, tham chiếu bằng `note_ref`. Log mang **mã lý do có enum**, không mang câu chữ.

Log là thứ sẽ được copy, export, đưa vào script phân tích, dán vào issue. Mỗi lần copy là một cơ hội rò.

## 11. Golden event stream — bắt buộc trước khi W1 được coi là xong

Chuỗi event **tổng hợp**, mỗi loại có ca **dương và âm**, để hai bên phân tích độc lập phải ra cùng con số:

`qualifying_repeat` · `valid_cost_opportunity` · `organizer_active_time` (gồm ca `T_idle`) · tỉ lệ can thiệp · thu tiền 7 ngày (gồm `disputed`, `waived`, `cancelled_valid`) · `attrition` · `missingness` · vi phạm bất biến consent.

Hai bên chạy trên cùng chuỗi mà ra khác số ⇒ **hợp đồng chưa đủ chặt**, không phải một bên tính sai.
