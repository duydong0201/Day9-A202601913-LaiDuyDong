# Báo cáo cá nhân — Day 9: Multi-Agent E-commerce Dispute Resolution

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Lại Duy Đông |
| MSSV | 2A202601913 |
| Khóa/Lớp | K3 |
| Vai trò chính | Tích hợp hệ thống, Policy và Verification |
| Ngày hoàn thành | 2026-08-05 |

## 2. Vai trò và phạm vi công việc

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Data contract và repository | `contracts.py`, `repository.py` | CSV Olist, order ID | `OrderFacts` gồm order/item/payment đã xác thực | Hoàn thành |
| Agent handoff | `agents.py`, `analysis.py` | `OrderFacts` | Handoff Order/Seller, Payment, Delivery | Hoàn thành |
| Policy và verifier | `policy.py`, `coordinator.py`, `verifier.py` | Handoff + facts | Output đúng schema sau khi verify | Hoàn thành |
| Batch delivery | `case_io.py`, `runner.py`, `trace.jsonl`, `output/` | 50 input JSON | 50 output JSON và 50 trace records | Hoàn thành |

Ngoài phần code, tôi hoàn thiện tài liệu kiến trúc và kiểm tra batch đủ 50 case trước khi đóng gói output.

## 3. Kết quả theo vai trò

| Nhiệm vụ | Artifact | Kết quả | Cách xác minh |
| --- | --- | --- | --- |
| Áp dụng chính sách | `PolicyAgent` | Phân loại 6 issue theo đúng precedence của `EC_POLICY_V1` | So sánh primary issue, root cause, refund và action với quyết định policy cho mỗi case |
| Kiểm tra output | `OutputVerifier` | Chặn lỗi schema, ID, tiền và status/refund | Re-verify 50 JSON dựa trên CSV gốc |
| Chạy batch | `output/`, `trace.jsonl` | 50 output và 50 trace record | Batch runner trả về `resolved_cases=50` |

Kết quả batch: 8 `canceled_order_paid`, 8 `unavailable_order_paid`, 8 `late_delivery_seller`, 8 `late_delivery_logistics`, 9 `valid_split_payment` và 9 `unsupported_late_claim`.

## 4. Giải thích kỹ thuật

### Vấn đề cần giải quyết

Một khiếu nại không thể được xác định chỉ từ lời nhắn của khách hàng. Pipeline phải join trạng thái order, item/seller, payment và các timestamp để phân biệt seller giao carrier muộn, logistics giao muộn, order đã hủy/không có hàng nhưng đã thanh toán, hay yêu cầu hoàn tiền không được dữ liệu hỗ trợ.

### Cách triển khai

Repository đọc CSV ở chế độ read-only và tạo `OrderFacts`. Ba agent phân tích tách riêng facts về order/seller, payment và delivery. Policy nhận các handoff để áp rule theo precedence; Coordinator chỉ hợp nhất kết quả, còn Verifier dựng lại tập evidence/entity hợp lệ từ CSV trước khi cho phép runner ghi file. Tiền được tính bằng `Decimal`, sai số đối soát payment là 0.10 BRL.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `EC_xxx.json` chứa `claimed_order_id` và `EC_POLICY_V1` |
| Output | JSON theo schema đề bài: assessment, entities, root cause, evidence, financial resolution, actions |
| Module phụ thuộc | Repository, ba agent phân tích, PolicyAgent |
| Module sử dụng output | BatchRunner, `output/`, `trace.jsonl` |
| Điều kiện lỗi | Case thiếu/sai schema, order không tồn tại, policy không có rule phù hợp, evidence không tồn tại, tổng tiền sai |

### Cách xác minh

```powershell
$env:PYTHONPATH = 'src'
& .\.venv\Scripts\python.exe -m dispute_resolution.cli run --data-dir data --input-dir input --output-dir output --trace-path trace.jsonl
```

- **Kết quả mong đợi:** 50 case được giải quyết và mỗi output vượt verifier.
- **Kết quả thực tế:** `resolved_cases=50`; kiểm tra lại độc lập xác nhận 50 output và 50 trace records hợp lệ.
- **Artifact/log:** `output/`, `trace.jsonl`, `architecture.md`; không chứa secret.

## 5. Quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần giải quyết tranh chấp dựa trên evidence, có nhiều rule ưu tiên và yêu cầu chấm chính xác số tiền/ID.
- **Các phương án:** Một prompt LLM xử lý toàn bộ case; hoặc agent chuyên trách với policy deterministic và verifier độc lập.
- **Phương án chọn:** Agent theo domain tạo handoff có cấu trúc, sau đó áp policy deterministic.
- **Lý do:** Rule có thể truy vết trực tiếp đến CSV, giữ đúng precedence, tái lập được kết quả và tránh sinh evidence không tồn tại.
- **Bằng chứng:** Toàn bộ 50 output đã được đối soát lại với CSV, policy và verifier.

## 6. Lỗi hoặc blocker đã xử lý

- **Triệu chứng:** `pip install -e .` thất bại vì không thể kết nối PyPI để tải build dependency `setuptools`.
- **Nguyên nhân gốc:** Mạng môi trường bị hạn chế, không phải lỗi business logic của project.
- **Cách xử lý:** Vì project chỉ dùng Python standard library, chạy trực tiếp source bằng `PYTHONPATH=src` với Python 3.11 trong `.venv`, không tải dependency ngoài.
- **Cách xác minh:** Compile `src` và chạy batch thành công 50 case.
- **Điều học được:** Thiết kế dependency-free giúp pipeline tái lập được trong môi trường giới hạn mạng.

## 7. Hiểu biết luồng end-to-end

1. Case cung cấp `claimed_order_id`; repository dùng ID này để lấy order, item và payment từ CSV.
2. Ba agent domain tạo handoff riêng để Coordinator không phải suy luận từ dữ liệu thô.
3. Policy áp thứ tự rule: canceled/unavailable đã trả tiền, giao trễ theo seller/logistics, split payment hợp lệ, rồi reject late claim không có căn cứ.
4. Verifier kiểm tra schema, evidence ID, entity ID, giới hạn số lượng, số tiền và status trước khi output được ghi.
5. Batch thành công khi có đủ 50 JSON tương ứng, 50 trace records, và mỗi output vượt lại validation với facts/policy gốc.

## 8. Cam kết

- [x] Nội dung phản ánh phần việc đã thực hiện và đã được kiểm chứng.
- [x] Tôi có thể giải thích luồng end-to-end của hệ thống.
- [x] Báo cáo không ghi kết quả chưa kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.

**Họ và tên:** Lại Duy Đông
**Ngày xác nhận:** 2026-08-05
