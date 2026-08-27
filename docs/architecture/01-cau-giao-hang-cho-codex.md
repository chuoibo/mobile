# Vì sao Codex không tự giao hàng được, và cách sửa

> Chẩn đoán 2026-08-27 sau khi Codex giao 2222 dòng code chạy được nhưng **không commit và không mở PR được**, hai lượt liên tiếp.

## Triệu chứng

Codex báo `failed` ở cả hai lượt, dù code và test của nó đều xanh:

```
git add   → .../mobile/.git/worktrees/mobile-codex2/index.lock: Read-only file system
gh pr     → could not resolve host: api.github.com
```

Tôi đã ghi lại hai lần như "hạn chế hạ tầng" rồi tự commit hộ. **Đó là né triệu chứng, không phải sửa nguyên nhân.**

## Nguyên nhân 1 — worktree liên kết giữ index ở NƠI KHÁC

```
/home/lakiet/mobile-codex2/.git   →   gitdir: /home/lakiet/mobile/.git/worktrees/mobile-codex2
```

Worktree liên kết **không có `.git` riêng**. Nó là một file trỏ về repo chính. Mọi `git add` ghi vào `/home/lakiet/mobile/.git/...` — tức là:

- **ngoài writable root** của sandbox Codex, vốn chỉ mở đúng thư mục `--cwd` được giao
- và đúng thư mục tôi **cấm nó chạm** trong mọi prompt

Quyền file hoàn toàn bình thường: `drwxr-xr-x lakiet:lakiet`. **Không phải lỗi permission.** Ranh giới nằm ở sandbox.

> Đây là lỗi thiết kế của tôi. Tôi chọn `git worktree add` vì nó rẻ và nhanh, mà không kiểm nó lưu index ở đâu.

**Sửa:** cho Codex một **clone độc lập** tại `/home/lakiet/codex-repo`. `.git` nằm trong chính nó, commit được ngay.

## Nguyên nhân 2 — sandbox không phân giải được DNS tới GitHub

Cái này không đáng đánh nhau. Ngay cả khi mở được, phụ thuộc vào nó vẫn mong manh.

**Sửa:** đổi trách nhiệm. **Codex chỉ cần commit cục bộ.** Phần còn lại do một cây cầu mang đi.

## `scripts/codex-delivery.sh`

Theo dõi clone của Codex; khi thấy commit mới trên nhánh `codex/*` thì **push và mở hoặc cập nhật PR**.

```bash
scripts/codex-delivery.sh          # chạy liên tục, mặc định 60 giây
scripts/codex-delivery.sh --once   # một lượt, dùng để kiểm
```

Mỗi lần giao hàng in đúng một dòng, nên nó dùng được làm nguồn tín hiệu.

**Đã kiểm end-to-end:** một commit thử trên `codex/probe-delivery` được push và mở thành PR #6 tự động, không ai chạm vào.

## Cái này đổi được gì

| Trước | Sau |
|---|---|
| Codex commit → **thất bại** | Codex commit → **thành công** |
| Claude phát hiện, commit hộ, mở PR hộ | Cầu phát hiện, push, mở PR |
| Mỗi vòng cần một lời nhắc | Tín hiệu là **commit**, không phải lời nhắc |

## Cái này KHÔNG sửa được

**Hạn mức dùng của Codex.** Nó cạn hai lần trong một buổi. Không có cách nào lách, và cây cầu không giúp gì khi Codex không chạy.

**Codex vẫn không đọc được GitHub.** Nó không xem được comment, không đọc được review, không tự lấy diff của PR về. Verdict vẫn phải đi qua file rồi Claude đăng hộ. Sửa được chỗ này thì cần mở DNS trong sandbox của nó, ngoài tầm với ở đây.
